"""Canonical creative content. Serialization is not the authoring source."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from st_agent.domain.case import CardDelivery, LorebookDelivery


class DeliveryPreferences(BaseModel):
    character: CardDelivery = CardDelivery.json
    lorebook: LorebookDelivery = LorebookDelivery.none
    portrait_ref: str | None = None
    environment_constraints: str | None = None


class CaseBrief(BaseModel):
    experience_goal: str
    player_role: str
    characters: str
    world: str
    tone_and_boundaries: str
    mechanics: str
    information_reveals: str
    opening: str
    creative_authorization: str
    delivery: DeliveryPreferences = Field(default_factory=DeliveryPreferences)


class CharacterContent(BaseModel):
    name: str
    description: str
    personality: str
    scenario: str
    first_message: str
    example_dialogue: str = ""
    system_prompt: str = ""
    creator_notes: str = ""
    alternate_greetings: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    lorebook_relationship: str = ""


class LorebookEntry(BaseModel):
    entry_id: str
    title: str
    content: str
    keys: list[str] = Field(default_factory=list)
    secondary_keys: list[str] = Field(default_factory=list)
    constant: bool = False
    selective: bool = False
    insertion_order: int = 100
    position: str = "after_char"
    enabled: bool = True
    optional_activation: dict[str, Any] = Field(default_factory=dict)


class LorebookContent(BaseModel):
    name: str
    entries: list[LorebookEntry] = Field(default_factory=list)


class SourceOverlay(BaseModel):
    original_spec: str
    source_hash: str
    unknown_fields: dict[str, Any] = Field(default_factory=dict)
    merge_policy: str = "preserve_unknown"

    def merge(self, authored: dict[str, Any]) -> dict[str, Any]:
        merged = dict(self.unknown_fields)
        merged.update(authored)
        return merged

    def as_creative_text(self) -> str:
        return ""
