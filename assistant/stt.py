"""Speech-to-text using local Whisper so we can process microphone input."""
from __future__ import annotations

import io
import os
import threading
import wave
from typing import Optional

import config

# Lazy-load Whisper (heavy); optional dependency
_whisper_model = None
# Whisper is not thread-safe; kv_cache corrupts when used concurrently
_transcribe_lock = threading.Lock()

# Whisper expects 16 kHz mono float32
WHISPER_SAMPLE_RATE = 16000


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper
            _whisper_model = whisper.load_model(config.WHISPER_MODEL)
        except ImportError as e:
            raise RuntimeError(
                "Whisper is not installed. Install with: pip install openai-whisper"
            ) from e
        except Exception as e:
            raise RuntimeError(f"Failed to load Whisper model: {e}") from e
    return _whisper_model


def _wav_bytes_to_numpy(wav_bytes: bytes) -> "np.ndarray":
    """Convert WAV bytes to float32 mono numpy array at 16 kHz. No ffmpeg needed."""
    import numpy as np
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    if sample_width == 2:  # 16-bit
        audio = np.frombuffer(raw, dtype=np.int16)
    elif sample_width == 4:  # 32-bit
        audio = np.frombuffer(raw, dtype=np.int32)
    else:
        raise ValueError(f"Unsupported sample width: {sample_width}")

    audio = audio.astype(np.float32) / 32768.0

    if n_channels == 2:
        audio = audio.reshape(-1, 2).mean(axis=1)

    if framerate != WHISPER_SAMPLE_RATE:
        # Resample to 16 kHz using linear interpolation
        duration = len(audio) / framerate
        new_length = int(duration * WHISPER_SAMPLE_RATE)
        indices = np.linspace(0, len(audio) - 1, new_length)
        audio = np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

    return audio


def transcribe_audio_bytes(wav_bytes: bytes, language: Optional[str] = None) -> str:
    """Transcribe raw WAV bytes (16-bit mono, 16kHz or 44.1kHz) to text. No ffmpeg required."""
    model = _get_whisper()
    audio = _wav_bytes_to_numpy(wav_bytes)
    with _transcribe_lock:
        result = model.transcribe(audio, language=language, fp16=False)
    return (result.get("text") or "").strip()


def transcribe_file(path: str, language: Optional[str] = None) -> str:
    """Transcribe a WAV file to text."""
    model = _get_whisper()
    with _transcribe_lock:
        result = model.transcribe(path, language=language, fp16=False)
    return (result.get("text") or "").strip()


def _record_via_ffmpeg(seconds: float, sample_rate: int = 16000) -> Optional[bytes]:
    """Record using ffmpeg (Windows dshow or Linux alsa). Use when PyAudio is broken/unavailable."""
    import subprocess
    import tempfile
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        try:
            if os.name == "nt":
                # Windows: use DirectShow. Try common device names.
                for device in ["Microphone", "Audio (Microphone)", "Default"]:
                    cmd = [
                        "ffmpeg", "-y", "-loglevel", "error", "-f", "dshow",
                        "-i", f"audio={device}",
                        "-t", str(seconds),
                        "-acodec", "pcm_s16le", "-ar", str(sample_rate), "-ac", "1",
                        path,
                    ]
                    r = subprocess.run(cmd, capture_output=True, timeout=int(seconds) + 10)
                    if r.returncode == 0 and os.path.isfile(path) and os.path.getsize(path) > 0:
                        with open(path, "rb") as f:
                            return f.read()
            else:
                cmd = [
                    "ffmpeg", "-y", "-loglevel", "error", "-f", "pulse" if os.path.exists("/dev/snd") else "alsa",
                    "-i", "default",
                    "-t", str(seconds),
                    "-acodec", "pcm_s16le", "-ar", str(sample_rate), "-ac", "1",
                    path,
                ]
                subprocess.run(cmd, capture_output=True, timeout=int(seconds) + 10)
                if os.path.isfile(path) and os.path.getsize(path) > 0:
                    with open(path, "rb") as f:
                        return f.read()
        finally:
            try:
                os.unlink(path)
            except Exception:
                pass
    except Exception:
        pass
    return None


def _choose_input_device(pa) -> Optional[int]:
    """
    Choose a PyAudio input device based on config.MIC_DEVICE_INDEX or MIC_DEVICE_NAME.
    Returns the device index or None to use the default.
    """
    index = getattr(config, "MIC_DEVICE_INDEX", None)
    name_sub = (getattr(config, "MIC_DEVICE_NAME", "") or "").lower()
    chosen: Optional[int] = None
    try:
        count = pa.get_device_count()
    except Exception:
        return None
    # Explicit index takes priority
    if isinstance(index, int):
        try:
            info = pa.get_device_info_by_index(index)
            if info.get("maxInputChannels", 0) > 0:
                chosen = index
        except Exception:
            chosen = None
    # Otherwise, match by substring in name
    if chosen is None and name_sub:
        try:
            for i in range(count):
                try:
                    info = pa.get_device_info_by_index(i)
                    if info.get("maxInputChannels", 0) <= 0:
                        continue
                    if name_sub in str(info.get("name", "")).lower():
                        chosen = i
                        break
                except Exception:
                    continue
        except Exception:
            chosen = None
    return chosen


