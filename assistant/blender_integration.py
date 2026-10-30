from __future__ import annotations

import json
import os
import subprocess
import tempfile
from typing import Any, Dict

import config


def _blender_executable() -> str:
    """
    Resolve Blender executable path from config or PATH.
    """
    path = getattr(config, "BLENDER_PATH", "") or ""
    if path and os.path.isfile(path):
        return path
    return "blender"


def open_simple_scene(spec: Dict[str, Any]) -> str:
    """
    Create a simple 3D scene in Blender based on a structured spec and open it.

    Spec example:
    {
      "objects": [
        {"type": "cube", "location": [0,0,0], "scale": [1,1,1]},
        {"type": "sphere", "location": [2,0,0], "scale": [0.5,0.5,0.5]}
      ]
    }
    """
    try:
        exe = _blender_executable()
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as script:
            script_path = script.name
            script.write("import bpy\n")
            script.write("import json\n")
            script.write("spec = json.loads(r'''")
            script.write(json.dumps(spec))
            script.write("''')\n")
            script.write(
                "for obj in list(bpy.data.objects):\n"
                "    if obj.type in {'MESH','LIGHT','CAMERA'}:\n"
                "        bpy.data.objects.remove(obj, do_unlink=True)\n"
            )
            script.write(
                "for desc in spec.get('objects', []):\n"
                "    t = (desc.get('type') or 'cube').lower()\n"
                "    loc = desc.get('location', [0,0,0])\n"
                "    sc = desc.get('scale', [1,1,1])\n"
                "    if t == 'cube':\n"
                "        bpy.ops.mesh.primitive_cube_add(location=loc)\n"
                "    elif t in ('sphere','uv_sphere'):\n"
                "        bpy.ops.mesh.primitive_uv_sphere_add(location=loc)\n"
                "    elif t == 'plane':\n"
                "        bpy.ops.mesh.primitive_plane_add(location=loc)\n"
                "    else:\n"
                "        bpy.ops.mesh.primitive_cube_add(location=loc)\n"
                "    obj = bpy.context.active_object\n"
                "    obj.scale = sc\n"
            )
        subprocess.Popen([exe, "--python", script_path], shell=False)
        return "Opening a generated 3D scene in Blender."
    except Exception as e:
        return f"Could not open Blender scene: {e}"

