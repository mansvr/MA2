from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import bpy

from .preferences import MeshAnythingPreferences

_addon_root = Path(__file__).resolve().parent
# Zip install: meshanything_client/ is bundled next to this file.
# Repo dev: also integrations/meshanything_client/ (parent of this addon folder).
for _base in (_addon_root, _addon_root.parent / "meshanything_client"):
    if (_base / "meshanything_client" / "__init__.py").is_file():
        if str(_base) not in sys.path:
            sys.path.insert(0, str(_base))
        break

from meshanything_client import ClientConfig, MeshAnythingClient  # noqa: E402
from meshanything_client.errors import MeshAnythingAPIError  # noqa: E402


def _get_prefs(context) -> MeshAnythingPreferences:
    return context.preferences.addons["blender_meshanything"].preferences


def _export_selection_obj(filepath: str) -> None:
    """Blender 4.0+ uses wm.obj_export; older builds use export_scene.obj."""
    if hasattr(bpy.ops.wm, "obj_export"):
        bpy.ops.wm.obj_export(
            filepath=filepath,
            export_selected_objects=True,
            export_materials=False,
            export_triangulated_mesh=True,
        )
    else:
        bpy.ops.export_scene.obj(
            filepath=filepath,
            use_selection=True,
            use_materials=False,
            use_triangles=True,
        )


def _import_obj(filepath: str) -> None:
    """Blender 4.0+ uses wm.obj_import; older builds use import_scene.obj."""
    if hasattr(bpy.ops.wm, "obj_import"):
        bpy.ops.wm.obj_import(filepath=filepath)
    else:
        bpy.ops.import_scene.obj(filepath=filepath)


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
            self.report(
                {"INFO"},
                "Neural optimize: calling Space (can take several minutes; Blender may look frozen)",
            )
            print("[MeshAnything] Neural optimize: waiting for API…")
            _export_selection_obj(in_path)
            os_ = context.scene.meshanything_optimize
            opt_kw: dict = {
                "input_type": "mesh",
                "mc": os_.use_marching_cubes,
                "mc_level": int(os_.mc_level),
                "enable_ai_style": os_.enable_ai_style,
                "seed": int(os_.seed),
            }
            if int(os_.target_face_count) > 0:
                opt_kw["target_face_count"] = int(os_.target_face_count)
            elif os_.optimization_strength != "none":
                opt_kw["optimization_strength"] = os_.optimization_strength
            result = client.optimize_file(in_path, **opt_kw)
            client.save_result(result, out_path)
            _import_obj(out_path)
        except MeshAnythingAPIError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        except Exception as e:
            self.report({"ERROR"}, f"{type(e).__name__}: {e}")
            return {"CANCELLED"}

        self.report({"INFO"}, "MeshAnything import complete")
        return {"FINISHED"}


class MESHANYTHING_OT_decimate_trimesh(bpy.types.Operator):
    bl_idname = "meshanything.decimate_trimesh"
    bl_label = "Trimesh decimate (API)"
    bl_description = "POST /v1/decimate only — quadric decimation on the Space, no neural model"
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

        tmp = tempfile.mkdtemp(prefix="meshanything_blender_decimate_")
        in_path = os.path.join(tmp, "meshanything_input.obj")
        out_path = os.path.join(tmp, "meshanything_trimesh_out.obj")

        try:
            _export_selection_obj(in_path)
            ds = context.scene.meshanything_decimate
            result = client.decimate_file(
                in_path,
                target_face_count=int(ds.target_face_count),
                optimization_strength=ds.strength,
                enable_ai_style=ds.vertex_colors,
            )
            client.save_result(result, out_path)
            _import_obj(out_path)
        except MeshAnythingAPIError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        except Exception as e:
            self.report({"ERROR"}, f"{type(e).__name__}: {e}")
            return {"CANCELLED"}

        parts: list[str] = []
        if result.faces_in is not None and result.faces_out is not None:
            parts.append(f"{result.faces_in} → {result.faces_out} faces (server)")
        if result.server_note:
            parts.append(str(result.server_note)[:160])
        msg = " | ".join(parts) if parts else "import complete"
        self.report({"INFO"}, f"Decimate: {msg}")
        print(f"[MeshAnything] Decimate: {msg}")
        return {"FINISHED"}


class MESHANYTHING_PT_panel(bpy.types.Panel):
    bl_label = "MeshAnything"
    bl_idname = "MESHANYTHING_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MeshAnything"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        os_ = scene.meshanything_optimize
        ds = scene.meshanything_decimate

        nbox = layout.box()
        nbox.label(text="Neural /v1/optimize")
        nbox.label(text="Start: AI-style off, target 0, strength None")
        nbox.prop(os_, "use_marching_cubes")
        nbox.prop(os_, "mc_level")
        nbox.prop(os_, "enable_ai_style")
        nbox.prop(os_, "seed")
        nbox.prop(os_, "target_face_count")
        nbox.prop(os_, "optimization_strength")
        nbox.operator(MESHANYTHING_OT_optimize.bl_idname, text="Optimize (neural)")

        tbox = layout.box()
        tbox.label(text="Trimesh /v1/decimate")
        tbox.prop(ds, "target_face_count")
        tbox.prop(ds, "strength")
        tbox.prop(ds, "vertex_colors")
        tbox.operator(MESHANYTHING_OT_decimate_trimesh.bl_idname, text="Decimate (trimesh)")


def register() -> None:
    bpy.utils.register_class(MESHANYTHING_OT_optimize)
    bpy.utils.register_class(MESHANYTHING_OT_decimate_trimesh)
    bpy.utils.register_class(MESHANYTHING_PT_panel)


def unregister() -> None:
    bpy.utils.unregister_class(MESHANYTHING_PT_panel)
    bpy.utils.unregister_class(MESHANYTHING_OT_decimate_trimesh)
    bpy.utils.unregister_class(MESHANYTHING_OT_optimize)