def listen_until_silence(
    max_wait_for_speech: float = 5.0,
    silence_duration: float = 5.0,
    max_recording_seconds: float = 45.0,
    sample_rate: int = 16000,
) -> Optional[bytes]:
    """
    Stream from the microphone with simple energy-based silence detection,
    instead of recording a blind fixed duration:

      - Waits up to `max_wait_for_speech` seconds for you to start talking.
        If nothing is heard in that window, returns None - the caller should
        treat that as "no one's talking, drop back to needing the wake word".
      - Once speech is detected, keeps recording until `silence_duration`
        seconds of continuous silence follow, then returns everything
        captured (including a little audio from just before the threshold
        was crossed, so the first syllable doesn't get clipped) as WAV bytes.
      - `max_recording_seconds` is a hard cap so a noisy room (music, a TV)
        can't keep it recording forever.

    The silence threshold is auto-calibrated against a brief sample of
    ambient room noise at the start of each call rather than a fixed
    constant, since "quiet room" and "noisy room" differ by an order of
    magnitude in practice. Tune via config.VAD_SILENCE_MULTIPLIER and
    config.VAD_MIN_ENERGY_THRESHOLD if it's too trigger-happy or too
    insensitive for your mic/room.

    Returns None (no ffmpeg fallback here) if PyAudio/the mic isn't
    available - ffmpeg only supports fixed-duration recording, not this
    kind of streaming detection. record_from_microphone() still exists with
    the ffmpeg fallback for callers that just need a fixed-length clip.
    """
    try:
        import pyaudio
        import numpy as np
        from . import audio_devices
    except Exception:
        return None

    import time as _time
    from collections import deque

    chunk_seconds = 0.1  # 100ms analysis window: responsive without being noisy
    multiplier = getattr(config, "VAD_SILENCE_MULTIPLIER", 2.5)
    min_threshold = getattr(config, "VAD_MIN_ENERGY_THRESHOLD", 150.0)

    pa = None
    stream = None
    try:
        pa = pyaudio.PyAudio()
        device_index = _choose_input_device(pa)
        stream, actual_rate = audio_devices.open_input_stream(
            pa, device_index, preferred_rate=sample_rate, channels=1,
            frames_per_buffer=max(1, int(sample_rate * chunk_seconds)),
        )
        chunk_frames = max(1, int(round(actual_rate * chunk_seconds)))

        def read_chunk() -> "np.ndarray":
            raw = stream.read(chunk_frames, exception_on_overflow=False)
            return raw, np.frombuffer(raw, dtype=np.int16)

        def rms(samples: "np.ndarray") -> float:
            if len(samples) == 0:
                return 0.0
            return float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))

        # Calibrate against ~300ms of ambient noise before listening for real.
        ambient_samples = []
        for _ in range(3):
            try:
                _, samples = read_chunk()
                ambient_samples.append(rms(samples))
            except Exception:
                break
        ambient_rms = sum(ambient_samples) / len(ambient_samples) if ambient_samples else 0.0
        threshold = max(ambient_rms * multiplier, min_threshold)

        pre_buffer: deque = deque(maxlen=2)  # ~200ms of lead-in, kept until speech starts
        frames = []
        speech_started = False
        start_ts = _time.time()
        last_voice_ts = start_ts

        while True:
            now = _time.time()
            try:
                raw, samples = read_chunk()
            except Exception:
                break

            is_voice = rms(samples) > threshold

            if not speech_started:
                pre_buffer.append(raw)
                if is_voice:
                    speech_started = True
                    frames = list(pre_buffer)
                    last_voice_ts = now
                elif now - start_ts >= max_wait_for_speech:
                    return None  # nobody said anything - caller drops to wake-word mode
            else:
                frames.append(raw)
                if is_voice:
                    last_voice_ts = now
                if now - last_voice_ts >= silence_duration:
                    break  # done talking
                if now - start_ts >= max_recording_seconds:
                    break  # safety valve

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(actual_rate)
            wf.writeframes(b"".join(frames))
        return buf.getvalue()
    except Exception:
        return None
    finally:
        try:
            if stream:
                stream.stop_stream()
                stream.close()
        except Exception:
            pass
        try:
            if pa:
                pa.terminate()
        except Exception:
            pass


def record_from_microphone(seconds: float = 5.0, sample_rate: int = 16000) -> Optional[bytes]:
    """
    Record from the default microphone for `seconds` and return WAV bytes (16-bit mono).
    Tries PyAudio first; if that fails (e.g. broken _portaudio), tries ffmpeg.
    Returns None if both fail.
    """
    # Try PyAudio first (may print "Could not import PyAudio C module" to console if broken)
    try:
        import pyaudio
        import wave
        import io
        from . import audio_devices
        CHUNK = 1024
        pa = pyaudio.PyAudio()
        device_index = _choose_input_device(pa)
        stream, actual_rate = audio_devices.open_input_stream(
            pa, device_index, preferred_rate=sample_rate, channels=1, frames_per_buffer=CHUNK,
        )
        frames = []
        n_chunks = int(actual_rate * seconds / CHUNK)
        for _ in range(n_chunks):
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
            except Exception:
                break
        stream.stop_stream()
        stream.close()
        pa.terminate()
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            # Write the rate we actually recorded at - _wav_bytes_to_numpy
            # already resamples to WHISPER_SAMPLE_RATE based on this header,
            # so this doesn't need to match `sample_rate` exactly.
            wf.setframerate(actual_rate)
            wf.writeframes(b"".join(frames))
        return buf.getvalue()
    except Exception:
        pass
    # Fallback: ffmpeg (no PyAudio needed). Install ffmpeg and add to PATH.
    return _record_via_ffmpeg(seconds, sample_rate)
