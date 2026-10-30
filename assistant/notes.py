"""Notes and todo list — persisted to JSON."""
from __future__ import annotations

import json
import os
from typing import List

import config

_DATA_DIR = (config.DATA_DIR or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).rstrip("/\\")
_TODOS_FILE = os.path.join(_DATA_DIR, "jarvis_todos.json")
_NOTES_FILE = os.path.join(_DATA_DIR, "jarvis_notes.json")


def _ensure_dir() -> None:
    if _DATA_DIR and not os.path.isdir(_DATA_DIR):
        try:
            os.makedirs(_DATA_DIR, exist_ok=True)
        except Exception:
            pass


def get_todos() -> List[str]:
    try:
        _ensure_dir()
        if os.path.isfile(_TODOS_FILE):
            with open(_TODOS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def add_todo(item: str) -> str:
    todos = get_todos()
    todos.append(item.strip())
    try:
        _ensure_dir()
        with open(_TODOS_FILE, "w", encoding="utf-8") as f:
            json.dump(todos, f, indent=2)
        return f"Added \"{item.strip()}\" to your list."
    except Exception as e:
        return f"Could not save: {e}"


def clear_todos() -> str:
    try:
        if os.path.isfile(_TODOS_FILE):
            os.remove(_TODOS_FILE)
        return "Your to-do list is cleared."
    except Exception as e:
        return f"Could not clear: {e}"


def remove_todo(index: int) -> str:
    todos = get_todos()
    if 1 <= index <= len(todos):
        removed = todos.pop(index - 1)
        try:
            with open(_TODOS_FILE, "w", encoding="utf-8") as f:
                json.dump(todos, f, indent=2)
            return f"Removed: {removed}."
        except Exception as e:
            return f"Could not save: {e}"
    return "No such item number."


def get_notes() -> List[str]:
    try:
        _ensure_dir()
        if os.path.isfile(_NOTES_FILE):
            with open(_NOTES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def add_note(note: str) -> str:
    notes = get_notes()
    notes.append(note.strip())
    try:
        _ensure_dir()
        with open(_NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(notes, f, indent=2)
        return "Note saved."
    except Exception as e:
        return f"Could not save note: {e}"


def list_notes_summary() -> str:
    notes = get_notes()
    if not notes:
        return "You have no notes."
    lines = [f"You have {len(notes)} note(s):"]
    for i, n in enumerate(notes[-10:], 1):
        preview = (n[:60] + "…") if len(n) > 60 else n
        lines.append(f"  {i}. {preview}")
    return "\n".join(lines)
