"""
Trimesh-only mesh decimation (parity with Streamlit Space meshanythingv2-fromlocal).

No neural model — quadric decimation, cleaning, and optional orange vertex colors
("AI-style") matching the public app behavior.
"""

from __future__ import annotations

import io
from typing import Literal

import numpy as np
import trimesh

StrengthTitle = Literal["Conservative", "Moderate", "Aggressive"]

_STRENGTH_MAP = {
    "conservative": "Conservative",
    "moderate": "Moderate",
    "aggressive": "Aggressive",
}


def normalize_strength(s: str) -> StrengthTitle:
    key = s.strip().lower()
    if key not in _STRENGTH_MAP:
        allowed = ", ".join(sorted(_STRENGTH_MAP))
        raise ValueError(f"optimization_strength must be one of: {allowed} (got {s!r})")
    return _STRENGTH_MAP[key]  # type: ignore[return-value]


def load_mesh_from_path(path: str) -> trimesh.Trimesh:
    """Load mesh; if Scene, use first geometry (same as Streamlit app)."""
    loaded = trimesh.load(path, force="mesh")
    if isinstance(loaded, trimesh.Scene):
        if not loaded.geometry:
            raise ValueError("Empty scene: no geometry")
        first = next(iter(loaded.geometry.values()))
        if not isinstance(first, trimesh.Trimesh):
            raise ValueError("Scene geometry is not a Trimesh")
        return first
    if not isinstance(loaded, trimesh.Trimesh):
        raise ValueError("File did not load as a triangle mesh")
    return loaded


def advanced_mesh_cleaning(mesh: trimesh.Trimesh, *, aggressive: bool) -> trimesh.Trimesh:
    """Port of advanced_mesh_cleaning from meshanythingv2-fromlocal app.py."""
    cleaned_mesh = mesh.copy()
    cleaned_mesh.merge_vertices()
    try:
        cleaned_mesh.update_faces(cleaned_mesh.unique_faces())
    except Exception:
        try:
            cleaned_mesh.update_faces(cleaned_mesh.nondegenerate_faces())
        except Exception:
            pass
    cleaned_mesh.fix_normals()
    try:
        cleaned_mesh.update_faces(cleaned_mesh.nondegenerate_faces())
    except Exception:
        pass
    if not aggressive:
        try:
            cleaned_mesh.fill_holes()
        except Exception:
            pass
    return cleaned_mesh


def smart_simplify(
    mesh: trimesh.Trimesh,
    target_faces: int,
    strength: StrengthTitle,
) -> tuple[trimesh.Trimesh, str]:
    """
    Primary quadric decimation + optional multi-step / merge fallbacks
    (same structure as the Streamlit smart_simplify).
    """
    original_faces = len(mesh.faces)
    if original_faces <= target_faces:
        return mesh, f"already at target ({original_faces} faces)"

    simplified_mesh = mesh.copy()

    try:
        simplified_mesh = simplified_mesh.simplify_quadric_decimation(face_count=target_faces)
        current_faces = len(simplified_mesh.faces)

        if current_faces > target_faces * 1.3 and strength in ("Moderate", "Aggressive"):
            temp_mesh = mesh.copy()
            reduction_factor = target_faces / float(original_faces)
            if strength == "Aggressive":
                steps = 3
                for i in range(steps):
                    step_target = int(original_faces * (reduction_factor ** ((i + 1) / steps)))
                    step_target = max(step_target, target_faces)
                    try:
                        temp_mesh = temp_mesh.simplify_quadric_decimation(face_count=step_target)
                    except Exception:
                        break
                if len(temp_mesh.faces) < len(simplified_mesh.faces):
                    simplified_mesh = temp_mesh

        if len(simplified_mesh.faces) > target_faces * 1.2:
            try:
                merge_mesh = mesh.copy()
                scale = float(mesh.scale) if getattr(mesh, "scale", None) not in (None, 0) else 1.0
                if strength == "Conservative":
                    merge_distance = scale / 1000.0
                elif strength == "Moderate":
                    merge_distance = scale / 500.0
                else:
                    merge_distance = scale / 200.0
                _ = merge_distance  # original app passed this to merge_vertices; trimesh uses digits
                merge_mesh.merge_vertices()
                if len(merge_mesh.faces) > target_faces:
                    merge_mesh = merge_mesh.simplify_quadric_decimation(face_count=target_faces)
                if len(merge_mesh.faces) < len(simplified_mesh.faces):
                    simplified_mesh = merge_mesh
            except Exception:
                pass

        final_faces = len(simplified_mesh.faces)
        reduction = ((original_faces - final_faces) / original_faces) * 100
        return simplified_mesh, f"reduced by {reduction:.1f}% ({original_faces} → {final_faces} faces)"

    except Exception as e:
        try:
            fallback_mesh = mesh.copy()
            scale = float(mesh.scale) if getattr(mesh, "scale", None) not in (None, 0) else 1.0
            if strength == "Aggressive":
                merge_distance = scale / 100.0
            elif strength == "Moderate":
                merge_distance = scale / 200.0
            else:
                merge_distance = scale / 500.0
            _ = merge_distance
            fallback_mesh.merge_vertices()
            fallback_mesh.update_faces(fallback_mesh.unique_faces())
            final_faces = len(fallback_mesh.faces)
            reduction = ((original_faces - final_faces) / original_faces) * 100
            return fallback_mesh, f"fallback optimization: {reduction:.1f}% ({original_faces} → {final_faces} faces)"
        except Exception as e2:
            return mesh, f"all simplification methods failed: {e!s}; {e2!s}"


def apply_ai_style_vertex_colors(mesh: trimesh.Trimesh) -> None:
    """Orange vertex colors like the Streamlit 'AI-Style Processing' checkbox."""
    orange = np.array([255, 165, 0, 255], dtype=np.uint8)
    mesh.visual.vertex_colors = np.tile(orange, (len(mesh.vertices), 1))


def decimate_to_obj_bytes(
    input_path: str,
    *,
    target_face_count: int,
    optimization_strength: str,
    enable_ai_style: bool,
) -> tuple[bytes, str, int, int]:
    """
    Returns (obj_bytes, message, faces_in, faces_out).
    """
    strength = normalize_strength(optimization_strength)
    mesh = load_mesh_from_path(input_path)
    original_faces = len(mesh.faces)

    cleaned = advanced_mesh_cleaning(
        mesh,
        aggressive=(strength == "Aggressive"),
    )

    if original_faces > target_face_count:
        optimized, msg = smart_simplify(cleaned, target_face_count, strength)
    else:
        optimized = cleaned
        msg = f"mesh already has fewer faces than target ({original_faces} ≤ {target_face_count})"

    optimized.merge_vertices()
    optimized.fix_normals()

    if enable_ai_style:
        try:
            apply_ai_style_vertex_colors(optimized)
        except Exception:
            pass

    final_faces = len(optimized.faces)
    buf = io.BytesIO()
    optimized.export(buf, file_type="obj")
    return buf.getvalue(), msg, original_faces, final_faces
