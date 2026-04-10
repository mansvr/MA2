"""N-panel / Scene settings for neural optimize and trimesh decimate workflows."""

import bpy


class MeshAnythingOptimizeSettings(bpy.types.PropertyGroup):
    """POST /v1/optimize — neural MeshAnything V2 + optional trimesh post cap."""

    use_marching_cubes: bpy.props.BoolProperty(
        name="Marching cubes preprocess",
        description=(
            "Voxelize then sample points (slow). Try OFF first for clean OBJs; ON can help thin or messy geometry "
            "(see upstream main.py --mc)"
        ),
        default=False,
    )
    mc_level: bpy.props.IntProperty(
        name="MC level",
        description="Marching-cubes grid size 2**level (7 → 128³). Higher = finer but much slower and more VRAM",
        default=7,
        min=5,
        max=10,
    )
    enable_ai_style: bpy.props.BoolProperty(
        name="AI-style sampling",
        description=(
            "Stochastic output — can vary wildly run-to-run; OFF is recommended until you get a good baseline mesh"
        ),
        default=False,
    )
    seed: bpy.props.IntProperty(
        name="Seed",
        description="Random seed on the Space (affects sampling / point choices). Change if AI-style is ON and output is bad",
        default=0,
        min=0,
        max=2147483647,
    )
    target_face_count: bpy.props.IntProperty(
        name="Target face count",
        description=(
            "After neural inference, optional triangle cap via quadric decimation. 0 = no cap (use full neural mesh). "
            "Use thousands (e.g. 8000–20000), not single digits"
        ),
        default=0,
        min=0,
        max=500000,
    )
    optimization_strength: bpy.props.EnumProperty(
        name="Optimization strength",
        description=(
            "Only used when target face count is 0: scales down triangles from neural output (conservative/moderate/aggressive). "
            "Use None until the un-decimated mesh looks good"
        ),
        items=[
            ("none", "None", "No extra decimation — full neural mesh (recommended first)"),
            ("conservative", "Conservative", "Keep ~85% of neural triangle count"),
            ("moderate", "Moderate", "Keep ~55%"),
            ("aggressive", "Aggressive", "Keep ~30%"),
        ],
        default="none",
    )


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
    bpy.utils.register_class(MeshAnythingOptimizeSettings)
    bpy.utils.register_class(MeshAnythingDecimateSettings)
    bpy.types.Scene.meshanything_optimize = bpy.props.PointerProperty(type=MeshAnythingOptimizeSettings)
    bpy.types.Scene.meshanything_decimate = bpy.props.PointerProperty(type=MeshAnythingDecimateSettings)


def unregister() -> None:
    try:
        del bpy.types.Scene.meshanything_optimize
    except Exception:
        pass
    try:
        del bpy.types.Scene.meshanything_decimate
    except Exception:
        pass
    bpy.utils.unregister_class(MeshAnythingDecimateSettings)
    bpy.utils.unregister_class(MeshAnythingOptimizeSettings)
