"""
FastAPI entrypoint for Hugging Face Space or any host.

Contract (v1):
  POST /v1/optimize  multipart/form-data
    - file: required
    - input_type: mesh | pc_normal (default mesh)
    - mc, mc_level, sampling, seed: optional (match main.py)
    - enable_ai_style: optional (alias: stochastic generation; ORs with sampling)
    - target_face_count: optional; after neural mesh, trimesh quadric decimation toward this cap
    - optimization_strength: optional conservative|moderate|aggressive; if set without
      target_face_count, derives a target from output face count (trimesh post-process only)

  Response: application/octet-stream (OBJ) with Content-Disposition attachment.

  POST /v1/decimate  multipart/form-data (trimesh-only; no neural model)
    - file: required (.obj, .ply, .stl)
    - target_face_count: default 800 (same range idea as Streamlit slider)
    - optimization_strength: conservative|moderate|aggressive
    - enable_ai_style: optional orange vertex colors (cosmetic; matches old Space)

Errors: JSON { "detail": "...", "code": "..." } (FastAPI-compatible).
"""

from __future__ import annotations

import os
import shutil
import tempfile


def _fix_omp_num_threads() -> None:
    """HF / orchestration sometimes sets OMP_NUM_THREADS to empty or invalid → libgomp warning."""
    raw = os.environ.get("OMP_NUM_THREADS", "").strip()
    ok = raw.isdigit() and int(raw) >= 1
    if not ok:
        os.environ["OMP_NUM_THREADS"] = "4"


_fix_omp_num_threads()
from pathlib import Path

import trimesh
import uvicorn
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from inference_service import InferenceService
from trimesh_decimate import decimate_to_obj_bytes

MESH_EXTS = {".obj", ".ply", ".glb", ".gltf", ".off", ".stl"}
DECIMATE_EXTS = {".obj", ".ply", ".stl"}
PC_EXTS = {".npy"}

app = FastAPI(title="MeshAnything Space API", version="1.0.0")
_service = InferenceService()


def _studio_key_from_request(request: Request) -> str | None:
    """Studio secret from X-MeshAnything-Key (preferred with HF private Spaces) or Authorization Bearer."""
    x = request.headers.get("x-meshanything-key") or request.headers.get("X-MeshAnything-Key")
    if x:
        return x.strip()
    auth = request.headers.get("authorization") or ""
    if auth.startswith("Bearer "):
        return auth[len("Bearer ") :].strip()
    return None


def _check_api_key(request: Request) -> None:
    expected = os.environ.get("MESHANYTHING_SERVER_API_KEY")
    if not expected:
        return
    got = _studio_key_from_request(request)
    if got is None:
        raise HTTPException(
            status_code=401,
            detail="Missing API key (X-MeshAnything-Key or Authorization Bearer)",
            headers={"X-Error-Code": "UNAUTHORIZED"},
        )
    if got != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"X-Error-Code": "UNAUTHORIZED"},
        )


@app.on_event("startup")
def _startup() -> None:
    _service.load()


@app.get("/")
def root() -> dict:
    """HF and browsers hit `/`; avoid noisy 404s in logs. API lives under `/v1/`."""
    return {
        "service": "meshanything-space-api",
        "health": "/v1/health",
        "optimize": "POST /v1/optimize (neural MeshAnything V2)",
        "decimate": "POST /v1/decimate (trimesh-only, parity with meshanythingv2-fromlocal)",
        "docs": "/docs",
    }


@app.get("/v1/health")
def health() -> dict:
    return {
        "status": "ok",
        "model_loaded": _service.ready,
        "trimesh_decimate": True,
    }


