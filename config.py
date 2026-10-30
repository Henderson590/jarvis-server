# Jarvis-like Assistant - Configuration
# Edit these to customize wake word, models, and behavior.
#
# ---------------------------------------------------------------------------
# DEPENDENCIES (pip packages). Install before running. Copy-paste this line:
#   pip install pyttsx3 openwakeword numpy pyautogui pynput psutil duckduckgo-search requests opencv-python Pillow ollama customtkinter python-dotenv pyperclip schedule
# Optional (voice input): pip install openai-whisper
# Optional (better TTS): pip install edge-tts playsound   (then set TTS_ENGINE = "edge" below)
# Optional (wake word + Listen mic): pip install pyaudio   OR install ffmpeg and add to PATH (Listen will use ffmpeg if pyaudio fails)
# ---------------------------------------------------------------------------

import os as _os

try:
    from dotenv import load_dotenv as _load_dotenv
    # Loads variables from a local .env file (same folder as this file) into the
    # process environment. .env is gitignored - see .env.example for the template.
    _load_dotenv(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".env"))
except ImportError:
    pass  # python-dotenv not installed yet; env vars set another way still work

# Wake word phrase (used for display; detection may use a similar model)
WAKE_WORD = "Hey Jarvis"

# Ollama model for chat and command understanding
# qwen2.5:7b = best instruction-following, minimal roleplay, fast. Run: ollama pull qwen2.5:7b
# Alternatives: command-r:7b, mistral:7b-instruct, phi3:latest, llama3.2
OLLAMA_CHAT_MODEL = "qwen2.5:7b"

# Ollama vision model for camera "what do you see"
OLLAMA_VISION_MODEL = "llava"

# Ollama base URL (default: local)
OLLAMA_HOST = "http://localhost:11434"

# How long Ollama keeps a model loaded in memory after a request before
# unloading it. Ollama's own default is 5 minutes ("5m"); reloading a
# multi-GB model from disk is usually the single biggest cause of slow
# responses, so this project uses a longer default. "-1" keeps it loaded
# indefinitely (fastest, but ties up RAM/VRAM even when idle); "30m" is a
# reasonable middle ground. Lower this if you're tight on memory and running
# other GPU/RAM-heavy programs alongside Jarvis.
OLLAMA_KEEP_ALIVE = "30m"

# Whisper model size: tiny, base, small, medium, large (larger = more accurate, slower)
# Use "tiny" for fastest local transcription.
WHISPER_MODEL = "tiny"

# TTS: "pyttsx3" (offline, fastest to start speaking) or "edge" (better quality, slower, needs internet)
# For edge: pip install edge-tts
TTS_ENGINE = "edge"

# Edge TTS voice (only when TTS_ENGINE = "edge"). Examples:
#   en-US-AriaNeural (female), en-US-GuyNeural (male), en-GB-SoniaNeural, en-AU-NatashaNeural
TTS_EDGE_VOICE = "en-GB-RyanNeural"

# Pyttsx3 only: voice rate (wpm) and volume (0.0-1.0)
TTS_RATE = 195
TTS_VOLUME = 1.2

# Web search: max results to return
WEB_SEARCH_MAX_RESULTS = 5

# Google search (optional). If set, uses Google instead of DuckDuckGo.
# Get API key: https://console.cloud.google.com/ (enable Custom Search API)
# Get search engine ID: https://programmablesearchengine.google.com/ (create a search engine)
# Free tier: 100 queries/day.
#
# SECURITY: these are now loaded from a local .env file (see .env.example) instead of
# being hardcoded here. Never put real keys directly in config.py again - config.py is
# the kind of file that ends up shared, zipped, or committed by accident.
GOOGLE_SEARCH_API_KEY = _os.environ.get("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_SEARCH_ENGINE_ID = _os.environ.get("GOOGLE_SEARCH_ENGINE_ID", "")

# Camera: index (0 = default webcam)
CAMERA_INDEX = 0

# Always speak every response out loud (so you hear replies without looking at the screen)
SPEAK_RESPONSES = True

# Microphone selection for wake word and voice input:
# - MIC_DEVICE_INDEX: explicit PyAudio device index (see \"list microphones\" command)
# - MIC_DEVICE_NAME: substring to match in device name (e.g. \"yeti\", \"usb microphone\");
#   used if MIC_DEVICE_INDEX is None.
MIC_DEVICE_INDEX = 3  # e.g. 0, 1, 2 ...
MIC_DEVICE_NAME = None

# Conversation listening (silence-based, not a fixed duration): after the wake
# word or after Jarvis finishes speaking, the mic opens and waits for you to
# start talking. If you don't within CONVERSATION_SILENCE_TIMEOUT_SECONDS, it
# drops back to needing the wake word. Once you start talking, it keeps
# recording until that many seconds of continuous silence follow, then treats
# that as the end of your sentence.
CONVERSATION_SILENCE_TIMEOUT_SECONDS = 5.0
# Hard cap on a single utterance's length, regardless of silence detection -
# a safety valve against a noisy room (TV, music) that never reads as "silent".
CONVERSATION_MAX_UTTERANCE_SECONDS = 45.0

# Voice-activity detection sensitivity for the above. The silence threshold is
# auto-calibrated against a brief ambient-noise sample each time Jarvis starts
# listening, then scaled by VAD_SILENCE_MULTIPLIER, with VAD_MIN_ENERGY_THRESHOLD
# as a floor so a near-silent room doesn't make it overly trigger-happy on tiny
# noises. Raise VAD_SILENCE_MULTIPLIER or VAD_MIN_ENERGY_THRESHOLD if it's
# picking up background noise as speech; lower them if it's cutting you off or
# not noticing you've started talking.
VAD_SILENCE_MULTIPLIER = 2.5
VAD_MIN_ENERGY_THRESHOLD = 150.0

# Used by the manual "Listen" button (fixed-duration recording, unrelated to
# the silence-based conversation loop above) and as a fallback recording
# length wherever a fixed duration is still needed.
LISTEN_DURATION_SECONDS = 5.0

# Timer check interval in milliseconds (how often to check for due timers)
TIMER_CHECK_INTERVAL_MS = 2000

# Data folder for notes, todos, reminders (default: same folder as main.py)
DATA_DIR = ""

# How many recent user/assistant turns to send to Ollama for context (0 = no history)
# Lower = faster responses, less context. 4 is optimal for speed + continuity.
CONVERSATION_HISTORY_SIZE = 4

# Weather: "metric" (C) or "imperial" (F)
WEATHER_UNITS = "imperial"

# Ollama timeout in seconds (0 = no timeout)
OLLAMA_TIMEOUT = 30

# Strip roleplay/formatting from LLM responses (asterisks, *actions*, etc.)
STRIP_ROLEPLAY = True

# Vision speed: max image dimension sent to LLaVA (lower = faster, less precise). 768 is a good balance.
VISION_MAX_DIM = 768

# Seconds to wait for page load before screenshot (search+add-to-cart flow)
PAGE_LOAD_WAIT_SECONDS = 4.0

# System prompt for LLM: enforce strict instruction-following, zero roleplay
SYSTEM_PROMPT_STRICT = (
    "You are a direct command executor. Execute exactly what the user asks. "
    "Never roleplay. Never use asterisks, *actions*, or **bold** for actions. "
    "Never say you cannot do something if the user requested it. "
    "Respond in plain text only. Be terse and factual. No embellishment."
)
