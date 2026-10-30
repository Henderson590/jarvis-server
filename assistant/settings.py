"""Small persisted settings store (JSON) for UI selections like microphone."""
from __future__ import annotations

import json
import os
from typing import Any, Dict

import config


def _data_dir() -> str:
    base = (getattr(config, "DATA_DIR", "") or "").strip()
    if base:
        return os.path.normpath(base)
    # Default: project root (same folder as main.py)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _path() -> str:
    return os.path.join(_data_dir(), "jarvis_settings.json")


def load() -> Dict[str, Any]:
    try:
        p = _path()
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save(data: Dict[str, Any]) -> None:
    try:
        os.makedirs(_data_dir(), exist_ok=True)
        with open(_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def get(key: str, default: Any = None) -> Any:
    return load().get(key, default)


def set(key: str, value: Any) -> None:
    data = load()
    data[key] = value
    save(data)

