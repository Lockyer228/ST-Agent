"""Environment configuration for AWS region, model ID, and credentials."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_MODEL_ID = "global.anthropic.claude-sonnet-4-6"


@dataclass(frozen=True)
class RuntimeSettings:
    """Resolved runtime settings. Credentials stay in the AWS provider chain."""

    aws_region: str | None
    model_id: str


def load_settings() -> RuntimeSettings:
    """Read region and model ID from the environment. Never load secret files."""

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or None
    model_id = os.environ.get("ST_AGENT_MODEL_ID") or DEFAULT_MODEL_ID
    return RuntimeSettings(aws_region=region, model_id=model_id)
