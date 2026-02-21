# core/audio.py - Shared PyAudio instance for LUMEN
#
# PortAudio (the C library under PyAudio) uses GLOBAL state.
# Creating multiple PyAudio() instances in different threads causes
# Pa_Initialize() / Pa_Terminate() to race, corrupting internal state
# and causing a hard C-level segfault with no Python traceback.
#
# Solution: ONE PyAudio instance for the entire process lifetime.
# All audio code (STT, TTS) must use get_audio_instance() instead of
# creating their own PyAudio().
#
# Streams are opened/closed normally — only the PyAudio *instance*
# (and its Pa_Initialize/Pa_Terminate lifecycle) is shared.

import threading
import pyaudio
from core.logger import get_logger

log = get_logger("audio")

_instance: pyaudio.PyAudio | None = None
_lock = threading.Lock()


def get_audio_instance() -> pyaudio.PyAudio:
    """
    Return the shared PyAudio instance (created once, never terminated).

    Thread-safe. Call this instead of pyaudio.PyAudio() anywhere in the app.
    Individual streams can still be opened/closed freely — it's only the
    Pa_Initialize/Pa_Terminate lifecycle that must not overlap.
    """
    global _instance
    if _instance is not None:
        return _instance

    with _lock:
        if _instance is not None:
            return _instance
        log.info("Initializing shared PyAudio (PortAudio).")
        _instance = pyaudio.PyAudio()
        return _instance
