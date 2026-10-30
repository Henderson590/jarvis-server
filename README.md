# Jarvis-like Local Assistant

A voice-controlled, locally-running AI assistant inspired by Iron Man's J.A.R.V.I.S. It listens for a wake word, takes voice or text input, and executes commands directly on your computer — search, control apps, type, mouse, camera, and more.

**Architecture (Phase 1):** Jarvis runs on a tool-calling planner — the LLM is given a registry of tools (open an app, read a file, search the web, etc.) and decides which to call and in what order, instead of matching your exact phrasing against hardcoded patterns. This means paraphrasing and multi-step requests ("open notepad and type today's date") work without any per-phrase code. See `assistant/agent/` for the implementation.

**Memory (Phase 2):** Jarvis now remembers things about you across restarts — facts, preferences, and habits are stored locally in `jarvis_memory.db` and automatically pulled into context on every relevant message, so you don't have to repeat yourself between sessions. See `assistant/memory/` for the implementation, and `PHASE3_HANDOFF.md` for the full technical writeup and what's next.

## Features

- **Wake word** – Say "Hey Jarvis" to start a conversation
- **Always-conversational voice** – No toggle to turn on: after the wake word (or after each response), the mic stays open and listens until you go quiet for a few seconds, then processes what you said. After responding, it goes right back to listening - keep talking naturally without repeating the wake word each time. Only stops and needs "Hey Jarvis" again once you've gone quiet for `config.CONVERSATION_SILENCE_TIMEOUT_SECONDS` (default 5s) with nothing new to say. No fixed recording length, so you won't get cut off mid-sentence.
- **Text input** – Type instead of talking any time
- **Open anything** – Apps by name, sites (YouTube, Reddit, etc.), or search on a site ("open YouTube and search for X")
- **Web search** – Google or DuckDuckGo; open browser with search or on-site search (YouTube, Amazon, Wikipedia, etc.)
- **To-do & notes** – "Add milk to my list", "What's on my list?", "Create a note: meeting at 3", "Clear my list"
- **Reminders & timers** – "Remind me in 20 minutes to call mom", "Set a timer for 5 minutes" (reminders saved to disk, timers in-memory)
- **Weather** – "What's the weather?" or "Weather in Austin" (Open-Meteo, no API key)
- **Quick math** – "What is 15% of 80?", "Calculate 23 times 4"
- **System** – Lock PC, volume up/down/mute/set, system info (CPU/RAM), screenshot
- **Files & folders** – "What's on my desktop?", "Create a folder called Projects", "Open my downloads", read/write/append/delete text files
- **Clipboard** – Read or set clipboard
- **Camera & screen vision** – "What do you see?", "What's on my screen?" (Ollama LLaVA)
- **Simple 3D scenes** – "Make a 3D scene of a table in Blender"
- **Confirmation on risky actions** – deleting a file, clearing your to-do list, adding something to a shopping cart, or locking the PC all ask "yes/no" first
- **Conversation memory** – Recent turns sent to Ollama for follow-up context within a session
- **Persistent memory** – Facts, preferences, and habits you mention are remembered across restarts (e.g. "I use VS Code", "when I say send it, use Outlook") and pulled back in automatically when relevant. Ask "what do you know about me?" any time to see what's stored.
- **Multi-step requests** – "Open notepad, type hello, and take a screenshot" runs as one request

## Requirements

