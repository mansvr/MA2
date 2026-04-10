"""
Thin Blender addon: export selection → Space API → import result OBJ.

Enable with folder name `blender_meshanything` so bl_idname matches preferences.
Set environment variables or addon preferences: base URL, optional API key.
"""

import bpy

from . import operators, preferences

bl_info = {
    "name": "MeshAnything Space API",
    "author": "MeshAnything integrations",
    "version": (0, 1, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > MeshAnything",
    "description": "Call MeshAnything v1 REST API (HF Space or self-hosted)",
    "category": "Object",
}


def register() -> None:
    preferences.register()
    operators.register()


def unregister() -> None:
    operators.unregister()
    preferences.unregister()
