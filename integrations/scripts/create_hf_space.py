#!/usr/bin/env python3
"""
Create a Hugging Face Space (Docker SDK) and request GPU hardware via the Hub API.

Prerequisites:
  - pip install -U "huggingface_hub>=0.20"
  - A Hugging Face account token with write access:
      https://huggingface.co/settings/tokens
  - Set one of: HF_TOKEN, HUGGING_FACE_HUB_TOKEN

Usage (PowerShell):
  $env:HF_TOKEN = "hf_..."
  python integrations/scripts/create_hf_space.py --repo-id YourHFUser/ma2-api --hardware t4-small --private

Then push this repo to the Space (see integrations/MVP_SETUP.md Step 2b).

Hardware slugs match HF Hub (cheapest GPU for tests: t4-small).
"""

from __future__ import annotations

import argparse
import os
import sys

from huggingface_hub import HfApi, SpaceHardware


def _hardware(name: str) -> SpaceHardware:
    by_value = {h.value: h for h in SpaceHardware}
    if name in by_value:
        return by_value[name]
    alias = {
        "t4": SpaceHardware.T4_SMALL,
        "a10g": SpaceHardware.A10G_SMALL,
        "l4": SpaceHardware.L4X1,
    }
    if name in alias:
        return alias[name]
    raise SystemExit(f"Unknown hardware {name!r}. Try: {sorted(by_value.keys())}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--repo-id",
        required=True,
        help="Namespace/name on the Hub, e.g. Mansur333/ma2-api",
    )
    p.add_argument(
        "--hardware",
        default="t4-small",
        help="GPU flavor (e.g. t4-small, t4-medium, l4x1, a10g-small, zero-a10g) or 'cpu-basic'",
    )
    p.add_argument("--private", action="store_true", help="Private Space")
    p.add_argument(
        "--exist-ok",
        action="store_true",
        help="Do not fail if the Space repo already exists",
    )
    args = p.parse_args()

    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        print("Set HF_TOKEN (or HUGGING_FACE_HUB_TOKEN) to a write-capable token.", file=sys.stderr)
        return 1

    api = HfApi(token=token)
    hw = _hardware(args.hardware)

    url = api.create_repo(
        repo_id=args.repo_id,
        repo_type="space",
        space_sdk="docker",
        space_hardware=hw,
        private=args.private,
        exist_ok=args.exist_ok,
    )
    print("Created or updated:", url)
    print("Space page:", f"https://huggingface.co/spaces/{args.repo_id}")
    print("Next: push code — see integrations/MVP_SETUP.md (Step 2b).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
