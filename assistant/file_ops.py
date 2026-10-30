"""File operations: create, read, append, overwrite, delete files."""
from __future__ import annotations

import os
from typing import Optional

_USERPROFILE = os.environ.get("USERPROFILE", os.path.expanduser("~"))


def _resolve_folder(location: str) -> str:
    """Resolve 'desktop', 'documents', 'downloads' to full path."""
    loc = (location or "").strip().lower()
    if loc in ("desktop", "my desktop"):
        return os.path.join(_USERPROFILE, "Desktop")
    if loc in ("documents", "docs"):
        return os.path.join(_USERPROFILE, "Documents")
    if loc in ("downloads", "download"):
        return os.path.join(_USERPROFILE, "Downloads")
    return os.path.join(_USERPROFILE, "Desktop")


def resolve_path(location: str, filename: str) -> str:
    """
    Resolve a file path. location can be 'desktop', 'documents', 'downloads',
    or a path. filename is the file name. Returns absolute path.
    """
    location = (location or "desktop").strip()
    filename = (filename or "").strip()
    if not filename:
        raise ValueError("Filename is required")
    if os.path.isabs(filename) and os.path.dirname(filename):
        return os.path.normpath(filename)
    base = _resolve_folder(location) if location.lower() in ("desktop", "documents", "downloads", "docs", "download", "my desktop") else os.path.expanduser(location)
    if not os.path.isdir(base):
        base = _resolve_folder("desktop")
    return os.path.normpath(os.path.join(base, filename))


def create_file(path: str, content: str = "") -> str:
    """Create a text file at path with optional content. Overwrites if exists."""
    try:
        path = os.path.normpath(os.path.expanduser(path))
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Created file: {path}"
    except Exception as e:
        return f"Could not create file: {e}"


def read_file(path: str) -> str:
    """Read contents of a text file."""
    try:
        path = os.path.normpath(os.path.expanduser(path))
        if not os.path.isfile(path):
            return f"File not found: {path}"
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"Could not read file: {e}"


def append_to_file(path: str, content: str) -> str:
    """Append text to a file. Creates file if it doesn't exist."""
    try:
        path = os.path.normpath(os.path.expanduser(path))
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
        return f"Appended to {path}"
    except Exception as e:
        return f"Could not append to file: {e}"


def write_file(path: str, content: str) -> str:
    """Overwrite a file with new content."""
    try:
        path = os.path.normpath(os.path.expanduser(path))
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote to {path}"
    except Exception as e:
        return f"Could not write file: {e}"


def delete_file(path: str) -> str:
    """Delete a file."""
    try:
        path = os.path.normpath(os.path.expanduser(path))
        if not os.path.isfile(path):
            return f"File not found: {path}"
        os.remove(path)
        return f"Deleted {path}"
    except Exception as e:
        return f"Could not delete file: {e}"
