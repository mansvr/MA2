from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import requests

from meshanything_client.config import ClientConfig
from meshanything_client.errors import MeshAnythingAPIError

InputType = Literal["mesh", "pc_normal"]


@dataclass(frozen=True)
class OptimizeResult:
    """Result of a successful /v1/optimize call."""

    content_type: str
    data: bytes
    filename: str | None = None


class MeshAnythingClient:
    """Thin REST client for the v1 Space API contract."""

    def __init__(self, config: ClientConfig):
        self._config = config

    def optimize_file(
        self,
        file_path: str | Path,
        *,
        input_type: InputType = "mesh",
        mc: bool = False,
        mc_level: int = 7,
        sampling: bool = False,
        enable_ai_style: bool = False,
        seed: int = 0,
        target_face_count: int | None = None,
        optimization_strength: str | None = None,
    ) -> OptimizeResult:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(str(path))

        url = f"{self._config.base_url}/v1/optimize"
        headers = self._config.build_auth_headers()

        with path.open("rb") as f:
            files = {"file": (path.name, f, "application/octet-stream")}
            data = {
                "input_type": input_type,
                "mc": str(mc).lower(),
                "mc_level": str(mc_level),
                "sampling": str(sampling).lower(),
                "enable_ai_style": str(enable_ai_style).lower(),
                "seed": str(seed),
            }
            if target_face_count is not None:
                data["target_face_count"] = str(target_face_count)
            if optimization_strength is not None:
                data["optimization_strength"] = optimization_strength
            resp = requests.post(
                url,
                headers=headers,
                files=files,
                data=data,
                timeout=self._config.timeout_sec,
            )

        if resp.status_code >= 400:
            raise _error_from_response(resp)

        cd = resp.headers.get("Content-Disposition", "")
        filename = _parse_filename_from_content_disposition(cd)
        return OptimizeResult(
            content_type=resp.headers.get("Content-Type", "model/obj"),
            data=resp.content,
            filename=filename,
        )

    def decimate_file(
        self,
        file_path: str | Path,
        *,
        target_face_count: int = 800,
        optimization_strength: str = "moderate",
        enable_ai_style: bool = True,
    ) -> OptimizeResult:
        """POST /v1/decimate — trimesh-only (parity with meshanythingv2-fromlocal Space)."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(str(path))

        url = f"{self._config.base_url}/v1/decimate"
        headers = self._config.build_auth_headers()

        with path.open("rb") as f:
            files = {"file": (path.name, f, "application/octet-stream")}
            data = {
                "target_face_count": str(target_face_count),
                "optimization_strength": optimization_strength,
                "enable_ai_style": str(enable_ai_style).lower(),
            }
            resp = requests.post(
                url,
                headers=headers,
                files=files,
                data=data,
                timeout=self._config.timeout_sec,
            )

        if resp.status_code >= 400:
            raise _error_from_response(resp)

        cd = resp.headers.get("Content-Disposition", "")
        filename = _parse_filename_from_content_disposition(cd)
        return OptimizeResult(
            content_type=resp.headers.get("Content-Type", "model/obj"),
            data=resp.content,
            filename=filename,
        )

    def save_result(self, result: OptimizeResult, out_path: str | Path) -> Path:
        out = Path(out_path)
        out.write_bytes(result.data)
        return out


def _parse_filename_from_content_disposition(value: str) -> str | None:
    # Very small parser: filename="foo.obj"
    if "filename=" not in value:
        return None
    part = value.split("filename=", 1)[1].strip()
    if part.startswith('"'):
        return part.strip('"').split(";", 1)[0]
    return part.split(";", 1)[0].strip()


def _error_from_response(resp: requests.Response) -> MeshAnythingAPIError:
    status = resp.status_code
    detail: str | None = None
    code = resp.headers.get("X-Error-Code")
    try:
        payload: Any = resp.json()
        if isinstance(payload, dict):
            raw = payload.get("detail")
            if isinstance(raw, str):
                detail = raw
            elif isinstance(raw, list) and raw:
                first = raw[0]
                if isinstance(first, dict) and "msg" in first:
                    detail = str(first.get("msg"))
                else:
                    detail = json.dumps(raw)
            if code is None:
                c = payload.get("code")
                code = c if isinstance(c, str) else code
            if detail is None and "message" in payload:
                detail = str(payload.get("message"))
    except Exception:
        detail = None

    if detail is None:
        detail = resp.text[:4000] if resp.text else f"HTTP {status}"

    msg = f"MeshAnything API error ({status}): {detail}"
    return MeshAnythingAPIError(msg, status_code=status, code=code, detail=detail)
