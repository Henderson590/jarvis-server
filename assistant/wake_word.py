"""Wake word detection: listen for 'Hey Jarvis' to activate."""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

try:
    import pyaudio  # can fail with broken C module '_portaudio'
    import numpy as np
    import openwakeword
    from openwakeword.model import Model
    import config
    from . import audio_devices
    _OWW_AVAILABLE = True
except Exception:
    _OWW_AVAILABLE = False

# Cooldown between detections (seconds)
WAKE_COOLDOWN = 2.0
SAMPLE_RATE = 16000
CHUNK = 1280
_WAKE_MODEL_NAME = "hey_jarvis"


def run_wake_word_loop(
    on_wake: Callable[[], None],
    stop_event: Optional[threading.Event] = None,
    on_status: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Blocking loop: listen for "hey jarvis" and call on_wake() when detected.
    Uses openwakeword's dedicated "hey_jarvis" model (ONNX backend, so no
    separate tflite_runtime dependency needed).

    on_status, if given, receives short human-readable status/error strings.
    Wire it to your UI's log - setup problems here (missing model download,
    no usable microphone, etc.) used to fail completely silently, which is
    why "say the wake word" could just quietly do nothing forever with no
    indication why.
    """
    def status(msg: str) -> None:
        if on_status:
            try:
                on_status(msg)
            except Exception:
                pass

    if not _OWW_AVAILABLE:
        status("Wake word unavailable: openwakeword/pyaudio/numpy not installed.")
        return

    # openwakeword ships model *definitions* but not the model weight files -
    # those are downloaded on first use and cached under the openwakeword
    # package directory. This is idempotent (skips re-downloading if already
    # present), so it's safe to call on every startup.
    try:
        openwakeword.utils.download_models([_WAKE_MODEL_NAME])
    except Exception as e:
        status(f"Could not download the wake word model ({e}). Check your internet connection.")
        return

    try:
        oww_model = Model(wakeword_models=[_WAKE_MODEL_NAME], inference_framework="onnx")
    except Exception as e:
        status(f"Wake word model failed to load: {e}")
        return

    pa = pyaudio.PyAudio()
    device_index = None
    device_label = "system default"
    try:
        index = getattr(config, "MIC_DEVICE_INDEX", None)
        name_sub = (getattr(config, "MIC_DEVICE_NAME", "") or "").lower()
        count = pa.get_device_count()
        if isinstance(index, int):
            try:
                info = pa.get_device_info_by_index(index)
                if info.get("maxInputChannels", 0) > 0:
                    device_index = index
                    device_label = str(info.get("name", index))
            except Exception:
                device_index = None
        if device_index is None and name_sub:
            for i in range(count):
                try:
                    info = pa.get_device_info_by_index(i)
                    if info.get("maxInputChannels", 0) <= 0:
                        continue
                    if name_sub in str(info.get("name", "")).lower():
                        device_index = i
                        device_label = str(info.get("name", i))
                        break
                except Exception:
                    continue
    except Exception:
        device_index = None

    try:
        stream, actual_rate = audio_devices.open_input_stream(
            pa,
            device_index,
            preferred_rate=SAMPLE_RATE,
            channels=1,
            frames_per_buffer=CHUNK,
        )
    except Exception as e:
        status(f"Could not open microphone ({device_label}): {e}")
        pa.terminate()
        return

    if actual_rate != SAMPLE_RATE:
        status(
            f'"{device_label}" doesn\'t support 16kHz directly - recording at '
            f"{actual_rate}Hz and converting. This should still work fine."
        )
    else:
        status(f'Wake word ready - listening on "{device_label}" for "hey Jarvis".')

    # If we had to fall back to the device's native rate, each read() gives us
    # native-rate samples covering the same time window as CHUNK would at
    # 16kHz - resample that down to CHUNK samples at 16kHz before handing it
    # to the model, which expects 16kHz input.
    read_size = int(round(CHUNK * actual_rate / SAMPLE_RATE))

    last_wake = 0.0
    try:
        while True:
            if stop_event and stop_event.is_set():
                break
            try:
                raw = stream.read(read_size, exception_on_overflow=False)
            except Exception as e:
                status(f"Microphone read failed, wake word stopped: {e}")
                break
            audio = np.frombuffer(raw, dtype=np.int16)
            if actual_rate != SAMPLE_RATE and len(audio) > 1:
                # Simple linear-interpolation resample - good enough for wake
                # word detection, which doesn't need studio-quality audio.
                orig_idx = np.linspace(0, len(audio) - 1, CHUNK)
                audio = np.interp(orig_idx, np.arange(len(audio)), audio).astype(np.int16)
            prediction = oww_model.predict(audio)
            score = prediction.get(_WAKE_MODEL_NAME, 0.0)
            if score > 0.5 and (time.time() - last_wake) >= WAKE_COOLDOWN:
                last_wake = time.time()
                on_wake()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        status(f"Wake word loop stopped unexpectedly: {e}")
    finally:
        try:
            stream.stop_stream()
            stream.close()
        except Exception:
            pass
        pa.terminate()


def start_wake_word_background(
    on_wake: Callable[[], None],
    stop_event: Optional[threading.Event] = None,
    on_status: Optional[Callable[[str], None]] = None,
) -> threading.Thread:
    """Start wake word detection in a daemon thread. Returns the thread."""
    def run():
        try:
            run_wake_word_loop(on_wake, stop_event=stop_event, on_status=on_status)
        except Exception as e:
            if on_status:
                try:
                    on_status(f"Wake word thread crashed: {e}")
                except Exception:
                    pass

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t
