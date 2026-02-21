# tts.py - Piper TTS (fully offline, raw PCM streaming)

import os
import threading
import pyaudio
from core.logger import get_logger
from core.sanitizer import sanitize_for_tts
from core.audio import get_audio_instance

log = get_logger("tts")

PIPER_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "piper")

stop_speaking_flag = threading.Event()

# Lazy-loaded voice instance
_voice = None
_voice_lock = threading.Lock()


def _get_voice():
    """Load Piper voice model on first use."""
    global _voice
    if _voice is not None:
        return _voice

    with _voice_lock:
        if _voice is not None:
            return _voice

        from piper import PiperVoice

        model_path = None
        if os.path.isdir(PIPER_MODEL_DIR):
            for f in os.listdir(PIPER_MODEL_DIR):
                if f.endswith(".onnx"):
                    model_path = os.path.join(PIPER_MODEL_DIR, f)
                    break

        if not model_path:
            raise FileNotFoundError(
                f"No Piper .onnx model found in {PIPER_MODEL_DIR}\n"
                "Download a voice from: https://huggingface.co/rhasspy/piper-voices\n"
                "Place the .onnx and .onnx.json files in V1/models/piper/"
            )

        log.info(f"Loading Piper voice: {os.path.basename(model_path)}")
        _voice = PiperVoice.load(model_path)
        log.info("Piper voice loaded.")
        return _voice


def speak(text: str, ui=None, blocking=False):
    """Synthesize text with Piper TTS and stream raw PCM to PyAudio."""
    if not text or not text.strip():
        return

    # Sanitize before speaking — strip JSON, code, role markers, etc.
    clean_text = sanitize_for_tts(text)
    if not clean_text:
        log.debug(f"TTS skipped (nothing speakable after sanitize): '{text[:80]}'")
        return

    finished_event = threading.Event()

    def _thread():
        if ui:
            ui.start_speaking()
        stop_speaking_flag.clear()

        try:
            voice = _get_voice()

            p = get_audio_instance()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=voice.config.sample_rate,
                output=True,
                frames_per_buffer=1024
            )

            for chunk in voice.synthesize(clean_text):
                if stop_speaking_flag.is_set():
                    break
                stream.write(chunk.audio_int16_bytes)

            stream.stop_stream()
            stream.close()

        except FileNotFoundError as e:
            log.error(f"Piper model missing: {e}")
        except OSError as e:
            log.error(f"Audio output error: {e}")
        except Exception as e:
            log.error(f"TTS error: {e}", exc_info=True)
        finally:
            if ui:
                ui.stop_speaking()
            finished_event.set()

    threading.Thread(target=_thread, name="tts", daemon=True).start()

    if blocking:
        finished_event.wait()


def stop_speaking():
    """Stop current speech playback."""
    stop_speaking_flag.set()
