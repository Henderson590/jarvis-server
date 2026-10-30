"""Audio device helpers (PyAudio input devices).

Windows exposes almost every physical microphone multiple times - once per
audio host API (MME, DirectSound, WASAPI, WDM-KS) - which is why a naive
device listing can show 8-12 near-identical entries for what's really 2-3
physical mics. This narrows that down to one clean entry per physical
device, using WASAPI (the modern, low-latency Windows API where each device
appears exactly once) as the canonical source.

This also provides open_input_stream(), a shared helper used by both
wake_word.py and stt.py to actually open a recording stream. Some devices
(webcams, cheap USB mics) only support their own native sample rate and
reject others outright - PyAudio/PortAudio raises "Invalid sample rate"
rather than silently adapting. Earlier versions of this file tried to
*predict* that in advance with pa.is_format_supported(), but that call
turned out to be unreliable in both directions (both false positives and
false negatives were observed against real hardware). It's more robust to
just try opening at the preferred rate and fall back to the device's native
rate on failure - see open_input_stream().
"""
from __future__ import annotations

from typing import List, Optional, Tuple

_TARGET_RATE = 16000  # what wake_word and Whisper both want


def list_input_devices() -> List[Tuple[int, str]]:
    """
    Return (device_index, device_name) for input devices that are real (not
    a duplicate host-API entry for the same physical mic). The system
    default device, if present, is labeled "(default)" and sorted first.
    """
    try:
        import pyaudio
    except Exception:
        return []

    pa = None
    try:
        pa = pyaudio.PyAudio()

        # Find WASAPI - each physical device appears exactly once under it,
        # unlike the legacy MME/DirectSound APIs which each re-list every
        # device separately.
        wasapi_index = None
        for i in range(pa.get_host_api_count()):
            try:
                api_info = pa.get_host_api_info_by_index(i)
                if "wasapi" in str(api_info.get("name", "")).lower():
                    wasapi_index = i
                    break
            except Exception:
                continue

        default_name = ""
        try:
            default_name = str(pa.get_default_input_device_info().get("name", "")).strip().lower()
        except Exception:
            pass

        def _gather(require_wasapi: bool) -> list:
            found = []
            for i in range(pa.get_device_count()):
                try:
                    info = pa.get_device_info_by_index(i)
                except Exception:
                    continue
                if info.get("maxInputChannels", 0) <= 0:
                    continue
                if require_wasapi and info.get("hostApi") != wasapi_index:
                    continue
                found.append(info)
            return found

        candidates = _gather(require_wasapi=True) if wasapi_index is not None else []
        if not candidates:
            # WASAPI unavailable - fall back to everything, deduped by name,
            # rather than showing nothing or a huge duplicated list.
            seen_names = set()
            for info in _gather(require_wasapi=False):
                name = str(info.get("name", ""))
                if name in seen_names:
                    continue
                seen_names.add(name)
                candidates.append(info)

        out: List[Tuple[int, str]] = []
        default_entry = None
        for info in candidates:
            idx = int(info["index"])
            name = str(info.get("name", "")).strip()
            is_default = name.lower() == default_name
            label = f"{name} (default)" if is_default else name
            entry = (idx, label)
            if is_default:
                default_entry = entry
            else:
                out.append(entry)

        if default_entry:
            out.insert(0, default_entry)

        return out
    finally:
        try:
            if pa:
                pa.terminate()
        except Exception:
            pass


def open_input_stream(
    pa,
    device_index: Optional[int],
    preferred_rate: int = _TARGET_RATE,
    channels: int = 1,
    frames_per_buffer: int = 1024,
):
    """
    Open a PyAudio input stream, preferring `preferred_rate` but falling
    back to the device's own native rate if it rejects that (common with
    webcam/USB mics, which often only support 44100/48000 and raise
    "Invalid sample rate" for anything else).

    Returns (stream, actual_rate) - callers that need audio at a specific
    rate (like wake_word's 16kHz model) must resample if actual_rate !=
    preferred_rate; callers that just need *a* usable recording (like
    stt.record_from_microphone, which resamples after the fact anyway) can
    use actual_rate directly.
    """
    import pyaudio

    try:
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=preferred_rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=frames_per_buffer,
        )
        return stream, preferred_rate
    except Exception:
        pass

    try:
        info = (
            pa.get_device_info_by_index(device_index)
            if device_index is not None
            else pa.get_default_input_device_info()
        )
        native_rate = int(info.get("defaultSampleRate", 44100) or 44100)
    except Exception:
        native_rate = 44100

    stream = pa.open(
        format=pyaudio.paInt16,
        channels=channels,
        rate=native_rate,
        input=True,
        input_device_index=device_index,
        frames_per_buffer=frames_per_buffer,
    )
    return stream, native_rate

