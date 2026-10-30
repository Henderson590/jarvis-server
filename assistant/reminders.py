"""Persisted reminders (saved to JSON, checked on interval)."""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import List, Tuple

import config

_DATA_DIR = (config.DATA_DIR or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).rstrip("/\\")
_REMINDERS_FILE = os.path.join(_DATA_DIR, "jarvis_reminders.json")


def _ensure_dir() -> None:
    if _DATA_DIR and not os.path.isdir(_DATA_DIR):
        try:
            os.makedirs(_DATA_DIR, exist_ok=True)
        except Exception:
            pass


def _load() -> List[dict]:
    try:
        _ensure_dir()
        if os.path.isfile(_REMINDERS_FILE):
            with open(_REMINDERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _save(reminders: List[dict]) -> None:
    _ensure_dir()
    with open(_REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, indent=2)


def add_reminder(when: datetime, message: str) -> str:
    reminders = _load()
    reminders.append({"when": when.isoformat(), "message": message.strip()})
    _save(reminders)
    return f"Reminder set for {when.strftime('%I:%M %p' if when.date() == datetime.now().date() else '%b %d at %I:%M %p')}: {message}."


def check_due() -> List[str]:
    """Return list of reminder messages that are due (and remove them)."""
    now = datetime.now()
    reminders = _load()
    due = []
    keep = []
    for r in reminders:
        try:
            t = datetime.fromisoformat(r["when"])
            if t <= now:
                due.append(r.get("message", "Reminder"))
            else:
                keep.append(r)
        except Exception:
            keep.append(r)
    if due:
        _save(keep)
    return due


def list_upcoming() -> List[Tuple[datetime, str]]:
    """Return list of (when, message) for upcoming reminders."""
    now = datetime.now()
    out = []
    for r in _load():
        try:
            t = datetime.fromisoformat(r["when"])
            if t > now:
                out.append((t, r.get("message", "")))
        except Exception:
            pass
    out.sort(key=lambda x: x[0])
    return out[:10]
