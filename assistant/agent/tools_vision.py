"""Vision tools: camera and screen understanding via the local vision model."""
from __future__ import annotations

from .. import vision
from .registry import tool


@tool(
    "look_at_camera",
    "Look through the webcam and describe what's visible, or answer a specific question "
    "about what the camera sees.",
    parameters={"question": {"type": "string", "description": "Optional specific question about the camera view"}},
)
def look_at_camera(question: str = "") -> str:
    return vision.what_do_you_see(question=question or None)


@tool(
    "look_at_screen",
    "Take a screenshot and describe what's on screen, or answer a specific question about it.",
    parameters={"question": {"type": "string", "description": "Optional specific question about the screen"}},
)
def look_at_screen(question: str = "") -> str:
    return vision.describe_screen(question=question or None)


@tool("count_fingers", "Look at the webcam and count how many fingers are held up.")
def count_fingers() -> str:
    result = vision.describe_hand_gesture()
    return result
