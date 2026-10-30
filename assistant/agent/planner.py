"""
The planner: agentic tool-calling loop with multi-user isolation.
Host desktop tools (mouse/keyboard/app launching) are disabled so JARVIS runs
purely as an always-on server engine.
"""
from __future__ import annotations

import json
import re
from typing import Optional

import config

from . import registry
# Active capabilities:
from . import tools_web          # noqa: F401
from . import tools_productivity # noqa: F401
from . import tools_memory       # noqa: F401

# Disabled Host Desktop Tools:
# from . import tools_system     # noqa: F401
# from . import tools_files      # noqa: F401
# from . import tools_vision     # noqa: F401
# from . import tools_blender    # noqa: F401

from ..memory import store as memory_store

_HISTORY_SIZE = getattr(config, "CONVERSATION_HISTORY_SIZE", 4)
_STRIP_ROLEPLAY = getattr(config, "STRIP_ROLEPLAY", True)
_MAX_TOOL_ITERATIONS = 6
_KEEP_ALIVE = getattr(config, "OLLAMA_KEEP_ALIVE", "30m")

# Conversation histories & confirmations tracked per user_id
_conversation_histories: dict[str, list[dict]] = {}
_pending_confirmations: dict[str, Optional[dict]] = {}

_AFFIRM_RE = re.compile(r"^\s*(yes|yeah|yep|yup|confirm(ed)?|do it|go ahead|proceed|sure|ok(ay)?)\b", re.I)
_DENY_RE = re.compile(r"^\s*(no|nope|cancel|stop|don'?t|do not|never ?mind)\b", re.I)

_SYSTEM_PROMPT = (
    "You are Jarvis, a cloud-connected AI assistant serving user requests across multiple devices.\n\n"
    "Rules:\n"
    "- Use tools whenever relevant to complete tasks.\n"
    "- Provide clear, concise, direct answers without unnecessary filler or roleplay.\n"
    "- Never use asterisks, *actions*, or emoji. Plain spoken text only.\n"
    "- Maintain distinct context for each user profile (e.g. Henderson, Jenna).\n"
    "- Quietly record long-term facts using persistent memory tools when mentioned."
)


def _sanitize_response(text: str) -> str:
    if not text or not _STRIP_ROLEPLAY:
        return (text or "").strip()
    out = text
    out = re.sub(r"\*\*(.+?)\*\*", r"\1", out)
    out = re.sub(r"\*([^*]+?)\*", r"\1", out)
    out = out.replace("*", "")
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _push_history(user_id: str, role: str, content: str) -> None:
    if _HISTORY_SIZE <= 0:
        return
    if user_id not in _conversation_histories:
        _conversation_histories[user_id] = []
    history = _conversation_histories[user_id]
    history.append({"role": role, "content": content})
    if len(history) > _HISTORY_SIZE * 2:
        _conversation_histories[user_id] = history[-(_HISTORY_SIZE * 2):]


def _execute(name: str, args: dict) -> str:
    t = registry.get_tool(name)
    if t is None:
        return f"Unknown tool: {name}"
    try:
        return str(t.func(**args))
    except TypeError as e:
        return f"Tool '{name}' got bad arguments: {e}"
    except Exception as e:
        return f"Tool '{name}' failed: {e}"


def _run_pending_confirmation(user_message: str, user_id: str) -> Optional[str]:
    pending = _pending_confirmations.get(user_id)
    _pending_confirmations[user_id] = None

    if pending and _AFFIRM_RE.match(user_message):
        result = _execute(pending["tool"], pending["args"])
        reply = _sanitize_response(f"Confirmed. {result}")
        _push_history(user_id, "user", user_message)
        _push_history(user_id, "assistant", reply)
        _log_turn(user_message, [pending["tool"]], reply, user_id)
        return reply

    if pending and _DENY_RE.match(user_message):
        reply = "Cancelled."
        _push_history(user_id, "user", user_message)
        _push_history(user_id, "assistant", reply)
        _log_turn(user_message, [], reply, user_id)
        return reply

    return None


def _log_turn(user_message: str, tool_names: list[str], final_reply: str, user_id: str) -> None:
    try:
        summary = f"[{user_id}] User: {user_message[:150]} | Reply: {final_reply[:150]}"
        memory_store.log_episodic(summary, user_id=user_id)
    except Exception:
        pass


def process(user_message: str, user_id: str = "Henderson") -> str:
    """Processes turn with user_id context (defaults to Henderson)."""
    user_id = user_id.strip() if user_id else "Henderson"
    memory_store.set_current_user(user_id)

    try:
        import ollama
    except ImportError as e:
        return f"Error importing 'ollama': {e}"

    if _pending_confirmations.get(user_id) is not None:
        resolved = _run_pending_confirmation(user_message, user_id)
        if resolved is not None:
            return resolved

    if user_id not in _conversation_histories:
        _conversation_histories[user_id] = []
    history = _conversation_histories[user_id]

    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    try:
        memory_block = memory_store.build_context_block(user_message, user_id=user_id)
    except Exception:
        memory_block = ""
        
    if memory_block:
        messages.append({"role": "system", "content": memory_block})
        
    if _HISTORY_SIZE > 0:
        messages.extend(history[-_HISTORY_SIZE:])
    messages.append({"role": "user", "content": user_message})

    tools_schema = registry.ollama_tool_schemas()
    final_reply = None
    tools_used: list[str] = []

    for _ in range(_MAX_TOOL_ITERATIONS):
        try:
            response = ollama.chat(
                model=config.OLLAMA_CHAT_MODEL,
                messages=messages,
                tools=tools_schema,
                keep_alive=_KEEP_ALIVE,
            )
        except Exception as e:
            final_reply = f"Ollama error: {e}. Ensure Ollama is running."
            break

        msg = response.get("message", {}) if isinstance(response, dict) else dict(response.get("message", {}))
        tool_calls = msg.get("tool_calls") or []

        if not tool_calls:
            final_reply = (msg.get("content") or "").strip()
            break

        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": tool_calls})

        awaiting_confirmation = False
        for call in tool_calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            raw_args = fn.get("arguments", {})
            args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args or {})

            t = registry.get_tool(name)
            if t is not None and t.confirm:
                _pending_confirmations[user_id] = {"tool": name, "args": args}
                final_reply = f"That action ({name}) requires confirmation. Should I proceed? (yes/no)"
                awaiting_confirmation = True
                break

            tools_used.append(name)
            result = _execute(name, args)
            messages.append({"role": "tool", "content": result, "name": name})

        if awaiting_confirmation:
            break
    else:
        final_reply = "Request required too many execution steps."

    if not final_reply:
        final_reply = "Done."

    final_reply = _sanitize_response(final_reply)
    _push_history(user_id, "user", user_message)
    _push_history(user_id, "assistant", final_reply)
    _log_turn(user_message, tools_used, final_reply, user_id)
    return final_reply