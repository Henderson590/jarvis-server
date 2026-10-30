"""
CRUD and retrieval for Jarvis's memory with multi-user isolation.
Supports distinct contexts for Henderson, Jenna, or other users.
"""
from __future__ import annotations

import contextvars
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

from . import db

_MAX_EPISODIC_EVENTS = 500  # oldest events get pruned past this
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "to", "of", "and", "or",
    "in", "on", "at", "for", "with", "my", "me", "i", "you", "your", "it",
    "that", "this", "do", "does", "did", "can", "could", "please", "what",
    "when", "how", "should", "would", "will", "want", "need",
}

# Thread-safe context tracker for the active user during a turn
_current_user_var: contextvars.ContextVar[str] = contextvars.ContextVar("current_user_id", default="Henderson")


def set_current_user(user_id: str) -> None:
    _current_user_var.set(user_id or "Henderson")


def get_current_user() -> str:
    return _current_user_var.get() or "Henderson"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _words(text: str) -> set:
    tokens = re.findall(r"[a-z0-9']+", (text or "").lower())
    return {t for t in tokens if t not in _STOPWORDS and len(t) > 1}


# --------------------------------------------------------------------------
# Semantic facts
# --------------------------------------------------------------------------

def remember_fact(key: str, value: str, confidence: float = 1.0, user_id: Optional[str] = None) -> str:
    uid = user_id or get_current_user()
    key = key.strip()
    value = value.strip()
    now = _now()
    conn = db.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO semantic_facts (user_id, key, value, confidence, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, key) DO UPDATE SET
                value = excluded.value,
                confidence = excluded.confidence,
                updated_at = excluded.updated_at
            """,
            (uid, key, value, confidence, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    return f"Remembered for {uid}: {key} = {value}"


def forget_fact(key: str, user_id: Optional[str] = None) -> str:
    uid = user_id or get_current_user()
    conn = db.get_connection()
    try:
        cur = conn.execute("DELETE FROM semantic_facts WHERE user_id = ? AND key = ?", (uid, key.strip()))
        conn.commit()
        return f"Forgot '{key}' for {uid}." if cur.rowcount else f"No fact stored for '{key}' under {uid}."
    finally:
        conn.close()


def get_relevant_facts(query: str, limit: int = 6, user_id: Optional[str] = None) -> List[str]:
    uid = user_id or get_current_user()
    conn = db.get_connection()
    try:
        rows = conn.execute(
            "SELECT key, value FROM semantic_facts WHERE user_id = ? ORDER BY updated_at DESC", (uid,)
        ).fetchall()
    finally:
        conn.close()
    query_words = _words(query)
    scored = []
    for row in rows:
        text_words = _words(f"{row['key']} {row['value']}")
        score = len(query_words & text_words)
        scored.append((score, row["key"], row["value"]))
    scored.sort(key=lambda t: t[0], reverse=True)
    top = [t for t in scored if t[0] > 0][:limit]
    if not top:
        top = scored[:min(3, limit)]
    return [f"{k}: {v}" for _, k, v in top]


# --------------------------------------------------------------------------
# Preferences
# --------------------------------------------------------------------------

def remember_preference(category: str, value: str, user_id: Optional[str] = None) -> str:
    uid = user_id or get_current_user()
    category = category.strip().lower()
    value = value.strip()
    now = _now()
    conn = db.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO preferences (user_id, category, value, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, category) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (uid, category, value, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    return f"Noted preference for {uid} - {category}: {value}"


def get_preference(category: str, user_id: Optional[str] = None) -> Optional[str]:
    uid = user_id or get_current_user()
    conn = db.get_connection()
    try:
        row = conn.execute(
            "SELECT value FROM preferences WHERE user_id = ? AND category = ?", (uid, category.strip().lower())
        ).fetchone()
        return row["value"] if row else None
    finally:
        conn.close()


def get_all_preferences(user_id: Optional[str] = None) -> Dict[str, str]:
    uid = user_id or get_current_user()
    conn = db.get_connection()
    try:
        rows = conn.execute(
            "SELECT category, value FROM preferences WHERE user_id = ? ORDER BY category", (uid,)
        ).fetchall()
        return {row["category"]: row["value"] for row in rows}
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Procedural rules
# --------------------------------------------------------------------------

def remember_procedure(trigger: str, action: str, user_id: Optional[str] = None) -> str:
    uid = user_id or get_current_user()
    now = _now()
    conn = db.get_connection()
    try:
        conn.execute(
            "INSERT INTO procedural_rules (user_id, trigger, action, created_at) VALUES (?, ?, ?, ?)",
            (uid, trigger.strip(), action.strip(), now),
        )
        conn.commit()
    finally:
        conn.close()
    return f"Noted rule for {uid} - when {trigger}, {action}."


def get_relevant_procedures(query: str, limit: int = 4, user_id: Optional[str] = None) -> List[str]:
    uid = user_id or get_current_user()
    conn = db.get_connection()
    try:
        rows = conn.execute(
            "SELECT trigger, action FROM procedural_rules WHERE user_id = ? ORDER BY created_at DESC", (uid,)
        ).fetchall()
    finally:
        conn.close()
    query_words = _words(query)
    scored = []
    for row in rows:
        text_words = _words(f"{row['trigger']} {row['action']}")
        score = len(query_words & text_words)
        scored.append((score, row["trigger"], row["action"]))
    scored.sort(key=lambda t: t[0], reverse=True)
    top = [t for t in scored if t[0] > 0][:limit]
    return [f"When {trig}: {act}" for _, trig, act in top]


# --------------------------------------------------------------------------
# Episodic events
# --------------------------------------------------------------------------

def log_episodic(summary: str, user_id: Optional[str] = None) -> None:
    uid = user_id or get_current_user()
    now = _now()
    conn = db.get_connection()
    try:
        conn.execute(
            "INSERT INTO episodic_events (user_id, summary, created_at) VALUES (?, ?, ?)",
            (uid, summary.strip()[:500], now),
        )
        conn.execute(
            """
            DELETE FROM episodic_events WHERE user_id = ? AND id NOT IN (
                SELECT id FROM episodic_events WHERE user_id = ? ORDER BY id DESC LIMIT ?
            )
            """,
            (uid, uid, _MAX_EPISODIC_EVENTS),
        )
        conn.commit()
    finally:
        conn.close()


def get_recent_episodic(limit: int = 4, user_id: Optional[str] = None) -> List[str]:
    uid = user_id or get_current_user()
    conn = db.get_connection()
    try:
        rows = conn.execute(
            "SELECT summary FROM episodic_events WHERE user_id = ? ORDER BY id DESC LIMIT ?", (uid, limit)
        ).fetchall()
        return [row["summary"] for row in rows]
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Context building
# --------------------------------------------------------------------------

def build_context_block(user_message: str, user_id: Optional[str] = None) -> str:
    uid = user_id or get_current_user()
    facts = get_relevant_facts(user_message, limit=6, user_id=uid)
    prefs = get_all_preferences(user_id=uid)
    procs = get_relevant_procedures(user_message, limit=4, user_id=uid)
    recent = get_recent_episodic(limit=4, user_id=uid)

    sections = []
    if facts:
        sections.append(f"Known facts about {uid}:\n" + "\n".join(f"- {f}" for f in facts))
    if prefs:
        pref_lines = "\n".join(f"- {cat}: {val}" for cat, val in prefs.items())
        sections.append(f"Stated preferences for {uid}:\n" + pref_lines)
    if procs:
        sections.append(f"How {uid} likes certain tasks done:\n" + "\n".join(f"- {p}" for p in procs))
    if recent:
        sections.append(f"Recent turns with {uid}:\n" + "\n".join(f"- {r}" for r in recent))

    if not sections:
        return f"User identified as: {uid}."
    return f"User profile active: {uid}\n\n" + "\n\n".join(sections)


def summarize_all(user_id: Optional[str] = None) -> str:
    uid = user_id or get_current_user()
    conn = db.get_connection()
    try:
        facts = conn.execute("SELECT key, value FROM semantic_facts WHERE user_id = ? ORDER BY updated_at DESC", (uid,)).fetchall()
        procs = conn.execute("SELECT trigger, action FROM procedural_rules WHERE user_id = ? ORDER BY created_at DESC", (uid,)).fetchall()
    finally:
        conn.close()
    prefs = get_all_preferences(user_id=uid)

    lines = [f"Memory stored for {uid}:"]
    if facts:
        lines.append("Facts:")
        lines.extend(f"  - {r['key']}: {r['value']}" for r in facts)
    if prefs:
        lines.append("Preferences:")
        lines.extend(f"  - {cat}: {val}" for cat, val in prefs.items())
    if procs:
        lines.append("Habits/rules:")
        lines.extend(f"  - When {r['trigger']}: {r['action']}" for r in procs)
    if len(lines) == 1:
        return f"No memories stored yet for {uid}."
    return "\n".join(lines)