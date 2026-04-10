"""
Inference runner for the Space API. Expects repository root on sys.path (see app.py).

Uses the same Dataset + forward path as main.py for parity with CLI batch inference.
"""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

import numpy as np
import torch
import trimesh
from accelerate import Accelerator
from accelerate.utils import DistributedDataParallelKwargs, set_seed

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from MeshAnything.models.meshanything_v2 import MeshAnythingV2  # noqa: E402
from main import Dataset  # noqa: E402

_STRENGTH_TO_RATIO = {
    "conservative": 0.85,
    "moderate": 0.55,
    "aggressive": 0.30,
}


def _resolve_target_face_count(
    n_faces: int,
    *,
    target_face_count: int | None,
    optimization_strength: str | None,
) -> int | None:
    """Return a target face count for optional quadric decimation, or None to skip."""
    if n_faces < 2:
        return None
    if target_face_count is not None:
        if target_face_count < 4:
            raise ValueError("target_face_count must be at least 4 when set")
        return min(target_face_count, n_faces)
    if optimization_strength:
        key = optimization_strength.strip().lower()
        if key not in _STRENGTH_TO_RATIO:
            allowed = ", ".join(sorted(_STRENGTH_TO_RATIO))
            raise ValueError(
                f"optimization_strength must be one of: {allowed} (got {optimization_strength!r})"
            )
        return max(4, int(n_faces * _STRENGTH_TO_RATIO[key]))
    return None


def _maybe_simplify_face_count(mesh: trimesh.Trimesh, target_faces: int) -> trimesh.Trimesh:
    """Reduce face count toward ``target_faces`` using trimesh quadric decimation when available."""
    if target_faces < 4 or len(mesh.faces) <= target_faces:
        return mesh
    try:
        simplified = mesh.simplify_quadric_decimation(face_count=target_faces)
    except Exception:
        return mesh
    if len(simplified.faces) < 1:
        return mesh
    return simplified


class InferenceService:
    def __init__(self) -> None:
        self._accelerator: Accelerator | None = None
        self._model = None
        self._project_dir = tempfile.mkdtemp(prefix="meshanything_space_api_")

    @property
    def ready(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        if self._model is not None:
            return
        kwargs = DistributedDataParallelKwargs(find_unused_parameters=True)
        self._accelerator = Accelerator(
            mixed_precision="fp16",
            project_dir=self._project_dir,
            kwargs_handlers=[kwargs],
        )
        self._model = MeshAnythingV2.from_pretrained("Yiwen-ntu/meshanythingv2")
        self._model = self._accelerator.prepare(self._model)
        self._model.eval()

    def optimize(
        self,
        input_path: str,
        *,
        input_type: str,
        mc: bool,
        mc_level: int,
        sampling: bool,
        seed: int,
        target_face_count: int | None = None,
        optimization_strength: str | None = None,
    ) -> bytes:
        if self._accelerator is None or self._model is None:
            raise RuntimeError("Model not loaded")

        set_seed(seed)
        dataset = Dataset(input_type, [input_path], mc, mc_level)
        loader = torch.utils.data.DataLoader(
            dataset,
            batch_size=1,
            drop_last=False,
            shuffle=False,
        )
        loader = self._accelerator.prepare(loader)

        uid = Path(input_path).stem
        out_obj: bytes | None = None

        with torch.inference_mode():
            with self._accelerator.autocast():
                for batch_data_label in loader:
                    outputs = self._model(batch_data_label["pc_normal"], sampling=sampling)
                    batch_size = outputs.shape[0]
                    for batch_id in range(batch_size):
                        recon_mesh = outputs[batch_id]
                        valid_mask = torch.all(~torch.isnan(recon_mesh.reshape((-1, 9))), dim=1)
                        recon_mesh = recon_mesh[valid_mask]
                        vertices = recon_mesh.reshape(-1, 3).cpu()
                        vertices_index = np.arange(len(vertices))
                        triangles = vertices_index.reshape(-1, 3)

                        scene_mesh = trimesh.Trimesh(
                            vertices=vertices,
                            faces=triangles,
                            force="mesh",
                            merge_primitives=True,
                        )
                        scene_mesh.merge_vertices()
                        scene_mesh.update_faces(scene_mesh.nondegenerate_faces())
                        scene_mesh.update_faces(scene_mesh.unique_faces())
                        scene_mesh.remove_unreferenced_vertices()
                        scene_mesh.fix_normals()

                        tgt = _resolve_target_face_count(
                            len(scene_mesh.faces),
                            target_face_count=target_face_count,
                            optimization_strength=optimization_strength,
                        )
                        if tgt is not None:
                            scene_mesh = _maybe_simplify_face_count(scene_mesh, tgt)

                        num_faces = len(scene_mesh.faces)
                        brown_color = np.array([255, 165, 0, 255], dtype=np.uint8)
                        face_colors = np.tile(brown_color, (num_faces, 1))
                        scene_mesh.visual.face_colors = face_colors

                        buf = io.BytesIO()
                        scene_mesh.export(buf, file_type="obj")
                        out_obj = buf.getvalue()

        if out_obj is None:
            raise RuntimeError(f"No output produced for uid={uid}")
        return out_obj
