"""py2app build for the repo-backed Pólya.app (Stage A, `make app`).

Alias mode (-A) produces a real app bundle whose stub runs macos/launcher.py in place with the repo venv, so code
edits show up on relaunch, and macOS privacy prompts (microphone, speech) are attributed to Pólya with the
usage descriptions below.
"""
from setuptools import setup

PLIST = {
    "CFBundleName": "Pólya",
    "CFBundleDisplayName": "Pólya",
    "CFBundleIdentifier": "io.github.chow-n.polya",
    "CFBundleShortVersionString": "0.3.0",
    "CFBundleVersion": "0.3.0",
    "LSMinimumSystemVersion": "13.0",
    "NSHighResolutionCapable": True,
    "LSApplicationCategoryType": "public.app-category.education",
    "NSMicrophoneUsageDescription": "Pólya listens while you dictate your reasoning and measures prosody "
                                    "(latency, pauses, pace) as learning telemetry. Audio stays on this Mac.",
    "NSSpeechRecognitionUsageDescription": "Pólya transcribes your spoken reasoning on-device so you can "
                                           "think aloud instead of typing.",
}

if __name__ == "__main__":
    setup(
        app=["macos/launcher.py"],
        name="Pólya",
        options={"py2app": {"iconfile": "macos/Polya.icns", "plist": PLIST, "argv_emulation": False}},
    )
