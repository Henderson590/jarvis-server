"""
Jarvis-like Local Assistant - Main entry point.
Run with: python main.py
"""
from __future__ import annotations

import os
import warnings

# Suppress CTkLabel HighDPI warning for camera preview (we use PhotoImage for stability)
warnings.filterwarnings("ignore", message=".*Given image is not CTkImage.*", module="customtkinter")
import queue
import threading
from typing import Optional

# Set Ollama host from config before any module imports ollama
import config
os.environ.setdefault("OLLAMA_HOST", config.OLLAMA_HOST)

import customtkinter as ctk
from assistant import brain, stt, tts, wake_word
from assistant import audio_devices, settings
from assistant import vision

# Theme: dark Jarvis-style
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Response queue so TTS and UI updates don't block
response_queue: queue.Queue = queue.Queue()


def append_log(log_widget: ctk.CTkTextbox, line: str, tag: str = "response") -> None:
    def do():
        log_widget.configure(state="normal")
        log_widget.insert("end", line + "\n")
        log_widget.see("end")
        log_widget.configure(state="disabled")
    log_widget.after(0, do)


def process_and_respond(
    user_text: str,
    log_widget: ctk.CTkTextbox,
    tts_engine: Optional[tts.TTS],
    speak: bool,
    status_label: Optional[ctk.CTkLabel] = None,
) -> None:
    if not user_text.strip():
        return
    append_log(log_widget, f"You: {user_text}", "user")
    # Immediate feedback - show executing state before thread starts
    if status_label:
        status_label.configure(text="Executing...", text_color="#06b6d4")

    def run_brain() -> None:
        if status_label:
            log_widget.after(0, lambda: status_label.configure(text="Processing...", text_color="#06b6d4"))
        try:
            reply = brain.process(user_text)
            def done() -> None:
                if status_label:
                    status_label.configure(text="Ready", text_color="#22c55e")
                append_log(log_widget, f"Jarvis: {reply}", "response")
                # Always speak every response when TTS is available (so you hear it without looking)
                if tts_engine and reply:
                    tts_engine.speak(reply, block=False)
            log_widget.after(0, done)
        except Exception as e:
            def err() -> None:
                if status_label:
                    status_label.configure(text="Error", text_color="#ef4444")
                append_log(log_widget, f"Jarvis: Error — {e}", "error")
                if tts_engine:
                    tts_engine.speak(f"Sorry, something went wrong. {e}", block=False)
            log_widget.after(0, err)

    threading.Thread(target=run_brain, daemon=True).start()


