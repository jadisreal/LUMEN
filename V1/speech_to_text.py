# speech_to_text.py - Whisper STT (local, fully offline via faster-whisper)

import os
import time
import threading
import numpy as np
import pyaudio
from faster_whisper import WhisperModel
from core.logger import get_logger
from core.audio import get_audio_instance

log = get_logger("stt")

# ── Model config ──────────────────────────────────────────────
MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")


def _init_whisper():
    """Initialize Whisper with CUDA if available, CPU fallback."""
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            log.info(f"Loading Whisper '{MODEL_SIZE}' on CUDA (float16)...")
            m = WhisperModel(MODEL_SIZE, device="cuda", compute_type="float16")
            log.info("Whisper loaded on GPU.")
            return m
    except Exception as e:
        log.warning(f"CUDA init failed, falling back to CPU: {e}")

    log.info(f"Loading Whisper '{MODEL_SIZE}' on CPU (int8)...")
    m = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    log.info("Whisper loaded on CPU.")
    return m


model = _init_whisper()

stop_listening_flag = threading.Event()

# ── Audio config ──────────────────────────────────────────────
TARGET_RATE = 16000
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1

# ── Silence / VAD config ─────────────────────────────────────
SILENCE_THRESHOLD = int(os.getenv("SILENCE_THRESHOLD", "400"))
SILENCE_DURATION = float(os.getenv("SILENCE_DURATION", "1.8"))
MIN_RECORD_SECONDS = 0.4

# ── Retry config ─────────────────────────────────────────────
MAX_MIC_RETRIES = 3
MIC_RETRY_DELAY = 2.0

# ── Whisper hallucination filter ─────────────────────────────
# Whisper hallucinates these on silence or ambient noise.
HALLUCINATION_BLACKLIST = {
    "thank you",
    "thanks for watching",
    "thanks for listening",
    "subscribe",
    "like and subscribe",
    "please subscribe",
    "see you next time",
    "bye",
    "goodbye",
    "you",
    "the end",
    "hmm",
    "huh",
    "...",
    "ah",
    "oh",
    "uh",
    "um",
    "so",
    "",
}


def _is_hallucination(text: str) -> bool:
    """Check if transcription is a known Whisper hallucination."""
    cleaned = text.lower().strip().rstrip(".!?,;:")
    if cleaned in HALLUCINATION_BLACKLIST:
        return True
    # Single-word garbage (1-2 chars)
    if len(cleaned) <= 2:
        return True
    # Repeated single word/phrase (e.g. "Thank you. Thank you. Thank you.")
    words = cleaned.split()
    if len(words) >= 3 and len(set(words)) == 1:
        return True
    return False


def _get_input_device_info():
    """Query the default input device and return its supported config."""
    try:
        p = get_audio_instance()
        info = p.get_default_input_device_info()
        log.debug(f"Default input device: {info.get('name')} "
                  f"(channels={info.get('maxInputChannels')}, "
                  f"rate={info.get('defaultSampleRate')})")
        return info
    except Exception as e:
        log.error(f"No input device found: {e}")
        return None


def _open_mic_stream(p: pyaudio.PyAudio):
    """
    Open a microphone stream using the shared PyAudio instance.
    Falls back to the device's native sample rate if 16kHz isn't supported.
    """
    info = p.get_default_input_device_info()
    max_channels = int(info.get("maxInputChannels", 1))
    native_rate = int(info.get("defaultSampleRate", TARGET_RATE))

    channels = min(CHANNELS, max_channels) if max_channels > 0 else 1

    # Try 16kHz first (Whisper's native rate)
    for rate in [TARGET_RATE, native_rate]:
        try:
            stream = p.open(
                format=FORMAT,
                channels=channels,
                rate=rate,
                input=True,
                frames_per_buffer=CHUNK,
            )
            log.info(f"Mic opened: rate={rate}, channels={channels}")
            return stream, rate, channels
        except OSError as e:
            log.warning(f"Mic open failed at rate={rate}, channels={channels}: {e}")
            continue

    raise OSError("Could not open any microphone configuration")


def _rms(chunk: np.ndarray) -> float:
    """Root-mean-square energy of an int16 audio chunk."""
    return float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))


def _resample(audio: np.ndarray, orig_rate: int, target_rate: int) -> np.ndarray:
    """Simple linear resampling from orig_rate to target_rate."""
    if orig_rate == target_rate:
        return audio
    duration = len(audio) / orig_rate
    target_len = int(duration * target_rate)
    indices = np.linspace(0, len(audio) - 1, target_len)
    return np.interp(indices, np.arange(len(audio)), audio.astype(np.float64)).astype(audio.dtype)


def record_voice(prompt="I'm listening..."):
    """
    Record from the microphone until speech is detected and then
    silence follows. Transcribe with Whisper and return the text.
    Retries on mic failure up to MAX_MIC_RETRIES times.
    """
    log.debug(prompt)

    p = get_audio_instance()

    for attempt in range(1, MAX_MIC_RETRIES + 1):
        try:
            stream, actual_rate, actual_channels = _open_mic_stream(p)
            break
        except OSError as e:
            log.error(f"Mic attempt {attempt}/{MAX_MIC_RETRIES} failed: {e}")
            if attempt < MAX_MIC_RETRIES:
                time.sleep(MIC_RETRY_DELAY)
            else:
                log.critical("All mic retries exhausted. Returning empty.")
                return ""

    frames: list[np.ndarray] = []
    speech_detected = False
    silent_chunks = 0
    silence_chunks_needed = int(SILENCE_DURATION * actual_rate / CHUNK)
    min_chunks = int(MIN_RECORD_SECONDS * actual_rate / CHUNK)

    try:
        while not stop_listening_flag.is_set():
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
            except OSError as e:
                log.warning(f"Mic read error (recovering): {e}")
                continue

            audio_chunk = np.frombuffer(data, dtype=np.int16)

            # If stereo, take only first channel
            if actual_channels > 1:
                audio_chunk = audio_chunk[::actual_channels]

            frames.append(audio_chunk)

            if _rms(audio_chunk) > SILENCE_THRESHOLD:
                speech_detected = True
                silent_chunks = 0
            else:
                silent_chunks += 1

            if speech_detected and silent_chunks >= silence_chunks_needed and len(frames) >= min_chunks:
                break
    except Exception as e:
        log.error(f"Recording loop error: {e}", exc_info=True)
    finally:
        try:
            stream.stop_stream()
            stream.close()
        except Exception:
            pass

    if not speech_detected or not frames:
        return ""

    # Merge chunks → float32 [-1, 1]
    audio = np.concatenate(frames).astype(np.float32) / 32768.0

    # Resample to 16kHz if mic used a different rate
    if actual_rate != TARGET_RATE:
        audio = _resample(audio, actual_rate, TARGET_RATE).astype(np.float32)

    try:
        segments, _ = model.transcribe(audio, language="en", beam_size=5)
        text = " ".join(seg.text.strip() for seg in segments).strip()
    except Exception as e:
        log.error(f"Whisper transcription error: {e}", exc_info=True)
        return ""

    if not text:
        return ""

    if _is_hallucination(text):
        log.debug(f"Filtered hallucination: '{text}'")
        return ""

    log.info(f"You: {text}")
    return text
