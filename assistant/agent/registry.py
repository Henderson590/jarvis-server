"""
Tool registry for the agent core.

Any module that wants to expose a capability to the planner defines a plain
Python function and decorates it with @tool(...). That's the entire plugin
contract for built-in tools: register a function, describe its parameters in
JSON-schema form, and the planner can call it. This is also the pattern
Phase 3's external plugin loader will reuse for third-party plugins.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class Tool:
    name: str
    description: str
    func: Callable[..., str]
    parameters: dict = field(default_factory=dict)   # JSON-schema "properties"
    required: list = field(default_factory=list)      # required property names
    confirm: bool = False                              # ask user before running

    def to_ollama_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required,
                },
            },
        }


_REGISTRY: dict[str, Tool] = {}


def tool(
    name: str,
    description: str,
    parameters: Optional[dict] = None,
    required: Optional[list] = None,
    confirm: bool = False,
):
    """
    Decorator that registers a function as a tool the planner can call.

    parameters: JSON-schema "properties" dict, e.g.
        {"city": {"type": "string", "description": "City name or zip code"}}
    required: list of property names the model must always provide.
    confirm: if True, the planner will ask the user to confirm before running
        this tool (use for purchases, deletions, or anything hard to undo).
    """
    def decorator(func: Callable[..., str]) -> Callable[..., str]:
        if name in _REGISTRY:
            raise ValueError(f"Tool '{name}' is already registered (duplicate name).")
        _REGISTRY[name] = Tool(
            name=name,
            description=description,
            func=func,
            parameters=parameters or {},
            required=required or [],
            confirm=confirm,
        )
        return func
    return decorator


def get_tool(name: str) -> Optional[Tool]:
    return _REGISTRY.get(name)


def all_tools() -> list[Tool]:
    return list(_REGISTRY.values())


def ollama_tool_schemas() -> list[dict]:
    return [t.to_ollama_schema() for t in _REGISTRY.values()]


def clear_registry() -> None:
    """Only for tests - wipes registered tools."""
    _REGISTRY.clear()