def on_wake(log_widget: ctk.CTkTextbox, tts_engine: Optional[tts.TTS], speak: bool, status_label: Optional[ctk.CTkLabel] = None) -> None:
    """Called when wake word is detected: start a conversation session.

    Always conversational now (no toggle) - after each response, it goes
    straight back to listening. A session only ends when you go quiet for
    config.CONVERSATION_SILENCE_TIMEOUT_SECONDS with nothing new to say, at
    which point the wake word is needed again.
    """
    def do():
        append_log(log_widget, "[Wake word detected — listening...]", "system")

        def set_status(text: str, color: str) -> None:
            if status_label:
                log_widget.after(0, lambda: status_label.configure(text=text, text_color=color))

        def conversation_loop() -> None:
            while True:
                set_status("Listening...", "#06b6d4")
                try:
                    wav = stt.listen_until_silence(
                        max_wait_for_speech=config.CONVERSATION_SILENCE_TIMEOUT_SECONDS,
                        silence_duration=config.CONVERSATION_SILENCE_TIMEOUT_SECONDS,
                        max_recording_seconds=config.CONVERSATION_MAX_UTTERANCE_SECONDS,
                    )
                except Exception as e:
                    msg = str(e)
                    log_widget.after(0, lambda m=msg: append_log(log_widget, f"Voice input: {m}", "system"))
                    break

                if not wav:
                    # Either the mic isn't available, or nobody said anything
                    # within the timeout - either way, stop listening.
                    break

                try:
                    text = stt.transcribe_audio_bytes(wav)
                except RuntimeError as e:
                    msg = str(e)
                    log_widget.after(0, lambda m=msg: append_log(log_widget, f"Voice input: {m}", "system"))
                    break

                if not text or not text.strip():
                    # Silence detector triggered on a cough/noise, not real
                    # speech - just keep listening rather than ending the session.
                    continue

                log_widget.after(0, lambda t=text: append_log(log_widget, f"You: {t}", "user"))
                set_status("Processing...", "#06b6d4")
                try:
                    reply = brain.process(text)
                except Exception as e:
                    reply = f"Sorry, something went wrong. {e}"
                    set_status("Error", "#ef4444")

                log_widget.after(0, lambda r=reply: append_log(log_widget, f"Jarvis: {r}", "response"))
                if tts_engine and reply:
                    set_status("Speaking...", "#06b6d4")
                    # block=True is essential here: without it, the loop would
                    # go straight back to listening while Jarvis is still
                    # talking, and the mic would pick up his own voice.
                    tts_engine.speak(reply, block=True)
                # Loop back to listening - this is what makes it "conversational"
                # without needing a toggle.

            set_status("Ready", "#22c55e")
            log_widget.after(
                0, lambda: append_log(log_widget, "[Done listening — say the wake word to talk again.]", "system")
            )

        threading.Thread(target=conversation_loop, daemon=True).start()
    log_widget.after(0, do)


