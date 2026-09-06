"""Scripted Strands model for fake-model integration tests."""

from __future__ import annotations

import json
import threading
from collections.abc import AsyncIterable
from typing import Any

from pydantic import BaseModel
from strands.models.model import Model
from strands.types.content import Messages, SystemContentBlock
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolChoice, ToolSpec


class ScriptedModel(Model):
    def __init__(self, steps: list[dict[str, Any]]) -> None:
        self.steps = list(steps)
        self.config: dict[str, Any] = {}

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self.config

    async def structured_output(
        self,
        output_model: type[BaseModel],
        prompt: Messages,
        system_prompt: str | None = None,
        **kwargs: Any,
    ):
        if not self.steps:
            yield {"output": output_model(kind="blocked", message="script exhausted")}
            return
        step = self.steps[0]
        if "outcome" in step:
            self.steps.pop(0)
            yield {"output": output_model.model_validate(step["outcome"])}

    async def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        *,
        tool_choice: ToolChoice | None = None,
        system_prompt_content: list[SystemContentBlock] | None = None,
        invocation_state: dict[str, Any] | None = None,
        cancel_signal: threading.Event | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[StreamEvent]:
        step = self.steps.pop(0) if self.steps else {"text": ""}
        yield {"messageStart": {"role": "assistant"}}
        if "tools" in step:
            for index, call in enumerate(step["tools"]):
                tool_id = str(call.get("id") or f"call-{index}")
                yield {
                    "contentBlockStart": {
                        "start": {"toolUse": {"name": call["name"], "toolUseId": tool_id}}
                    }
                }
                yield {
                    "contentBlockDelta": {
                        "delta": {"toolUse": {"input": json.dumps(call.get("input") or {})}}
                    }
                }
                yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            yield {"contentBlockStart": {"start": {}}}
            yield {"contentBlockDelta": {"delta": {"text": str(step.get("text") or "")}}}
            yield {"contentBlockStop": {}}
            if "outcome" in step:
                payload = step["outcome"]
                yield {
                    "contentBlockStart": {
                        "start": {"toolUse": {"name": "TurnOutcome", "toolUseId": "outcome"}}
                    }
                }
                yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(payload)}}}}
                yield {"contentBlockStop": {}}
                yield {"messageStop": {"stopReason": "tool_use"}}
            else:
                yield {"messageStop": {"stopReason": "end_turn"}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
                "metrics": {"latencyMs": 1},
            }
        }
