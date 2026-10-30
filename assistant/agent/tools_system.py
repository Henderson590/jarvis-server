"""Desktop control tools: apps, keyboard, mouse, clipboard, volume, screenshots."""
from __future__ import annotations

from .. import audio_devices, computer
from .registry import tool


@tool(
    "open_app",
    "Launch a desktop application by name, e.g. 'notepad', 'chrome', 'spotify'.",
    parameters={"name": {"type": "string", "description": "Application name or path"}},
    required=["name"],
)
def open_app(name: str) -> str:
    return computer.open_app(name)


@tool(
    "type_text",
    "Type text at the current cursor/focus location, as if typed on the keyboard.",
    parameters={"text": {"type": "string", "description": "Text to type"}},
    required=["text"],
)
def type_text(text: str) -> str:
    return computer.type_text(text)


@tool(
    "press_key",
    "Press a single keyboard key or shortcut, e.g. 'enter', 'escape', 'ctrl+c', 'alt+tab'.",
    parameters={"key_name": {"type": "string", "description": "Key or shortcut name"}},
    required=["key_name"],
)
def press_key(key_name: str) -> str:
    return computer.press_key(key_name)


@tool(
    "mouse_move",
    "Move the mouse cursor to absolute screen coordinates, or by a relative offset.",
    parameters={
        "x": {"type": "integer", "description": "Target X coordinate"},
        "y": {"type": "integer", "description": "Target Y coordinate"},
        "relative": {"type": "boolean", "description": "If true, x/y are offsets from current position"},
    },
    required=["x", "y"],
)
def mouse_move(x: int, y: int, relative: bool = False) -> str:
    return computer.mouse_move(x=x, y=y, relative=relative)


@tool(
    "mouse_click",
    "Click the mouse at its current position.",
    parameters={
        "button": {"type": "string", "description": "'left', 'right', or 'middle'", "enum": ["left", "right", "middle"]},
        "clicks": {"type": "integer", "description": "Number of clicks (2 for double-click)"},
    },
)
def mouse_click(button: str = "left", clicks: int = 1) -> str:
    return computer.mouse_click(button=button, clicks=clicks)


@tool(
    "click_on_screen",
    "Find something on screen by visual description (e.g. 'the Save button', 'the search box') "
    "and click it. Uses a screenshot + vision model to locate it. Slower than mouse_click - only "
    "use this when you don't already know exact coordinates.",
    parameters={"target": {"type": "string", "description": "Visual description of what to click"}},
    required=["target"],
)
def click_on_screen(target: str) -> str:
    return computer.click_on_screen(target)


@tool(
    "mouse_scroll",
    "Scroll the mouse wheel up or down.",
    parameters={"delta": {"type": "integer", "description": "Positive scrolls up, negative scrolls down"}},
    required=["delta"],
)
def mouse_scroll(delta: int) -> str:
    return computer.mouse_scroll(delta)


@tool(
    "take_screenshot",
    "Capture a screenshot of the screen and save it to disk.",
    parameters={"save_path": {"type": "string", "description": "Optional file path to save to"}},
)
def take_screenshot(save_path: str = "") -> str:
    return computer.take_screenshot(save_path or None)


@tool("get_system_info", "Get CPU, memory, and disk usage stats for this PC.")
def get_system_info() -> str:
    return computer.get_system_info()


@tool("get_clipboard", "Read the current text on the clipboard.")
def get_clipboard() -> str:
    return computer.get_clipboard()


@tool(
    "set_clipboard",
    "Copy text to the clipboard.",
    parameters={"text": {"type": "string", "description": "Text to copy"}},
    required=["text"],
)
def set_clipboard(text: str) -> str:
    return computer.set_clipboard(text)


@tool(
    "lock_pc",
    "Lock the computer immediately, ending this session until the user logs back in.",
    confirm=True,
)
def lock_pc() -> str:
    return computer.lock_pc()


@tool(
    "adjust_volume",
    "Change the system volume: turn it up, down, mute it, or set an exact percentage.",
    parameters={
        "action": {"type": "string", "enum": ["up", "down", "mute", "set"], "description": "Which volume action"},
        "percent": {"type": "integer", "description": "Target percent (0-100), only used when action is 'set'"},
    },
    required=["action"],
)
def adjust_volume(action: str, percent: int = 50) -> str:
    action = (action or "").lower()
    if action == "up":
        return computer.volume_up()
    if action == "down":
        return computer.volume_down()
    if action == "mute":
        return computer.volume_mute()
    if action == "set":
        return computer.set_volume_percent(percent)
    return f"Unknown volume action: {action}"


@tool("list_microphones", "List available microphone input devices and their index numbers.")
def list_microphones() -> str:
    devices = audio_devices.list_input_devices()
    if not devices:
        return "No microphones found."
    return "\n".join(f"[{idx}] {name}" for idx, name in devices)
