"""N-panel / Scene settings for decimate (trimesh) workflow."""

import bpy


class MeshAnythingDecimateSettings(bpy.types.PropertyGroup):
    target_face_count: bpy.props.IntProperty(
        name="Target faces",
        description="POST /v1/decimate — goal triangle count after quadric decimation",
        default=800,
        min=4,
        max=500000,
    )
    strength: bpy.props.EnumProperty(
        name="Strength",
        description="Decimation aggressiveness on the Space",
        items=[
            ("conservative", "Conservative", "Gentle reduction"),
            ("moderate", "Moderate", "Balanced"),
            ("aggressive", "Aggressive", "Stronger reduction"),
        ],
        default="moderate",
    )
    vertex_colors: bpy.props.BoolProperty(
        name="Orange vertex colors",
        description="Cosmetic tint on vertices (API enable_ai_style); turn off for neutral imports",
        default=True,
    )


def register() -> None:
    bpy.utils.register_class(MeshAnythingDecimateSettings)
    bpy.types.Scene.meshanything_decimate = bpy.props.PointerProperty(type=MeshAnythingDecimateSettings)


def unregister() -> None:
    try:
        del bpy.types.Scene.meshanything_decimate
    except Exception:
        pass
    bpy.utils.unregister_class(MeshAnythingDecimateSettings)