@app.post("/v1/optimize")
async def optimize(
    file: UploadFile = File(...),
    input_type: str = Form("mesh"),
    mc: bool = Form(False),
    mc_level: int = Form(7),
    sampling: bool = Form(False),
    enable_ai_style: bool = Form(False),
    seed: int = Form(0),
    target_face_count: int | None = Form(default=None),
    optimization_strength: str | None = Form(default=None),
    _: None = Depends(_check_api_key),
) -> Response:
    if input_type not in ("mesh", "pc_normal"):
        raise HTTPException(
            status_code=422,
            detail="input_type must be 'mesh' or 'pc_normal'",
        )

    suffix = Path(file.filename or "input").suffix.lower()
    if input_type == "mesh":
        if suffix not in MESH_EXTS:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Unsupported mesh extension '{suffix}'. "
                    f"Supported: {sorted(MESH_EXTS)}. "
                    "FBX often requires extra converters; export to OBJ or GLB first."
                ),
                headers={"X-Error-Code": "UNSUPPORTED_FORMAT"},
            )
    else:
        if suffix not in PC_EXTS:
            raise HTTPException(
                status_code=422,
                detail="Point cloud input must be a .npy with shape (N,6) normals (see upstream docs).",
                headers={"X-Error-Code": "UNSUPPORTED_FORMAT"},
            )

    max_mb = float(os.environ.get("MESHANYTHING_MAX_UPLOAD_MB", "128"))
    body = await file.read()
    if len(body) > max_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (limit {max_mb} MB).",
            headers={"X-Error-Code": "PAYLOAD_TOO_LARGE"},
        )

    tmp_dir = tempfile.mkdtemp(prefix="meshanything_upload_")
    in_path = os.path.join(tmp_dir, f"input{suffix}")
    with open(in_path, "wb") as f:
        f.write(body)

    if input_type == "mesh":
        try:
            trimesh.load(in_path, force="mesh")
        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail=f"Could not load mesh with trimesh: {e}",
                headers={"X-Error-Code": "LOAD_FAILED"},
            ) from e

    use_sampling = bool(sampling or enable_ai_style)
    tfc = target_face_count if (target_face_count is not None and target_face_count > 0) else None
    try:
        obj_bytes = _service.optimize(
            in_path,
            input_type=input_type,
            mc=mc,
            mc_level=mc_level,
            sampling=use_sampling,
            seed=seed,
            target_face_count=tfc,
            optimization_strength=(optimization_strength.strip() or None)
            if optimization_strength
            else None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=str(e),
            headers={"X-Error-Code": "INVALID_OPTIONS"},
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
            headers={"X-Error-Code": "INFERENCE_FAILED"},
        ) from e
    finally:
        try:
            Path(in_path).unlink(missing_ok=True)
        except OSError:
            pass

    out_name = f"{Path(file.filename or 'mesh').stem}_meshanything.obj"
    return Response(
        content=obj_bytes,
        media_type="model/obj",
        headers={
            "Content-Disposition": f'attachment; filename="{out_name}"',
        },
    )


@app.post("/v1/decimate")
async def decimate(
    file: UploadFile = File(...),
    target_face_count: int = Form(800),
    optimization_strength: str = Form("moderate"),
    enable_ai_style: bool = Form(True),
    _: None = Depends(_check_api_key),
) -> Response:
    """
    Trimesh-only decimation (matches Hugging Face Space meshanythingv2-fromlocal Streamlit app).
    No GPU model required; works even when neural weights are unavailable.
    """
    suffix = Path(file.filename or "input").suffix.lower()
    if suffix not in DECIMATE_EXTS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unsupported extension '{suffix}' for /v1/decimate. "
                f"Supported: {sorted(DECIMATE_EXTS)}."
            ),
            headers={"X-Error-Code": "UNSUPPORTED_FORMAT"},
        )

    max_mb = float(os.environ.get("MESHANYTHING_MAX_UPLOAD_MB", "128"))
    body = await file.read()
    if len(body) > max_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (limit {max_mb} MB).",
            headers={"X-Error-Code": "PAYLOAD_TOO_LARGE"},
        )

    tmp_dir = tempfile.mkdtemp(prefix="meshanything_decimate_")
    in_path = os.path.join(tmp_dir, f"input{suffix}")
    try:
        with open(in_path, "wb") as f:
            f.write(body)
        try:
            obj_bytes, msg, faces_in, faces_out = decimate_to_obj_bytes(
                in_path,
                target_face_count=target_face_count,
                optimization_strength=optimization_strength,
                enable_ai_style=enable_ai_style,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail=str(e),
                headers={"X-Error-Code": "INVALID_OPTIONS"},
            ) from e
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=str(e),
                headers={"X-Error-Code": "DECIMATE_FAILED"},
            ) from e
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except OSError:
            pass

    note = msg.encode("ascii", "replace").decode("ascii")[:512]
    out_name = f"{Path(file.filename or 'mesh').stem}_trimesh_decimated.obj"
    return Response(
        content=obj_bytes,
        media_type="model/obj",
        headers={
            "Content-Disposition": f'attachment; filename="{out_name}"',
            "X-Trimesh-Faces-In": str(faces_in),
            "X-Trimesh-Faces-Out": str(faces_out),
            "X-Trimesh-Note": note,
        },
    )


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "7860"))
    uvicorn.run("app:app", host=host, port=port, factory=False)


if __name__ == "__main__":
    main()
