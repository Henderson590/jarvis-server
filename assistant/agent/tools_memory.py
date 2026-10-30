"""Memory tools. The planner also auto-injects relevant memory into the
system prompt every turn (see planner.py) - these tools are how new memory
gets written, plus an explicit recall tool for "what do you know about me"."""
from __future__ import annotations

from ..memory import store
from .registry import tool


@tool(
    "remember_fact",
    "Save a fact about the user for future conversations, e.g. their job, family, "
    "goals, or anything else worth remembering long-term. Use short key/value pairs.",
    parameters={
        "key": {"type": "string", "description": "Short label for the fact, e.g. 'job' or 'hometown'"},
        "value": {"type": "string", "description": "The fact itself"},
    },
    required=["key", "value"],
)
def remember_fact(key: str, value: str) -> str:
    return store.remember_fact(key, value)


@tool(
    "forget_fact",
    "Delete a previously remembered fact. Only use this when the user explicitly asks "
    "to forget or delete something.",
    parameters={"key": {"type": "string", "description": "The key of the fact to forget"}},
    required=["key"],
)
def forget_fact(key: str) -> str:
    return store.forget_fact(key)


@tool(
    "remember_preference",
    "Save a preference, e.g. favorite browser, IDE, music, or website. If the user "
    "mentions a favorite or 'always use X for Y', save it here.",
    parameters={
        "category": {"type": "string", "description": "What kind of preference, e.g. 'browser', 'ide', 'music'"},
        "value": {"type": "string", "description": "The preferred thing"},
    },
    required=["category", "value"],
)
def remember_preference(category: str, value: str) -> str:
    return store.remember_preference(category, value)


@tool(
    "remember_procedure",
    "Save how the user likes a specific task done, e.g. 'when I say send it, use Outlook "
    "not Gmail'. Use this for behavioral rules, not one-off facts.",
    parameters={
        "trigger": {"type": "string", "description": "The situation, e.g. 'I say send it'"},
        "action": {"type": "string", "description": "What to do in that situation"},
    },
    required=["trigger", "action"],
)
def remember_procedure(trigger: str, action: str) -> str:
    return store.remember_procedure(trigger, action)


@tool(
    "list_what_you_know",
    "List everything currently remembered about the user - facts, preferences, and habits. "
    "Use this when the user asks what you know or remember about them.",
)
def list_what_you_know() -> str:
    return store.summarize_all()
