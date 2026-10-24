"""On-device macOS dictation (SFSpeechRecognizer + AVAudioEngine via PyObjC) for the Mac app.

Exposed through the existing `/ws/dictation` protocol (docs/API.md), so the frontend treats it like the Deepgram
relay. Only enabled in app mode: TCC terminates a process that requests speech/microphone access without the
usage descriptions in its own bundle's Info.plist, which only Pólya.app provides.
"""
from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable, Optional

from . import config

try:  # PyObjC is macOS-only and optional
    import AVFoundation
    import Speech
    from Foundation import NSLocale, NSOperationQueue
    _IMPORT_ERROR = ""
except Exception as e:  # pragma: no cover - non-macOS or missing wheels
    AVFoundation = Speech = NSLocale = NSOperationQueue = None  # type: ignore[assignment]
    _IMPORT_ERROR = str(e)

# SFSpeechRecognizerAuthorizationStatus
NOT_DETERMINED, DENIED, RESTRICTED, AUTHORIZED = 0, 1, 2, 3
TASK_RESTART_S = 50.0   # Apple caps a recognition task at ~1 minute; roll over before that


def available() -> bool:
    """Native dictation can be offered: app mode, PyObjC present, recognizer usable."""
    if not config.APP_MODE or Speech is None:
        return False
    try:
        r = Speech.SFSpeechRecognizer.alloc().init()
        return bool(r and r.isAvailable())
    except Exception:
        return False


def unavailable_reason() -> str:
    if not config.APP_MODE:
        return "native dictation runs only inside the Pólya app"
    if Speech is None:
        return f"PyObjC Speech framework unavailable: {_IMPORT_ERROR}"
    return "speech recognizer unavailable on this Mac"


async def ensure_authorized(timeout: float = 120.0) -> tuple[bool, str]:
    """Ask once for speech-recognition and microphone permission (system prompts name Pólya)."""
    loop = asyncio.get_running_loop()

    status = Speech.SFSpeechRecognizer.authorizationStatus()
    if status == NOT_DETERMINED:
        fut: asyncio.Future[int] = loop.create_future()
        Speech.SFSpeechRecognizer.requestAuthorization_(
            lambda s: loop.call_soon_threadsafe(lambda: fut.done() or fut.set_result(int(s))))
        try:
            status = await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            return False, "speech permission prompt not answered"
    if status != AUTHORIZED:
        return False, "speech recognition permission denied (System Settings → Privacy & Security → Speech Recognition)"

    media = AVFoundation.AVMediaTypeAudio
    mic = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(media)
    if mic == 0:
        mfut: asyncio.Future[bool] = loop.create_future()
        AVFoundation.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
            media, lambda ok: loop.call_soon_threadsafe(lambda: mfut.done() or mfut.set_result(bool(ok))))
        try:
            granted = await asyncio.wait_for(mfut, timeout)
        except asyncio.TimeoutError:
            return False, "microphone permission prompt not answered"
    else:
        granted = mic == 3
    if not granted:
        return False, "microphone permission denied (System Settings → Privacy & Security → Microphone)"
    return True, ""


class NativeDictation:
    """Continuous dictation: partial results stream as interim text, each task's final result is committed.

    `on_message` receives dicts shaped like the Deepgram relay frames:
    {"type": "transcript", "text", "is_final", "words": [{"word", "start", "end"}]}
    and is called from a background operation queue (callers must hop to their event loop).
    """

    def __init__(self, on_message: Callable[[dict[str, Any]], None], locale: str = "en-US") -> None:
        self.on_message = on_message
        self.locale = locale
        self._lock = threading.Lock()
        self._active = False
        self._engine = None
        self._request = None
        self._task = None
        self._timer: Optional[threading.Timer] = None
        self._recognizer = None
        self._last_text = ""

    def start(self) -> None:
        with self._lock:
            if self._active:
                return
            self._active = True
        self._recognizer = Speech.SFSpeechRecognizer.alloc().initWithLocale_(
            NSLocale.localeWithLocaleIdentifier_(self.locale)) or Speech.SFSpeechRecognizer.alloc().init()
        queue = NSOperationQueue.alloc().init()
        queue.setMaxConcurrentOperationCount_(1)
        self._recognizer.setQueue_(queue)   # results off the main thread; no AppKit run-loop dependency
        self._engine = AVFoundation.AVAudioEngine.alloc().init()
        node = self._engine.inputNode()
        fmt = node.outputFormatForBus_(0)
        node.installTapOnBus_bufferSize_format_block_(0, 1024, fmt, self._on_buffer)
        self._engine.prepare()
        ok, err = self._engine.startAndReturnError_(None)
        if not ok:
            self.stop()
            raise RuntimeError(f"audio engine failed to start: {err}")
        self._new_task()

    def _on_buffer(self, buffer, when) -> None:
        req = self._request
        if req is not None:
            req.appendAudioPCMBuffer_(buffer)

    def _new_task(self) -> None:
        req = Speech.SFSpeechAudioBufferRecognitionRequest.alloc().init()
        req.setShouldReportPartialResults_(True)
        if self._recognizer.supportsOnDeviceRecognition():
            req.setRequiresOnDeviceRecognition_(True)
        if hasattr(req, "setAddsPunctuation_"):
            req.setAddsPunctuation_(True)
        self._last_text = ""
        self._request = req
        self._task = self._recognizer.recognitionTaskWithRequest_resultHandler_(req, self._on_result)
        self._timer = threading.Timer(TASK_RESTART_S, self._roll_over)
        self._timer.daemon = True
        self._timer.start()

    def _roll_over(self) -> None:
        """End the current task (its final result is committed) and continue in a fresh one."""
        with self._lock:
            if not self._active:
                return
            old = self._request
            self._request = None
        if old is not None:
            old.endAudio()

    def _on_result(self, result, error) -> None:
        if result is not None:
            best = result.bestTranscription()
            text = str(best.formattedString())
            words = [{"word": str(s.substring()), "start": float(s.timestamp()),
                      "end": float(s.timestamp() + s.duration())} for s in best.segments()]
            final = bool(result.isFinal())
            self._last_text = text
            self.on_message({"type": "transcript", "text": text, "is_final": final, "words": words})
            if final:
                self._continue()
            return
        if error is not None:
            if self._last_text:   # a task that errored after speech still commits what it heard
                self.on_message({"type": "transcript", "text": self._last_text, "is_final": True, "words": []})
            self._continue()

    def _continue(self) -> None:
        if self._timer:
            self._timer.cancel()
        with self._lock:
            active = self._active
        if active:
            self._new_task()

    def stop(self) -> None:
        with self._lock:
            self._active = False
        if self._timer:
            self._timer.cancel()
        try:
            if self._engine is not None:
                self._engine.stop()
                self._engine.inputNode().removeTapOnBus_(0)
        finally:
            if self._request is not None:
                self._request.endAudio()
            if self._task is not None:
                self._task.finish()
            self._engine = self._request = self._task = None
