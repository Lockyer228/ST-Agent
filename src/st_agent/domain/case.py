"""Typed case state. Files remain the recoverable authority."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Phase(StrEnum):
    setup = "setup"
    intake = "intake"
    qa = "qa"
    draft = "draft"
    final_text = "final_text"
    build = "build"
    official_check = "official_check"
    validate = "validate"
    delivery = "delivery"
    cleanup = "cleanup"


class Condition(StrEnum):
    active = "active"
    waiting_for_user = "waiting_for_user"
    blocked = "blocked"
    cleanup_pending = "cleanup_pending"


class CaseMode(StrEnum):
    new = "new"
    modify = "modify"


class CardDelivery(StrEnum):
    json = "json"
    png = "png"
    both = "both"


class LorebookDelivery(StrEnum):
    none = "none"
    standalone = "standalone"
    embedded = "embedded"
    both = "both"


class ArtifactRef(BaseModel):
    logical_id: str
    relative_path: str
    sha256: str
    kind: str
    valid: bool = True


class Lineage(BaseModel):
    source_hash: str
    artifact_hash: str | None = None
    stale: bool = False


class Blocker(BaseModel):
    code: str
    message: str
    retry_count: int = 0


class DeliveryPreference(BaseModel):
    card: CardDelivery = CardDelivery.json
    lorebook: LorebookDelivery = LorebookDelivery.none


class CaseManifest(BaseModel):
    schema_version: int = 1
    case_id: str
    story_name: str
    mode: CaseMode
    phase: Phase
    condition: Condition
    revision: int = 0
    operation_id: str
    delivery: DeliveryPreference = Field(default_factory=DeliveryPreference)
    inputs: list[ArtifactRef] = Field(default_factory=list)
    lineage: dict[str, Lineage] = Field(default_factory=dict)
    blocker: Blocker | None = None
    pending_question: str | None = None
    retry_count: int = 0
    last_error: str | None = None
