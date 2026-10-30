"""SQLite connection + schema for Jarvis's persistent memory.

One local file, no external services - stays consistent with the
local-first/free-only requirement. Lives next to jarvis_settings.json,
in DATA_DIR if set, otherwise the project root.
"""
from __future__ import annotations

import os
import sqlite3

import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS semantic_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'Henderson',
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, key)
);

CREATE TABLE IF NOT EXISTS preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'Henderson',
    category TEXT NOT NULL,
    value TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, category)
);

CREATE TABLE IF NOT EXISTS procedural_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'Henderson',
    trigger TEXT NOT NULL,
    action TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS episodic_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'Henderson',
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _data_dir() -> str:
    base = (getattr(config, "DATA_DIR", "") or "").strip()
    if base:
        return os.path.normpath(base)
    here = os.path.dirname(os.path.abspath(__file__))          # .../assistant/memory
    assistant_dir = os.path.dirname(here)                       # .../assistant
    return os.path.dirname(assistant_dir)                       # project root


def _db_path() -> str:
    return os.path.join(_data_dir(), "jarvis_memory.db")


def _migrate_from_old_location(correct_path: str) -> None:
    if os.path.exists(correct_path):
        return
    here = os.path.dirname(os.path.abspath(__file__))
    old_path = os.path.join(os.path.dirname(here), "jarvis_memory.db")
    if os.path.exists(old_path):
        try:
            os.replace(old_path, correct_path)
        except Exception:
            pass


def get_connection() -> sqlite3.Connection:
    os.makedirs(_data_dir(), exist_ok=True)
    db_path = _db_path()
    _migrate_from_old_location(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn