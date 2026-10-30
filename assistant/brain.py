"""
Compatibility shim delegating requests to assistant/agent/planner.py.
"""
from __future__ import annotations

from . import reminders
from .agent import planner


def process(user_message: str, user_id: str = "Henderson") -> str:
    return planner.process(user_message, user_id=user_id)


def check_timers() -> list[str]:
    from .agent import tools_productivity
    return tools_productivity.check_timers_due()


def check_reminders() -> list[str]:
    try:
        return reminders.check_due()
    except Exception:
        return []