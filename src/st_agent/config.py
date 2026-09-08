"""Environment configuration for the B-AI development model provider."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from st_agent.paths import source_root

DEFAULT_PROVIDER = "B-AI"
DEFAULT_BASE_URL = "https://api.b.ai/v1"
DEFAULT_MODEL_ID = "deepseek-v4-flash-0731"
AUTHORIZED_MODELS = ("deepseek-v4-flash-0731",)
_COLLAB_ENV = Path("project") / "Collaboration" / "b-ai-development-provider.env"


@dataclass(frozen=True)
class RuntimeSettings:
    """Resolved runtime settings. The API key stays in the environment only."""

    provider: str
    base_url: str
    model_id: str


def authorized_model_chain(preferred: str | None = None) -> tuple[str, ...]:
    """Return authorized models with an available preferred ID first."""

    if preferred in AUTHORIZED_MODELS:
        return (preferred,) + tuple(model for model in AUTHORIZED_MODELS if model != preferred)
    return AUTHORIZED_MODELS


def api_key() -> str | None:
    """Read ST_AGENT_API_KEY. Never log the value."""

    value = os.environ.get("ST_AGENT_API_KEY", "").strip()
    return value or None


def _apply_env_file(path: Path) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def load_local_env() -> Path | None:
    """Load collaboration env then gitignored `.env`. Never logs values."""

    last: Path | None = None
    root = source_root()
    for path in (root / _COLLAB_ENV, root / ".env"):
        if path.is_file():
            _apply_env_file(path)
            last = path
    return last


def load_settings() -> RuntimeSettings:
    """Read provider, base URL, and model ID from the environment."""

    return RuntimeSettings(
        provider=os.environ.get("ST_AGENT_PROVIDER") or DEFAULT_PROVIDER,
        base_url=os.environ.get("ST_AGENT_BASE_URL") or DEFAULT_BASE_URL,
        model_id=os.environ.get("ST_AGENT_MODEL_ID") or DEFAULT_MODEL_ID,
    )
