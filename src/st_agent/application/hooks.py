"""Sanitized Strands hook events. No prompts, credentials, or hidden reasoning."""

from __future__ import annotations

import json
from collections.abc import Callable

from strands.hooks import AfterInvocationEvent, AfterToolCallEvent, BeforeToolCallEvent

from st_agent.application.tools import TOOL_NAMES


def _tool_name(event: BeforeToolCallEvent | AfterToolCallEvent) -> str:
    if isinstance(event.tool_use, dict):
        return str(event.tool_use.get("name", "unknown"))
    return "unknown"


def _envelope_code(result: object) -> str | None:
    if result is None:
        return None
    nested = getattr(result, "tool_result", None)
    if nested is not None and nested is not result:
        return _envelope_code(nested)
    if not isinstance(result, dict):
        return None
    inner = result.get("tool_result")
    if isinstance(inner, dict):
        code = _envelope_code(inner)
        if code:
            return code
    code = result.get("code")
    if result.get("ok") is False and isinstance(code, str) and code:
        return code
    for block in result.get("content") or []:
        if not isinstance(block, dict):
            continue
        payload = block.get("json")
        if isinstance(payload, dict) and payload.get("ok") is False:
            inner_code = payload.get("code")
            if isinstance(inner_code, str) and inner_code:
                return inner_code
        text = block.get("text")
        if not isinstance(text, str):
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and parsed.get("ok") is False:
            inner_code = parsed.get("code")
            if isinstance(inner_code, str) and inner_code:
                return inner_code
    return None


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
    def __init__(self, event_sink: Callable[[str], None] | None = None) -> None:
        self.events: list[str] = []
        self._sink = event_sink

    def _emit(self, event: str) -> None:
        self.events.append(event)
        if self._sink is not None:
            self._sink(event)

    def before_tool(self, event: BeforeToolCallEvent) -> None:
        name = _tool_name(event)
        if name in TOOL_NAMES or name == "TurnOutcome":
            self._emit(f"tool-start:{name}")

    def after_tool(self, event: AfterToolCallEvent) -> None:
        name = _tool_name(event)
        if name not in TOOL_NAMES and name != "TurnOutcome":
            return
        failed = event.exception is not None or _tool_failed(event.result)
        if failed:
            code = _envelope_code(event.result)
            suffix = f":{code}" if code else ""
            self._emit(f"tool-failure:{name}{suffix}")
        else:
            self._emit(f"tool-success:{name}")

    def after_invocation(self, event: AfterInvocationEvent) -> None:
        self._emit("invocation-complete")

    def as_list(self) -> list:
        return [self.before_tool, self.after_tool, self.after_invocation]