def main() -> None:
    app = ctk.CTk()
    app.title("Jarvis — Command Execution System")
    app.geometry("1000x640")
    app.minsize(800, 520)

    # Refined dark theme - professional, minimal
    bg_dark = "#0a0e17"
    accent = "#06b6d4"
    accent_dim = "#0891b2"
    panel_bg = "#0f172a"
    border_glow = "#1e293b"
    text_primary = "#e2e8f0"
    text_muted = "#94a3b8"
    success = "#22c55e"
    error = "#ef4444"
    app.configure(fg_color=bg_dark)

    # TTS (optional)
    try:
        tts_engine = tts.TTS()
        # Visualizer hooks – these will be bound after vis_bar is created
    except Exception:
        tts_engine = None

    # ==== HEADER / STATUS BAR ====
    header = ctk.CTkFrame(app, fg_color=panel_bg, height=52, corner_radius=0)
    header.pack(fill="x", padx=0, pady=(0, 6))
    header.pack_propagate(False)

    title_label = ctk.CTkLabel(
        header,
        text="JARVIS",
        font=ctk.CTkFont(size=20, weight="bold"),
        text_color=accent,
    )
    title_label.pack(side="left", padx=20)

    subtitle_label = ctk.CTkLabel(
        header,
        text="Direct command execution — zero roleplay",
        font=ctk.CTkFont(size=11),
        text_color=text_muted,
    )
    subtitle_label.pack(side="left", padx=(8, 0))

    # Load saved mic selection (if any) and apply to config in-memory
    saved_mic_index = settings.get("mic_device_index", None)
    if isinstance(saved_mic_index, int):
        config.MIC_DEVICE_INDEX = saved_mic_index
        config.MIC_DEVICE_NAME = ""

    # Mic dropdown (changes wake word mic immediately)
    mic_devices = audio_devices.list_input_devices()
    if mic_devices:
        options = [f"{i}: {name}" for i, name in mic_devices]
    else:
        options = ["(PyAudio mic list unavailable)"]

    mic_var = ctk.StringVar(value=options[0])
    # If a saved index exists, try to select it
    if isinstance(saved_mic_index, int) and mic_devices:
        for i, name in mic_devices:
            if i == saved_mic_index:
                mic_var.set(f"{i}: {name}")
                break

    mic_menu = ctk.CTkOptionMenu(
        header,
        values=options,
        variable=mic_var,
        width=220,
        height=30,
        dynamic_resizing=False,
    )
    mic_menu.pack(side="right", padx=14)

    mic_label = ctk.CTkLabel(header, text="Mic", font=ctk.CTkFont(size=12), text_color=text_muted)
    mic_label.pack(side="right", padx=(0, 8))

    # ==== MAIN BODY: LEFT (CHAT), RIGHT (CAMERA + VISUALIZER) ====
    body = ctk.CTkFrame(app, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=12, pady=(2, 10))

    # Left column: chat log + status + input
    left_col = ctk.CTkFrame(body, fg_color=panel_bg, corner_radius=14, border_width=1, border_color=border_glow)
    left_col.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=0)

    # Chat log
    log = ctk.CTkTextbox(
        left_col,
        font=ctk.CTkFont(family="Consolas", size=13),
        wrap="word",
        state="disabled",
        corner_radius=8,
    )
    log.pack(fill="both", expand=True, padx=14, pady=(12, 6))
    log.configure(text_color=text_primary)
    append_log(
        log,
        "Ready. Type a command or say the wake word. Commands execute immediately with no roleplay.",
        "system",
    )

    # Status row (conversational mode toggle removed - Jarvis is always
    # conversational now: after the wake word or a response, it keeps
    # listening on its own until you go quiet for a few seconds)
    status_row = ctk.CTkFrame(left_col, fg_color="transparent")
    status_row.pack(fill="x", padx=12, pady=(0, 2))

    status_label = ctk.CTkLabel(status_row, text="Ready", font=ctk.CTkFont(size=12), text_color="#22c55e")
    status_label.pack(side="left")

    # Input row
    input_frame = ctk.CTkFrame(left_col, fg_color="transparent")
    input_frame.pack(fill="x", padx=12, pady=(4, 10))

    entry = ctk.CTkEntry(
        input_frame,
        placeholder_text="Command — e.g. Open Notepad, Search for X, Type hello",
        height=42,
        font=ctk.CTkFont(size=14),
        corner_radius=10,
    )
    entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

    def send_text() -> None:
        t = entry.get().strip()
        entry.delete(0, "end")
        if t:
            process_and_respond(t, log, tts_engine, speak=bool(tts_engine), status_label=status_label)

    entry.bind("<Return>", lambda e: send_text())
    entry.bind("<Control-Return>", lambda e: send_text())

    send_btn = ctk.CTkButton(
        input_frame,
        text="Execute",
        width=90,
        height=38,
        command=send_text,
        corner_radius=10,
        fg_color=accent,
        hover_color=accent_dim,
    )
    send_btn.pack(side="right", padx=(0, 10))

    # Right column: camera and visualizer panels
    right_col = ctk.CTkFrame(body, fg_color=panel_bg, corner_radius=14, border_width=1, border_color=border_glow)
    right_col.pack(side="right", fill="both", expand=False, padx=(8, 0), pady=0)

    right_col.grid_rowconfigure(0, weight=3)
    right_col.grid_rowconfigure(1, weight=2)
    right_col.grid_columnconfigure(0, weight=1)

    camera_panel = ctk.CTkFrame(right_col, fg_color="#050b1f", corner_radius=14)
    camera_panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 6))

    visualizer_panel = ctk.CTkFrame(right_col, fg_color="#050918", corner_radius=14)
    visualizer_panel.grid(row=1, column=0, sticky="nsew", padx=10, pady=(6, 10))

    # Camera controls + preview
    cam_header = ctk.CTkFrame(camera_panel, fg_color="transparent")
    cam_header.pack(fill="x", padx=10, pady=(8, 4))

    cam_title = ctk.CTkLabel(
        cam_header,
        text="Camera",
        font=ctk.CTkFont(size=13, weight="bold"),
        text_color=accent,
    )
    cam_title.pack(side="left")

    camera_running = {"on": False}
    _cam_img_ref = {"ctk_img": None}
    _latest_frame = {"frame": None, "lock": threading.Lock()}
    _cap_holder = {"cap": None}  # persistent VideoCapture

    cam_preview = ctk.CTkLabel(
        camera_panel,
        text="Camera offline",
        font=ctk.CTkFont(size=14),
        text_color="#7b8499",
    )
    cam_preview.pack(fill="both", expand=True, padx=10, pady=(0, 6))

    def _camera_capture_thread():
        import cv2
        cap = cv2.VideoCapture(config.CAMERA_INDEX)
        if not cap.isOpened():
            camera_running["on"] = False
            return
        _cap_holder["cap"] = cap
        try:
            while camera_running["on"]:
                ret, frame = cap.read()
                if not ret or frame is None:
                    camera_running["on"] = False
                    break
                with _latest_frame["lock"]:
                    _latest_frame["frame"] = frame
                vision.set_preview_frame(frame)
        except Exception:
            camera_running["on"] = False
        finally:
            cap.release()
            _cap_holder["cap"] = None

    def _update_camera_display():
        if not camera_running["on"]:
            return
        with _latest_frame["lock"]:
            frame = _latest_frame["frame"]
        if frame is None:
            app.after(33, _update_camera_display)
            return
        try:
            img = vision.bgr_to_tk_image(frame, size=(260, 160))
            if img is not None:
                from PIL import ImageTk
                photo = ImageTk.PhotoImage(img)
                _cam_img_ref["ctk_img"] = photo
                cam_preview.configure(image=photo, text="")
        except Exception:
            camera_running["on"] = False
            try:
                cam_preview.configure(image=None, text="Camera unavailable")
            except Exception:
                pass
            return
        app.after(33, _update_camera_display)

    def _start_camera():
        if camera_running["on"]:
            return
        camera_running["on"] = True
        with _latest_frame["lock"]:
            _latest_frame["frame"] = None
        threading.Thread(target=_camera_capture_thread, daemon=True).start()
        app.after(50, _update_camera_display)

    def _stop_camera():
        camera_running["on"] = False
        vision.clear_preview_frame()
        app.after(100, lambda: cam_preview.configure(image=None, text="Camera offline"))

    cam_controls = ctk.CTkFrame(camera_panel, fg_color="transparent")
    cam_controls.pack(fill="x", padx=10, pady=(0, 8))

    cam_start_btn = ctk.CTkButton(cam_controls, text="Start", width=60, command=_start_camera)
    cam_start_btn.pack(side="left", padx=(0, 6))

    cam_stop_btn = ctk.CTkButton(cam_controls, text="Stop", width=60, command=_stop_camera)
    cam_stop_btn.pack(side="left", padx=(0, 6))

    # Multi-bar voice visualizer (smooth spectrum-style)
    vis_label = ctk.CTkLabel(
        visualizer_panel,
        text="Voice",
        font=ctk.CTkFont(size=13),
        text_color="#7b8499",
    )
    vis_label.pack(pady=(10, 4))
    import tkinter as tk
    vis_canvas = tk.Canvas(
        visualizer_panel,
        width=260,
        height=56,
        bg="#050918",
        highlightthickness=0,
    )
    vis_canvas.pack(padx=16, pady=(0, 12))

    NUM_BARS = 14
    BAR_GAP = 4
    BAR_WIDTH = (260 - (NUM_BARS - 1) * BAR_GAP) // NUM_BARS
    BAR_MAX_H = 48
    _vis_state = {"speaking": False, "phase": 0.0, "bar_heights": [0.0] * NUM_BARS}
    _vis_rects = []

    def _draw_visualizer():
        import math
        state = _vis_state
        target = state["bar_heights"]
        if state["speaking"]:
            state["phase"] += 0.25
            for i in range(NUM_BARS):
                t = (state["phase"] + i * 0.4) % (2 * math.pi)
                target[i] = 0.12 + 0.88 * (0.5 + 0.5 * math.sin(t)) * (0.6 + 0.4 * math.sin(i * 0.7 + state["phase"] * 0.5))
        else:
            decay = 0.82
            for i in range(NUM_BARS):
                target[i] *= decay

        for i in range(NUM_BARS):
            h = max(2, int(BAR_MAX_H * target[i]))
            x = 10 + i * (BAR_WIDTH + BAR_GAP)
            y1 = 4 + BAR_MAX_H - h
            y2 = 4 + BAR_MAX_H
            color = accent if state["speaking"] else "#2a4a6a"
            vis_canvas.itemconfig(_vis_rects[i], fill=color, outline=color)
            vis_canvas.coords(_vis_rects[i], x, y1, x + BAR_WIDTH, y2)

        if state["speaking"] or any(t > 0.02 for t in target):
            app.after(36, _draw_visualizer)

    for i in range(NUM_BARS):
        x = 10 + i * (BAR_WIDTH + BAR_GAP)
        r = vis_canvas.create_rectangle(x, BAR_MAX_H, x + BAR_WIDTH, BAR_MAX_H, fill="#1a2a3a", outline="#1a2a3a")
        _vis_rects.append(r)

    if tts_engine:
        def _vis_start() -> None:
            _vis_state["speaking"] = True
            _draw_visualizer()

        def _vis_stop() -> None:
            _vis_state["speaking"] = False

        tts_engine.on_start_speaking = _vis_start
        tts_engine.on_stop_speaking = _vis_stop
        tts_engine.speak("Online sir.", block=False)

    # Wake word controller (so we can restart when mic changes)
    wake_stop = threading.Event()
    wake_thread = None

    def start_wake() -> None:
        nonlocal wake_thread
        wake_stop.clear()

        def _on_wake_status(msg: str) -> None:
            # Called from the wake-word background thread - hand off to the
            # Tkinter main thread instead of touching the widget directly.
            app.after(0, lambda: append_log(log, msg, "system"))

        wake_thread = wake_word.start_wake_word_background(
            lambda: on_wake(log, tts_engine, bool(tts_engine), status_label),
            stop_event=wake_stop,
            on_status=_on_wake_status,
        )

    def restart_wake() -> None:
        wake_stop.set()
        # give the thread a moment to exit its loop
        app.after(250, start_wake)

    # Start wake word - actual readiness/errors are reported by _on_wake_status
    # above as they happen, rather than assumed here.
    try:
        start_wake()
    except Exception as e:
        append_log(log, f"Wake word failed to start: {e}", "system")

    def on_mic_change(_choice: str) -> None:
        choice = mic_var.get()
        # Parse leading index "N: ..."
        try:
            idx_str = choice.split(":", 1)[0].strip()
            idx = int(idx_str)
        except Exception:
            append_log(log, "Could not change mic (invalid selection).", "system")
            return
        config.MIC_DEVICE_INDEX = idx
        config.MIC_DEVICE_NAME = ""
        settings.set("mic_device_index", idx)
        append_log(log, f"Microphone set to device index {idx}. Restarting wake word...", "system")
        restart_wake()

    if mic_devices:
        mic_menu.configure(command=on_mic_change)
    else:
        mic_menu.configure(state="disabled")

    def check_timers() -> None:
        due = brain.check_timers()
        for msg in due:
            append_log(log, f"Jarvis: Timer: {msg}", "response")
            if tts_engine and config.SPEAK_RESPONSES:
                tts_engine.speak(f"Reminder: {msg}", block=False)
        for msg in brain.check_reminders():
            append_log(log, f"Jarvis: Reminder: {msg}", "response")
            if tts_engine and config.SPEAK_RESPONSES:
                tts_engine.speak(f"Reminder: {msg}", block=False)
        app.after(config.TIMER_CHECK_INTERVAL_MS, check_timers)

    app.after(config.TIMER_CHECK_INTERVAL_MS, check_timers)

    def _on_close():
        camera_running["on"] = False
        if tts_engine:
            tts_engine.stop()
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", _on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
