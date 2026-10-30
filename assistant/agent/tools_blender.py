"""Blender integration: turns a natural-language scene description into a simple
primitive layout and opens it in Blender. This is intentionally basic for now -
mesh repair, manifold checks, and STL export are Phase 8 work."""
from __future__ import annotations

import json
import re

import config
from .. import blender_integration
from .registry import tool

_SPEC_PROMPT = (
    "Convert this 3D scene request into JSON only, no other text. Format:\n"
    '{"objects": [{"type": "cube"|"sphere"|"plane", "location": [x,y,z], "scale": [x,y,z]}]}\n'
    "Use reasonable coordinates so objects don't overlap. Request: "
)


def _spec_from_description(description: str) -> dict:
    try:
        import ollama
        response = ollama.chat(
            model=config.OLLAMA_CHAT_MODEL,
            messages=[{"role": "user", "content": _SPEC_PROMPT + description}],
            keep_alive=getattr(config, "OLLAMA_KEEP_ALIVE", "30m"),
        )
        text = (response.get("message", {}).get("content") or "").strip()
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            return json.loads(match.group(0))
    except Exception:
        pass
    # Fallback: a single cube, so the tool always produces something.
    return {"objects": [{"type": "cube", "location": [0, 0, 0], "scale": [1, 1, 1]}]}


@tool(
    "create_3d_scene",
    "Generate a simple 3D scene (made of cubes, spheres, and planes) from a description "
    "and open it in Blender.",
    parameters={"description": {"type": "string", "description": "What to build, e.g. 'a small table with four legs'"}},
    required=["description"],
)
def create_3d_scene(description: str) -> str:
    spec = _spec_from_description(description)
    return blender_integration.open_simple_scene(spec)
