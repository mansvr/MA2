"""
FastAPI entrypoint for Hugging Face Space or any host.

Contract (v1):
  POST /v1/optimize  multipart/form-data
    - file: required
    - input_type: mesh | pc_normal (default mesh)
    - mc, mc_level, sampling, seed: optional (match main.py)

  Response: application/octet-stream (OBJ) with Content-Disposition attachment.

Errors: JSON { "detail": "...", "code": "..." } (FastAPI-compatible).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import trimesh
import uvicorn
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from inference_service import InferenceService

MESH_EXTS = {".obj", ".ply", ".glb", ".gltf", ".off", ".stl"}
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


@app.get("/v1/health")
def health() -> dict:
    return {"status": "ok", "model_loaded": _service.ready}


@app.post("/v1/optimize")
async def optimize(
    file: UploadFile = File(...),
    input_type: str = Form("mesh"),
    mc: bool = Form(False),
    mc_level: int = Form(7),
    sampling: bool = Form(False),
    seed: int = Form(0),
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

    try:
        obj_bytes = _service.optimize(
            in_path,
            input_type=input_type,
            mc=mc,
            mc_level=mc_level,
            sampling=sampling,
            seed=seed,
        )
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


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "7860"))
    uvicorn.run("app:app", host=host, port=port, factory=False)


if __name__ == "__main__":
    main()
