"""Text-to-speech: pyttsx3 (offline) or edge-tts (higher quality, needs internet)."""
from __future__ import annotations

import queue
import re
import threading
from typing import Optional

import config

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

try:
    import edge_tts
except ImportError:
    edge_tts = None


class TTS:
    def __init__(self, rate: Optional[int] = None, volume: Optional[float] = None):
        self._rate = rate if rate is not None else getattr(config, "TTS_RATE", 175)
        self._volume = volume if volume is not None else getattr(config, "TTS_VOLUME", 1.0)
        self._engine_name = getattr(config, "TTS_ENGINE", "pyttsx3").lower()
        self._edge_voice = getattr(config, "TTS_EDGE_VOICE", "en-US-AriaNeural")
        self._pyttsx_engine = None
        self._queue: queue.Queue[str] = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._stop = threading.Event()
        # Optional callbacks for UI (e.g., visualizer)
        self.on_start_speaking = None
        self.on_stop_speaking = None

    def _get_pyttsx(self):
        if pyttsx3 is None:
            raise RuntimeError("pyttsx3 is not installed. Install with: pip install pyttsx3")
        if self._pyttsx_engine is None:
            self._pyttsx_engine = pyttsx3.init()
            self._pyttsx_engine.setProperty("rate", self._rate)
            self._pyttsx_engine.setProperty("volume", self._volume)
        return self._pyttsx_engine

    def _speak_pyttsx3(self, text: str) -> None:
        engine = self._get_pyttsx()
        engine.say(text)
        engine.runAndWait()

    def _speak_edge(self, text: str) -> None:
        if edge_tts is None:
            raise RuntimeError("edge-tts is not installed. Install with: pip install edge-tts")
        import asyncio
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            path = f.name
        try:
            async def _save():
                communicate = edge_tts.Communicate(text, self._edge_voice)
                await communicate.save(path)
            asyncio.run(_save())
            self._play_mp3(path, text)
        finally:
            try:
                os.unlink(path)
            except Exception:
                pass

    def _play_mp3(self, path: str, text: str) -> None:
        """Play an MP3 file (blocking). Tries playsound, then pygame, then system open."""
        try:
            import playsound
            playsound.playsound(path, block=True)
            return
        except Exception:
            pass
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=24000, size=-16, channels=1, buffer=512)
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            import time
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            return
        except Exception:
            pass
        import subprocess
        import time
        if os.name == "nt":
            subprocess.Popen(["cmd", "/c", "start", "/wait", path], shell=True)
            time.sleep(max(2, len(text) / 10))
        else:
            subprocess.run(["mpv", path, "--no-video"], capture_output=True)

    def _sanitize_for_speech(self, text: str) -> str:
        """Remove asterisks and other formatting that TTS reads aloud awkwardly."""
        if not text:
            return text
        # Remove ** ... ** (bold markers) but keep the inner text
        out = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        # Remove any remaining asterisks
        out = out.replace("*", "")
        # Collapse multiple spaces and trim
        return re.sub(r"  +", " ", out).strip()

    def _speak_one(self, text: str) -> None:
        text = self._sanitize_for_speech(text)
        if not text or not text.strip():
            return
        if callable(self.on_start_speaking):
            try:
                self.on_start_speaking()
            except Exception:
                pass
        try:
            if self._engine_name == "edge" and edge_tts:
                try:
                    self._speak_edge(text)
                except Exception:
                    if pyttsx3:
                        self._speak_pyttsx3(text)
                    else:
                        raise
            elif pyttsx3:
                self._speak_pyttsx3(text)
            else:
                raise RuntimeError("No TTS engine available. Install pyttsx3 or edge-tts.")
        finally:
            if callable(self.on_stop_speaking):
                try:
                    self.on_stop_speaking()
                except Exception:
                    pass

    def speak(self, text: str, block: bool = False) -> None:
        """Speak `text`. If block=True, wait until done."""
        if not text or not text.strip():
            return
        if block:
            self._speak_one(text)
            return
        self._queue.put(text)
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._run_worker, daemon=True)
            self._worker.start()

    def _run_worker(self) -> None:
        while not self._stop.is_set():
            try:
                text = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if not text:
                continue
            try:
                self._speak_one(text)
            except Exception:
                pass

    def stop(self) -> None:
        self._stop.set()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        if self._pyttsx_engine:
            try:
                self._pyttsx_engine.stop()
            except Exception:
                pass
