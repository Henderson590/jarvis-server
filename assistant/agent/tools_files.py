"""File and folder tools. Files are located by a folder shortcut ('desktop',
'documents', 'downloads') plus a filename, or a full path - file_ops.resolve_path
handles both."""
from __future__ import annotations

from .. import computer, file_ops
from .registry import tool

_LOCATION_DESC = (
    "Folder: 'desktop', 'documents', 'downloads', or a full folder path. "
    "Defaults to desktop if omitted."
)


@tool(
    "list_folder",
    "List the files and subfolders inside a folder.",
    parameters={"folder": {"type": "string", "description": _LOCATION_DESC}},
)
def list_folder(folder: str = "") -> str:
    return computer.list_directory(folder)


@tool(
    "create_folder",
    "Create a new folder/directory.",
    parameters={"path": {"type": "string", "description": "Folder path to create"}},
    required=["path"],
)
def create_folder(path: str) -> str:
    return computer.create_folder(path)


@tool(
    "open_folder",
    "Open a folder in File Explorer.",
    parameters={"path": {"type": "string", "description": _LOCATION_DESC}},
    required=["path"],
)
def open_folder(path: str) -> str:
    return computer.open_folder(path)


@tool(
    "create_file",
    "Create a new text file with content, overwriting if it already exists.",
    parameters={
        "location": {"type": "string", "description": _LOCATION_DESC},
        "filename": {"type": "string", "description": "File name, e.g. 'notes.txt'"},
        "content": {"type": "string", "description": "Text content to write"},
    },
    required=["filename"],
)
def create_file(filename: str, location: str = "desktop", content: str = "") -> str:
    path = file_ops.resolve_path(location, filename)
    return file_ops.create_file(path, content)


@tool(
    "read_file",
    "Read and return the text contents of a file.",
    parameters={
        "location": {"type": "string", "description": _LOCATION_DESC},
        "filename": {"type": "string", "description": "File name to read"},
    },
    required=["filename"],
)
def read_file(filename: str, location: str = "desktop") -> str:
    path = file_ops.resolve_path(location, filename)
    return file_ops.read_file(path)


@tool(
    "append_to_file",
    "Append text to the end of an existing file (creates it if missing).",
    parameters={
        "location": {"type": "string", "description": _LOCATION_DESC},
        "filename": {"type": "string", "description": "File name"},
        "content": {"type": "string", "description": "Text to append"},
    },
    required=["filename", "content"],
)
def append_to_file(filename: str, content: str, location: str = "desktop") -> str:
    path = file_ops.resolve_path(location, filename)
    return file_ops.append_to_file(path, content)


@tool(
    "overwrite_file",
    "Replace the entire contents of an existing file with new text.",
    parameters={
        "location": {"type": "string", "description": _LOCATION_DESC},
        "filename": {"type": "string", "description": "File name"},
        "content": {"type": "string", "description": "New text content"},
    },
    required=["filename", "content"],
)
def overwrite_file(filename: str, content: str, location: str = "desktop") -> str:
    path = file_ops.resolve_path(location, filename)
    return file_ops.write_file(path, content)


@tool(
    "delete_file",
    "Permanently delete a file. Destructive and cannot be undone.",
    parameters={
        "location": {"type": "string", "description": _LOCATION_DESC},
        "filename": {"type": "string", "description": "File name to delete"},
    },
    required=["filename"],
    confirm=True,
)
def delete_file(filename: str, location: str = "desktop") -> str:
    path = file_ops.resolve_path(location, filename)
    return file_ops.delete_file(path)
