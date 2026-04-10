from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return default
    return v.strip()


@dataclass(frozen=True)
class ClientConfig:
    """Runtime configuration for the Space API client.

    Environment variables (optional defaults):
    - MESHANYTHING_API_BASE: e.g. https://your-space.hf.space
    - MESHANYTHING_API_KEY: shared studio secret (sent as Bearer, or as X-MeshAnything-Key if HF token is set)
    - MESHANYTHING_HF_TOKEN (or HF_TOKEN / HUGGING_FACE_HUB_TOKEN): Hugging Face user token for **private** Spaces
    - MESHANYTHING_TIMEOUT_SEC: total request timeout (default 600)

    Private Spaces: set ``hf_token`` so ``Authorization: Bearer <hf_token>`` reaches HF ingress.
    If you also use a studio API key on the server, it is sent as ``X-MeshAnything-Key`` so it does not
    collide with the HF token.
    """

    base_url: str
    api_key: str | None = None
    hf_token: str | None = None
    timeout_sec: float = 600.0

    def build_auth_headers(self) -> dict[str, str]:
        """Headers for GET/POST to the Space (health + optimize)."""
        headers: dict[str, str] = {}
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"
        if self.api_key:
            if self.hf_token:
                headers["X-MeshAnything-Key"] = self.api_key
            else:
                headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    @staticmethod
    def from_env() -> "ClientConfig":
        base = _env("MESHANYTHING_API_BASE")
        if not base:
            raise ValueError(
                "MESHANYTHING_API_BASE is not set (example: https://your-space.hf.space)"
            )
        base = base.rstrip("/")
        timeout_raw = _env("MESHANYTHING_TIMEOUT_SEC", "600")
        try:
            timeout_sec = float(timeout_raw) if timeout_raw is not None else 600.0
        except ValueError:
            timeout_sec = 600.0
        hf_token = (
            _env("MESHANYTHING_HF_TOKEN")
            or _env("HF_TOKEN")
            or _env("HUGGING_FACE_HUB_TOKEN")
        )
        return ClientConfig(
            base_url=base,
            api_key=_env("MESHANYTHING_API_KEY"),
            hf_token=hf_token,
            timeout_sec=timeout_sec,
        )
