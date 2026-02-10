# tts.py - Piper TTS (fully offline)

import os
import io
import wave
import threading
import pyaudio

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
                "Place the .onnx and .onnx.json files in MarkX/models/piper/"
            )

        print(f"Loading Piper voice: {os.path.basename(model_path)}")
        _voice = PiperVoice.load(model_path)
        print("Piper voice loaded.")
        return _voice


def speak(text: str, ui=None, blocking=False):
    """Synthesize text with Piper TTS and play via PyAudio."""
    if not text or not text.strip():
        return

    finished_event = threading.Event()

    def _thread():
        if ui:
            ui.start_speaking()
        stop_speaking_flag.clear()

        try:
            voice = _get_voice()

            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wav_file:
                voice.synthesize(text.strip(), wav_file)

            wav_buffer.seek(0)

            with wave.open(wav_buffer, "rb") as wf:
                p = pyaudio.PyAudio()
                stream = p.open(
                    format=p.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True,
                    frames_per_buffer=1024
                )

                chunk_size = 1024
                data = wf.readframes(chunk_size)
                while data:
                    if stop_speaking_flag.is_set():
                        break
                    stream.write(data)
                    data = wf.readframes(chunk_size)

                stream.stop_stream()
                stream.close()
                p.terminate()

        except FileNotFoundError as e:
            print(f"PIPER ERROR: {e}")
        except Exception as e:
            print(f"VOICE ERROR: {e}")
        finally:
            if ui:
                ui.stop_speaking()
            finished_event.set()

    threading.Thread(target=_thread, daemon=True).start()

    if blocking:
        finished_event.wait()


def stop_speaking():
    """Stop current speech playback."""
    stop_speaking_flag.set()
