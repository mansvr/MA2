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

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "api_base")
        layout.prop(self, "hf_token")
        layout.prop(self, "api_key")
        layout.prop(self, "timeout_sec")
        layout.separator()
        layout.label(text="Neural (/v1/optimize) and Trimesh (/v1/decimate) options are in the")
        layout.label(text="3D View sidebar (N-panel) → MeshAnything.")


def register() -> None:
    bpy.utils.register_class(MeshAnythingPreferences)


def unregister() -> None:
    bpy.utils.unregister_class(MeshAnythingPreferences)
