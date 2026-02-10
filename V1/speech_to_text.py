import os
import pyaudio
import vosk
import queue
import sys
import json
import threading

# Vosk small model - CPU only
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "vosk", "vosk-model-small-en-us-0.15")

if not os.path.exists(MODEL_PATH):
    print(f"ERROR: Vosk model not found at {MODEL_PATH}")
    print("Download from: https://alphacephei.com/vosk/models")
    sys.exit(1)

model = vosk.Model(MODEL_PATH)

stop_listening_flag = threading.Event()

RATE = 16000
CHUNK = 8000
FORMAT = pyaudio.paInt16
CHANNELS = 1


def record_voice(prompt="I'm listening..."):
    print(prompt)
    rec = vosk.KaldiRecognizer(model, RATE)
    p = pyaudio.PyAudio()

    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )

    try:
        while not stop_listening_flag.is_set():
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
            except Exception:
                continue
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get("text", "")
                if text.strip():
                    print("You:", text)
                    return text
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

    return ""
