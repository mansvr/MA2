#!/usr/bin/env python3
"""
Smoke test for the v1 API: health + upload a small OBJ.

Usage (PowerShell):
  $env:MESHANYTHING_API_BASE="https://YOUR_SPACE.hf.space"
  $env:MESHANYTHING_API_KEY="your-studio-shared-secret"   # if server requires it
  python integrations/scripts/test_mvp.py

Optional:
  $env:MESHANYTHING_TEST_MESH="C:\\path\\to\\file.obj"

Private Space (HF auth): create a read token at https://huggingface.co/settings/tokens then:
  $env:MESHANYTHING_HF_TOKEN="hf_..."
"""

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


def main() -> int:
    base = os.environ.get("MESHANYTHING_API_BASE", "").strip().rstrip("/")
    if not base:
        print("Set MESHANYTHING_API_BASE (e.g. https://xxx.hf.space)", file=sys.stderr)
        return 1

    key = os.environ.get("MESHANYTHING_API_KEY", "").strip() or None
    hf = (
        os.environ.get("MESHANYTHING_HF_TOKEN", "").strip()
        or os.environ.get("HF_TOKEN", "").strip()
        or os.environ.get("HUGGING_FACE_HUB_TOKEN", "").strip()
        or None
    )
    timeout = float(os.environ.get("MESHANYTHING_TIMEOUT_SEC", "600"))
    cfg = ClientConfig(base_url=base, api_key=key, hf_token=hf, timeout_sec=timeout)

    print("GET", f"{cfg.base_url}/v1/health")
    r = requests.get(
        f"{cfg.base_url}/v1/health",
        headers=cfg.build_auth_headers(),
        timeout=30,
    )
    print("health:", r.status_code, r.text)
    if r.status_code != 200:
        return 2

    mesh = os.environ.get("MESHANYTHING_TEST_MESH")
    test_path = Path(mesh) if mesh else _repo / "examples" / "wand.obj"
    if not test_path.is_file():
        print("Missing test mesh:", test_path, file=sys.stderr)
        return 3

    print("POST /v1/optimize with", test_path)
    client = MeshAnythingClient(cfg)
    result = client.optimize_file(test_path, input_type="mesh", mc=False)
    out = _repo / "integrations" / "scripts" / "mvp_test_output.obj"
    client.save_result(result, out)
    print("Wrote", out, "bytes", len(result.data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
