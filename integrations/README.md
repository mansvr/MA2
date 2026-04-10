# MeshAnything V2 — integrations (v1)

**End-to-end MVP (HF Space, studio key, Blender, smoke test):** see [MVP_SETUP.md](MVP_SETUP.md).

## Contract summary

- **POST** `{base}/v1/optimize` — `multipart/form-data`: `file`, optional `input_type` (`mesh` | `pc_normal`), `mc`, `mc_level`, `sampling`, `seed`.
- **Response:** `model/obj` bytes; `Content-Disposition` filename `*_meshanything.obj`.
- **Errors:** JSON `detail` (FastAPI); optional **`X-Error-Code`** header (`UNAUTHORIZED`, `UNSUPPORTED_FORMAT`, `PAYLOAD_TOO_LARGE`, `LOAD_FAILED`, `INFERENCE_FAILED`).
- **Auth (optional):** set `MESHANYTHING_SERVER_API_KEY` on the server. Clients send **`Authorization: Bearer …`** (public Space) or **`X-MeshAnything-Key`** + **`Authorization: Bearer <HF token>`** for **private** Spaces (see `ClientConfig.build_auth_headers`).
- **Limits:** default **128 MB** upload (`MESHANYTHING_MAX_UPLOAD_MB`); default **600 s** client timeout (`MESHANYTHING_TIMEOUT_SEC`).

**Upstream model inputs:** mesh via **trimesh** (e.g. `.obj`, `.ply`, `.glb`/`.gltf`, `.stl`, …) or point cloud **`.npy`** `(N,6)` positions+normals (see `main.py`). **FBX** is not guaranteed (often needs assimp or offline conversion). **Image / text / NeRF / 3DGS** are *not* part of stock MeshAnything V2 in this repo; those are separate pipelines (e.g. dense mesh from another tool, then this API).

## Python client

```bash
cd integrations/meshanything_client
pip install -e .
export MESHANYTHING_API_BASE="https://your-space.hf.space"
# optional: export MESHANYTHING_API_KEY="..."
python -c "from meshanything_client import MeshAnythingClient, ClientConfig; ..."
```

## FastAPI server (Space or VPS)

Requires full **MeshAnything V2** deps (torch, accelerate, trimesh, repo root on `PYTHONPATH`).

```bash
cd integrations/space_api
pip install -r requirements.txt
# From repo root, with GPU and project venv:
set PYTHONPATH=o:\MeshanythingV2
cd integrations\space_api
python app.py
```

Deploy on HF: use a **Docker Space** whose `CMD` runs `uvicorn` on `$PORT`, with this repo + `requirements.txt` + base `requirements.txt` from the project root.

## Blender

Install the folder `integrations/blender_meshanything` as addon (zip the inner folder so the addon module name stays `blender_meshanything`). Set **API base URL** in preferences. Optional env: `MESHANYTHING_API_BASE`, `MESHANYTHING_API_KEY`.

## Houdini

Add `integrations/meshanything_client` to **HOUDINI_PYTHONPATH** (or use `meshanything_hda.py` path logic). Set `MESHANYTHING_API_BASE` (and optional key), then call `optimize_file(in_obj, out_obj)` from a Python SOP or shelf script after writing geometry to OBJ.
