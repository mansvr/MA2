import bpy


class MeshAnythingPreferences(bpy.types.AddonPreferences):
    bl_idname = "blender_meshanything"

    api_base: bpy.props.StringProperty(
        name="API base URL",
        description="e.g. https://your-space.hf.space (no trailing slash)",
        default="",
    )
    api_key: bpy.props.StringProperty(
        name="Studio API key",
        description="Shared secret if MESHANYTHING_SERVER_API_KEY is set on the server (X-MeshAnything-Key if HF token is set)",
        default="",
        subtype="PASSWORD",
    )
    hf_token: bpy.props.StringProperty(
        name="Hugging Face token",
        description="Read token (hf_...) for private Spaces only; leave empty on public Spaces",
        default="",
        subtype="PASSWORD",
    )
    timeout_sec: bpy.props.FloatProperty(
        name="Timeout (s)",
        default=600.0,
        min=30.0,
        max=7200.0,
    )
    use_marching_cubes: bpy.props.BoolProperty(
        name="Marching cubes preprocess",
        description="Matches main.py --mc",
        default=False,
    )
    mc_level: bpy.props.IntProperty(
        name="MC level",
        description="2**level grid size (7 => 128)",
        default=7,
        min=5,
        max=10,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "api_base")
        layout.prop(self, "hf_token")
        layout.prop(self, "api_key")
        layout.prop(self, "timeout_sec")
        layout.prop(self, "use_marching_cubes")
        layout.prop(self, "mc_level")


def register() -> None:
    bpy.utils.register_class(MeshAnythingPreferences)


def unregister() -> None:
    bpy.utils.unregister_class(MeshAnythingPreferences)
