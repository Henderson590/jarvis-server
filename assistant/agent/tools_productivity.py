"""Productivity tools: todos, notes, timers, reminders, weather, math, date/time.

Timers are in-memory only (lost on restart, which is fine for a "ring in 5
minutes" style timer). Reminders are persisted to disk via assistant.reminders.
Both are polled by main.py's timer-check loop through check_timers_due() /
assistant.reminders.check_due(), same as before Phase 1.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta

from .. import math_helper, notes, reminders, weather
from .registry import tool

import os
import requests

_UNIT_SECONDS = {"second": 1, "seconds": 1, "minute": 60, "minutes": 60, "hour": 3600, "hours": 3600}

# id -> (end_epoch_seconds, message)
_timers: dict[int, tuple[float, str]] = {}
_next_timer_id = 0


def _to_seconds(amount: int, unit: str) -> int:
    return int(amount) * _UNIT_SECONDS.get((unit or "minutes").lower(), 60)


def check_timers_due() -> list[str]:
    """Called by the planner's check_timers(); not itself an LLM tool."""
    now = time.time()
    due, expired_ids = [], []
    for tid, (end, msg) in _timers.items():
        if now >= end:
            due.append(msg)
            expired_ids.append(tid)
    for tid in expired_ids:
        del _timers[tid]
    return due


@tool(
    "set_timer",
    "Set a countdown timer that will announce a message when it finishes.",
    parameters={
        "amount": {"type": "integer", "description": "How many units from now"},
        "unit": {"type": "string", "enum": ["seconds", "minutes", "hours"], "description": "Time unit"},
        "message": {"type": "string", "description": "What to announce when the timer is done"},
    },
    required=["amount", "unit"],
)
def set_timer(amount: int, unit: str = "minutes", message: str = "Timer's up.") -> str:
    global _next_timer_id
    seconds = _to_seconds(amount, unit)
    _next_timer_id += 1
    _timers[_next_timer_id] = (time.time() + seconds, message)
    return f"Timer set for {amount} {unit}."


@tool(
    "set_reminder",
    "Set a reminder that persists across restarts and will announce a message at a future time.",
    parameters={
        "amount": {"type": "integer", "description": "How many units from now"},
        "unit": {"type": "string", "enum": ["seconds", "minutes", "hours"], "description": "Time unit"},
        "message": {"type": "string", "description": "What to be reminded of"},
    },
    required=["amount", "unit", "message"],
)
def set_reminder(amount: int, unit: str, message: str) -> str:
    seconds = _to_seconds(amount, unit)
    when = datetime.now() + timedelta(seconds=seconds)
    return reminders.add_reminder(when, message)


@tool("list_reminders", "List upcoming reminders that haven't fired yet.")
def list_reminders() -> str:
    upcoming = reminders.list_upcoming()
    if not upcoming:
        return "No upcoming reminders."
    return "\n".join(f"{when.strftime('%Y-%m-%d %H:%M')}: {msg}" for when, msg in upcoming)


@tool(
    "add_todo",
    "Add an item to the to-do list.",
    parameters={"item": {"type": "string", "description": "Item to add"}},
    required=["item"],
)
def add_todo(item: str) -> str:
    return notes.add_todo(item)


@tool("list_todos", "List everything currently on the to-do list.")
def list_todos() -> str:
    items = notes.get_todos()
    if not items:
        return "The to-do list is empty."
    return "\n".join(f"{i+1}. {t}" for i, t in enumerate(items))


@tool("clear_todos", "Remove everything from the to-do list.", confirm=True)
def clear_todos() -> str:
    return notes.clear_todos()


@tool(
    "add_note",
    "Save a free-form note for later.",
    parameters={"note": {"type": "string", "description": "Note text"}},
    required=["note"],
)
def add_note(note: str) -> str:
    return notes.add_note(note)


@tool("list_notes", "List saved notes.")
def list_notes() -> str:
    return notes.list_notes_summary()


@tool(
    "get_weather",
    "Get the current weather for a city or zip code.",
    parameters={"city_or_zip": {"type": "string", "description": "City name or zip code. Omit for the default location."}},
)
def get_weather(city_or_zip: str = "") -> str:
    return weather.get_weather(city_or_zip or None)


@tool(
    "calculate",
    "Evaluate a math expression and return the result.",
    parameters={"expression": {"type": "string", "description": "Math expression, e.g. '12 * (4 + 3)'"}},
    required=["expression"],
)
def calculate(expression: str) -> str:
    result = math_helper.safe_calculate(expression)
    if result is None:
        return f"Could not evaluate: {expression}"
    return str(result)


@tool("get_current_datetime", "Get the current date and time.")
def get_current_datetime() -> str:
    return datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")

@tool(
    "call_user_phone",
    "Make an outbound phone call to the user's phone to deliver an urgent message or reminder.",
    parameters={
        "message": {"type": "string", "description": "The spoken message to read to the user over the phone."}
    },
    required=["message"]
)
def call_user_phone(message: str) -> str:
    user_phone = os.environ.get("USER_PHONE_NUMBER", "")
    if not user_phone:
        return "Cannot make call: USER_PHONE_NUMBER not set in environment."
    try:
        # Call back into local FastAPI server endpoint
        res = requests.post(
            "http://127.0.0.1:8000/api/voice/call-me",
            json={"message": message, "target_phone_number": user_phone},
            timeout=10
        )
        if res.status_code == 200:
            return f"Initiated outbound call to user: '{message}'"
        return f"Call failed: {res.text}"
    except Exception as e:
        return f"Error triggering outbound call: {e}"
    