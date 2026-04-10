#!/usr/bin/env python3
"""Smoke test for POST /v1/decimate (trimesh-only; no neural model)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_repo = Path(__file__).resolve().parents[2]
_client = _repo / "integrations" / "meshanything_client"
if _client.is_dir() and str(_client) not in sys.path:
    sys.path.insert(0, str(_client))

import requests

from meshanything_client import ClientConfig, MeshAnythingClient
from meshanything_client.errors import MeshAnythingAPIError


def main() -> int:
    base = os.environ.get("MESHANYTHING_API_BASE", "").strip().rstrip("/")
    if not base:
        print("Set MESHANYTHING_API_BASE", file=sys.stderr)
        return 1

    key = os.environ.get("MESHANYTHING_API_KEY", "").strip() or None
    hf = (
        os.environ.get("MESHANYTHING_HF_TOKEN", "").strip()
        or os.environ.get("HF_TOKEN", "").strip()
        or None
    )
    timeout = float(os.environ.get("MESHANYTHING_TIMEOUT_SEC", "600"))
    cfg = ClientConfig(base_url=base, api_key=key, hf_token=hf, timeout_sec=timeout)

    r = requests.get(
        f"{cfg.base_url}/v1/health",
        headers=cfg.build_auth_headers(),
        timeout=30,
    )
    print("health:", r.status_code, r.text)
    if r.status_code != 200:
        return 2

    root = requests.get(
        f"{cfg.base_url}/",
        headers=cfg.build_auth_headers(),
        timeout=30,
    )
    if root.status_code == 200:
        try:
            info = root.json()
            if "decimate" not in info:
                print(
                    "Warning: GET / does not list /v1/decimate — Space image is probably "
                    "older than this repo. Push the latest code (including "
                    "integrations/space_api/trimesh_decimate.py) and rebuild the Space.",
                    file=sys.stderr,
                )
        except Exception:
            pass

    mesh = os.environ.get("MESHANYTHING_TEST_MESH")
    test_path = Path(mesh) if mesh else _repo / "examples" / "wand.obj"
    if not test_path.is_file():
        print("Missing test mesh:", test_path, file=sys.stderr)
        return 3

    tfc = int(os.environ.get("MESHANYTHING_TARGET_FACE_COUNT", "800"))
    strength = os.environ.get("MESHANYTHING_OPTIMIZATION_STRENGTH", "moderate").strip()
    ai = os.environ.get("MESHANYTHING_DECIMATE_AI_STYLE", "1").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    client = MeshAnythingClient(cfg)
    print("POST /v1/decimate", test_path, "target_face_count=", tfc, "strength=", strength)
    try:
        result = client.decimate_file(
            test_path,
            target_face_count=tfc,
            optimization_strength=strength,
            enable_ai_style=ai,
        )
    except MeshAnythingAPIError as e:
        if e.status_code == 404:
            print(
                "404 Not Found on POST /v1/decimate — the running Space does not include "
                "this route yet. Redeploy: push this repo to the Space (Docker build) so "
                "app.py contains @app.post('/v1/decimate').",
                file=sys.stderr,
            )
        raise
    out = _repo / "integrations" / "scripts" / "mvp_decimate_output.obj"
    client.save_result(result, out)
    print("Wrote", out, "bytes", len(result.data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
