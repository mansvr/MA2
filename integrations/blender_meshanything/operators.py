from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import bpy

from .preferences import MeshAnythingPreferences

_addon_root = Path(__file__).resolve().parent
_integrations_root = _addon_root.parent
_client_src = _integrations_root / "meshanything_client"
if str(_client_src) not in sys.path:
    sys.path.insert(0, str(_client_src))

from meshanything_client import ClientConfig, MeshAnythingClient  # noqa: E402
from meshanything_client.errors import MeshAnythingAPIError  # noqa: E402


def _get_prefs(context) -> MeshAnythingPreferences:
    return context.preferences.addons["blender_meshanything"].preferences


class MESHANYTHING_OT_optimize(bpy.types.Operator):
    bl_idname = "meshanything.optimize"
    bl_label = "MeshAnything optimize"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and context.selected_objects

    def execute(self, context):
        prefs = _get_prefs(context)
        base = (prefs.api_base or os.environ.get("MESHANYTHING_API_BASE", "")).strip().rstrip("/")
        if not base:
            self.report({"ERROR"}, "Set API base URL in addon preferences or MESHANYTHING_API_BASE")
            return {"CANCELLED"}

        key = (prefs.api_key or os.environ.get("MESHANYTHING_API_KEY", "") or "").strip() or None
        hf = (
            (prefs.hf_token or os.environ.get("MESHANYTHING_HF_TOKEN", "") or "").strip()
            or os.environ.get("HF_TOKEN", "").strip()
            or os.environ.get("HUGGING_FACE_HUB_TOKEN", "").strip()
            or None
        )
        cfg = ClientConfig(
            base_url=base,
            api_key=key,
            hf_token=hf,
            timeout_sec=float(prefs.timeout_sec),
        )
        client = MeshAnythingClient(cfg)

        tmp = tempfile.mkdtemp(prefix="meshanything_blender_")
        in_path = os.path.join(tmp, "meshanything_input.obj")
        out_path = os.path.join(tmp, "meshanything_output.obj")

        try:
            bpy.ops.export_scene.obj(
                filepath=in_path,
                use_selection=True,
                use_materials=False,
                use_triangles=True,
            )
            opt_kw: dict = {
                "input_type": "mesh",
                "mc": prefs.use_marching_cubes,
                "mc_level": int(prefs.mc_level),
                "enable_ai_style": prefs.enable_ai_style,
            }
            if int(prefs.target_face_count) > 0:
                opt_kw["target_face_count"] = int(prefs.target_face_count)
            elif prefs.optimization_strength != "none":
                opt_kw["optimization_strength"] = prefs.optimization_strength
            result = client.optimize_file(in_path, **opt_kw)
            client.save_result(result, out_path)
            bpy.ops.import_scene.obj(filepath=out_path)
        except MeshAnythingAPIError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        except Exception as e:
            self.report({"ERROR"}, f"{type(e).__name__}: {e}")
            return {"CANCELLED"}

        self.report({"INFO"}, "MeshAnything import complete")
        return {"FINISHED"}


class MESHANYTHING_PT_panel(bpy.types.Panel):
    bl_label = "MeshAnything"
    bl_idname = "MESHANYTHING_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MeshAnything"

    def draw(self, context):
        self.layout.operator(MESHANYTHING_OT_optimize.bl_idname)


def register() -> None:
    bpy.utils.register_class(MESHANYTHING_OT_optimize)
    bpy.utils.register_class(MESHANYTHING_PT_panel)


def unregister() -> None:
    bpy.utils.unregister_class(MESHANYTHING_PT_panel)
    bpy.utils.unregister_class(MESHANYTHING_OT_optimize)
