"""py2app build for the repo-backed LearnHarness.app (Stage A, `make app`).

Alias mode (-A) produces a real app bundle whose stub runs macos/launcher.py in place with the repo venv, so code
edits show up on relaunch, and macOS privacy prompts (microphone, speech) are attributed to LearnHarness with the
usage descriptions below.
"""
from setuptools import setup

PLIST = {
    "CFBundleName": "LearnHarness",
    "CFBundleDisplayName": "LearnHarness",
    "CFBundleIdentifier": "io.github.chow-n.learnharness",
    "CFBundleShortVersionString": "0.2.0",
    "CFBundleVersion": "0.2.0",
    "LSMinimumSystemVersion": "13.0",
    "NSHighResolutionCapable": True,
    "LSApplicationCategoryType": "public.app-category.education",
    "NSMicrophoneUsageDescription": "LearnHarness listens while you dictate your reasoning and measures prosody "
                                    "(latency, pauses, pace) as learning telemetry. Audio stays on this Mac.",
    "NSSpeechRecognitionUsageDescription": "LearnHarness transcribes your spoken reasoning on-device so you can "
                                           "think aloud instead of typing.",
}

setup(
    app=["macos/launcher.py"],
    name="LearnHarness",
    options={"py2app": {"iconfile": "macos/LearnHarness.icns", "plist": PLIST, "argv_emulation": False}},
)