- **Windows 10/11** (this project targets Windows only for now)
- **Python 3.11 or 3.12** — **do not use 3.13/3.14 yet.** Confirmed: PyAudio has no Windows wheel past 3.13, and pydantic-core (an `ollama` dependency) has been seen installing a mismatched binary on 3.14, which breaks `import ollama` while `pip list` still shows it installed. If you already have 3.14 as your main Python, that's fine — just point this project's venv at 3.11/3.12 specifically with `py -3.12 -m venv venv` instead of `python -m venv venv`.
- **Ollama** – [Download Ollama](https://ollama.ai) and install. Then run:
  ```bash
  ollama pull qwen2.5:7b
  ollama pull llava
  ```
  `qwen2.5:7b` is the default chat model and **must support tool/function calling** — the whole assistant is built around it deciding which tools to call. `llava` is used for camera/screen vision. If you swap `OLLAMA_CHAT_MODEL` in `config.py` for a different model, confirm on Ollama's model page that it lists "Tools" support, or the assistant will fall back to plain chat with no ability to actually do anything.
  This project only uses **free, local models through Ollama** — no paid API keys are required anywhere.
- **Voice input (optional)** – For "Listen" and wake-word voice commands, install Whisper:
  ```bash
  pip install openai-whisper
  ```
  On first use it will download a small model (e.g. `base`). Without Whisper, you can still use text input and all other features.

## Quick Start (full checklist — start to finish)

**Run on Windows**, using **PowerShell** or **Command Prompt** (not WSL/Ubuntu). If you use Cursor or VS Code, pick "PowerShell" or "Command Prompt" as the terminal profile so commands run on Windows, not Linux.

1. **Extract this project folder** somewhere on your PC (e.g. your Desktop or Documents).

2. **Install Ollama** if you haven't already: [ollama.ai](https://ollama.ai) → download → install → it runs in the background automatically (check for its icon in the system tray).

3. **Pull the two models it needs** (one-time, downloads a few GB):
   ```powershell
   ollama pull qwen2.5:7b
   ollama pull llava
   ```

4. **Open a terminal in the project folder:**
   ```powershell
   cd "C:\path\to\wherever\you\extracted\this\folder"
   ```

5. **Create and activate a virtual environment** (keeps dependencies isolated — recommended):
   ```powershell
   python -m venv venv
   venv\Scripts\activate
   ```
   You'll know it worked if your prompt now starts with `(venv)`. You'll need to run `venv\Scripts\activate` again every time you open a new terminal to run Jarvis.

6. **Install dependencies:**
   ```powershell
   pip install pyttsx3 openwakeword numpy pyautogui pynput psutil duckduckgo-search requests opencv-python Pillow "ollama>=0.4.0" customtkinter python-dotenv pyperclip schedule
   ```
   Optional — **better voice (TTS)**: `pip install edge-tts "playsound==1.2.2"` (the default `config.py` already has `TTS_ENGINE = "edge"` set, so install this unless you switch it back to `"pyttsx3"`). **Use `playsound==1.2.2` specifically** — version 1.3.0 has a broken `setup.py` that fails to build on modern pip (a known upstream bug, unrelated to this project). If you skip playsound entirely, `assistant/tts.py` falls back to `pygame` or the system's default player automatically.
   Optional — **voice input** (Listen / wake word): `pip install openai-whisper`.
   Optional — **microphone issues**: if you see "Could not import the PyAudio C module", install [ffmpeg](https://ffmpeg.org/download.html) and add it to your PATH — the Listen button will use it instead. Wake word specifically still needs `pyaudio`.

7. **(Optional) Set up Google search** — only if you want Google instead of the no-setup-required DuckDuckGo fallback. See "Using Google for web search" below.

8. **Run it:**
   ```powershell
   python main.py
   ```

9. Say **"Hey Jarvis"** or type in the text box, then give a command — e.g. "Open Notepad", "What's the weather", "Search for Python tutorials", "What do you see?". For anything Jarvis flags as risky (deleting a file, clearing your list, adding to a cart, locking the PC), it'll ask "yes/no" before doing it — just answer normally.

**Each time you come back later:** open a terminal in the project folder, run `venv\Scripts\activate`, then `python main.py`. Make sure Ollama is running (it usually auto-starts with Windows — check the system tray).

## Configuration

- **Wake word**: Default is "Hey Jarvis". You can change it in `config.py` (if using Porcupine you’d need a custom model; with openwakeword you can train or use a similar phrase).
- **Voice conversation timing**: `config.CONVERSATION_SILENCE_TIMEOUT_SECONDS` (default 5s) controls both how long it'll wait for you to start talking before giving up, and how much silence means you're done talking. `config.CONVERSATION_MAX_UTTERANCE_SECONDS` (default 45s) is a hard cap so a noisy room can't keep it recording forever. If it's cutting you off too early or too late, or picking up background noise as speech, also see `VAD_SILENCE_MULTIPLIER` and `VAD_MIN_ENERGY_THRESHOLD` in `config.py`.
- **Ollama**: Ensure Ollama is running (often starts with Windows). Default model names are in `config.py`.

### Using Google for web search

By default the assistant uses DuckDuckGo (no setup). To use **Google** instead:

1. **API key**: In [Google Cloud Console](https://console.cloud.google.com/), create or select a project, enable **Custom Search API**, and create credentials (API key).
2. **Search engine ID**: Go to [Programmable Search Engine](https://programmablesearchengine.google.com/), add a search engine that searches the whole web, and copy the **Search engine ID** (cx).

Then copy `.env.example` to `.env` (same folder as `main.py`) and fill in:
```
GOOGLE_SEARCH_API_KEY=your-api-key
GOOGLE_SEARCH_ENGINE_ID=your-search-engine-id
```
`.env` is gitignored and loaded automatically at startup — **never put real keys directly in `config.py`**, since that file is easy to accidentally share or commit. Google Custom Search has a **free tier of 100 queries per day**. If `.env` is missing or blank, search falls back to DuckDuckGo automatically.

## Performance (slow responses)

If Jarvis takes minutes to reply, check these roughly in order:

1. **Model reload between messages.** By default Ollama unloads a model after 5 minutes idle, and reloading a multi-GB model from disk is usually the single biggest source of slow responses — often bigger than the actual thinking time. This project sets `OLLAMA_KEEP_ALIVE = "30m"` in `config.py` so the model stays loaded between your messages; if you're still seeing long waits specifically after a pause, try `"-1"` to keep it loaded indefinitely (costs RAM/VRAM even when idle).
2. **CPU vs GPU.** Run `ollama ps` in a terminal while Jarvis is thinking — it shows whether the model is running on your GPU or falling back to CPU. CPU inference for a 7B model is dramatically slower (this is a hardware/driver question, not something this project's code controls).
3. **Model size.** `qwen2.5:7b` is a solid, capable default, but on modest hardware a smaller model responds noticeably faster at some cost to how well it follows complex tool-calling instructions. To try one: `ollama pull qwen2.5:3b` (or `qwen2.5:1.5b` for the fastest option), then change `OLLAMA_CHAT_MODEL` in `config.py` to match. Confirm whatever you pick supports tool/function calling (check its Ollama model page for "Tools") or Jarvis won't be able to act on anything.
4. **Multi-step requests take multiple model round-trips by design** — "open notepad, type hello, and take a screenshot" is 3-4 separate tool calls, each a full trip through the model. This is inherent to how the tool-calling planner works (see Phase 1 above); a single-tool request like "what's the weather" should be much faster than a chained one.

## Project Structure

```
Jarvis/
├── main.py                    # Entry point & UI
├── config.py                  # Settings, dependency list, and behavior options
├── .env                       # Local secrets (gitignored) - Google search key, etc.
├── .env.example                # Template for .env
├── jarvis_memory.db            # Persistent memory (gitignored, created on first run)
├── assistant/
│   ├── brain.py                # Thin compatibility shim -> delegates to agent/planner.py
│   ├── agent/                  # Phase 1: the tool-calling planner core
│   │   ├── planner.py           # The agentic loop: LLM decides which tools to call; injects memory context
│   │   ├── registry.py          # @tool decorator - the plugin contract for capabilities
│   │   ├── tools_system.py      # Desktop control: apps, keyboard, mouse, clipboard, volume
│   │   ├── tools_files.py       # File & folder read/write/delete
│   │   ├── tools_web.py         # Browser & web search
│   │   ├── tools_productivity.py # Todos, notes, timers, reminders, weather, math
│   │   ├── tools_vision.py      # Camera & screen understanding
│   │   ├── tools_blender.py     # Simple 3D scene generation
│   │   └── tools_memory.py      # Phase 2: remember/forget facts, preferences, procedures
│   ├── memory/                  # Phase 2: persistent memory
│   │   ├── db.py                 # SQLite connection & schema
│   │   └── store.py              # CRUD + keyword-based retrieval for all 4 memory types
│   ├── tts.py                  # Text-to-speech
│   ├── stt.py                  # Speech-to-text (Whisper)
│   ├── wake_word.py            # Wake word detection ("hey_jarvis" model, explicit + status-reporting)
│   ├── computer.py             # Low-level app/mouse/keyboard/clipboard/volume implementations
│   ├── vision.py                # Camera capture & LLaVA description
│   ├── web_search.py            # Google or DuckDuckGo search
│   ├── file_ops.py              # Low-level file read/write implementations
│   ├── audio_devices.py         # Mic listing - WASAPI-deduped, format-probed
│   ├── notes.py, reminders.py, weather.py, math_helper.py, blender_integration.py
│   └── settings.py
├── PHASE3_HANDOFF.md           # Paste into a new conversation to continue with Phase 3
└── README.md
```

**Adding a new capability going forward** means adding a function to a `tools_*.py` file (or a new file) with an `@tool(...)` decorator — no need to touch the planner or brain.py at all. This is also the pattern Phase 3's plugin loader will extend for drop-in third-party plugins.

## Troubleshooting

**Jarvis stops listening too early, or keeps listening when you're done talking.**
The silence detection (`assistant/stt.py`'s `listen_until_silence`) auto-calibrates against a brief sample of your room's background noise each time it starts listening, then requires audio that much louder to count as "you talking." If it's cutting you off during pauses or picking up background noise as speech, tune `VAD_SILENCE_MULTIPLIER` (raise to make it less sensitive) and `VAD_MIN_ENERGY_THRESHOLD` (raise if a quiet room is still triggering false positives) in `config.py`. `CONVERSATION_SILENCE_TIMEOUT_SECONDS` controls the actual silence duration required (default 5s) — shorten it for snappier turn-taking, lengthen it if you tend to pause mid-thought.

**"Ollama package isn't installed" / import errors, but `pip show ollama` says it's there.**
Almost always a Python version mismatch, not a missing package. Run `python --version` with your venv active — if it's 3.13 or 3.14, that's the problem: some of this project's dependencies (notably `pydantic-core`, which `ollama` needs) don't reliably have prebuilt wheels for those versions yet, and pip can end up with a binary compiled for the wrong Python ABI, which fails silently at import time. Fix: delete `venv/`, recreate it on 3.11 or 3.12 specifically (`py -3.12 -m venv venv`), and reinstall.

**"Could not import the PyAudio C module '_portaudio'."**
PyAudio only ships Windows wheels through Python 3.13. On 3.14 there's nothing for pip to install, even if something under that name shows up elsewhere on your system. Same fix as above — use a 3.11/3.12 venv — or skip voice input entirely and use the text box (everything else works without it).

**`pip list` shows a package installed, but Python still can't import it.**
Usually means you're looking at a different Python than the one actually running the app. Confirm with `python -c "import sys; print(sys.executable)"` while your venv is active — the path it prints should be inside this project's `venv` folder. If it isn't, your venv isn't actually active despite `pip` reporting things as installed elsewhere on your system.

**`playsound` fails to install with `OSError: could not get source code`.**
Known upstream bug in `playsound==1.3.0`'s packaging, unrelated to this project. Install `playsound==1.2.2` instead — it doesn't have the bug. If you'd rather skip it, `assistant/tts.py` automatically falls back to `pygame` or your system's default player.

**Mic dropdown shows a dozen near-identical entries.**
Fixed as of Phase 2 — the list is now filtered to WASAPI devices only (Windows' modern audio API, where each physical mic appears once) and each candidate is checked against the exact recording format Jarvis uses, so non-functional entries get dropped automatically. If you're still seeing duplicates, your system may not expose a WASAPI host API at all (rare) — in that case it falls back to a name-deduped list of everything else.

**Wake word ("Hey Jarvis") doesn't activate.**
Check the chat log right after startup — `wake_word.py` now reports its actual status there ("Wake word ready - listening on X" or a specific error) instead of failing silently. If it reports a download error, check your internet connection (the wake word model file downloads on first use). If it says "ready" but still doesn't trigger, try picking a different microphone from the dropdown and watch for the "listening on ..." message to confirm which device is actually active.


## License
