"""Sanitized Strands hook events. No prompts, credentials, or hidden reasoning."""

from __future__ import annotations

import json

from strands.hooks import AfterInvocationEvent, AfterToolCallEvent, BeforeToolCallEvent

from st_agent.application.tools import TOOL_NAMES


def _tool_name(event: BeforeToolCallEvent | AfterToolCallEvent) -> str:
    if isinstance(event.tool_use, dict):
        return str(event.tool_use.get("name", "unknown"))
    return "unknown"


def _tool_failed(result: object) -> bool:
    if result is None:
        return False
    nested = getattr(result, "tool_result", None)
    if nested is not None and nested is not result:
        return _tool_failed(nested)
    if not isinstance(result, dict):
        return False
    inner = result.get("tool_result")
    if isinstance(inner, dict):
        return _tool_failed(inner)
    if result.get("ok") is False or result.get("status") == "error":
        return True
    for block in result.get("content") or []:
        if not isinstance(block, dict):
            continue
        payload = block.get("json")
        if isinstance(payload, dict) and payload.get("ok") is False:
            return True
        text = block.get("text")
        if not isinstance(text, str):
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and parsed.get("ok") is False:
            return True
    return False


class SanitizedHooks:
    def __init__(self) -> None:
        self.events: list[str] = []

    def before_tool(self, event: BeforeToolCallEvent) -> None:
        name = _tool_name(event)
        if name in TOOL_NAMES or name == "TurnOutcome":
            self.events.append(f"tool-start:{name}")

    def after_tool(self, event: AfterToolCallEvent) -> None:
        name = _tool_name(event)
        if name not in TOOL_NAMES and name != "TurnOutcome":
            return
        failed = event.exception is not None or _tool_failed(event.result)
        self.events.append(f"tool-failure:{name}" if failed else f"tool-success:{name}")

    def after_invocation(self, event: AfterInvocationEvent) -> None:
        self.events.append("invocation-complete")

    def as_list(self) -> list:
        return [self.before_tool, self.after_tool, self.after_invocation]
