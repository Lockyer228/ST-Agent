"""WP-09 Step 0: per-model mini-probe for a multi-tool Chat Completions loop.

Pins one authorized model at a time. Does not print secrets.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

from strands import Agent, tool
from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent
from strands.models.openai import OpenAIModel

from st_agent.config import AUTHORIZED_MODELS, api_key, load_local_env, load_settings
from st_agent.outcomes import TurnOutcome

LOG_PATH = Path(
    os.environ.get("ST_AGENT_WP09_PROBE_LOG") or Path(__file__).with_name("wp-09-provider-probe.json")
)
TIMEOUT_S = 45.0
CLIENT_TIMEOUT_S = 40.0


@tool
def ping_alpha(note: str) -> str:
    return f"alpha:{note}"


@tool
def ping_beta(note: str) -> str:
    return f"beta:{note}"


def _tool_name(event: BeforeToolCallEvent | AfterToolCallEvent) -> str:
    if isinstance(event.tool_use, dict):
        return str(event.tool_use.get("name", "unknown"))
    return "unknown"


def _redact(text: str, secret: str | None) -> str:
    if not secret or not text:
        return text
    return text.replace(secret, "[redacted]")


def probe_model(model_id: str, *, base_url: str, key: str) -> dict[str, object]:
    events: list[str] = []
    warnings: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            msg = record.getMessage()
            if "reasoningContent" in msg or record.levelno >= logging.WARNING:
                warnings.append(_redact(f"{record.levelname}:{msg}", key)[:300])

    handler = _Capture()
    handler.setLevel(logging.WARNING)
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        def before_tool(event: BeforeToolCallEvent) -> None:
            events.append(f"tool-start:{_tool_name(event)}")

        def after_tool(event: AfterToolCallEvent) -> None:
            events.append(f"tool-end:{_tool_name(event)}")

        signal = threading.Event()
        timer = threading.Timer(TIMEOUT_S, signal.set)
        timer.daemon = True
        timer.start()
        agent = Agent(
            model=OpenAIModel(
                client_args={"api_key": key, "base_url": base_url, "timeout": CLIENT_TIMEOUT_S},
                model_id=model_id,
            ),
            tools=[ping_alpha, ping_beta],
            system_prompt=(
                "Call ping_alpha with note=one, then ping_beta with note=two. "
                "Then return kind=blocked with message naming both tool results. "
                "Do not claim delivery."
            ),
            structured_output_model=TurnOutcome,
            hooks=[before_tool, after_tool],
            callback_handler=None,
        )
        started = time.perf_counter()
        try:
            result = agent(
                "Prove a multi-tool loop and return a TurnOutcome.",
                structured_output_model=TurnOutcome,
                limits={"turns": 6},
                cancel_signal=signal,
            )
            elapsed = round(time.perf_counter() - started, 3)
            outcome = result.structured_output
            usage = getattr(getattr(result, "metrics", None), "accumulated_usage", None) or {}
            custom_ends = [e for e in events if e.startswith("tool-end:ping_")]
            row = {
                "model_id": model_id,
                "status": "pass" if len(custom_ends) >= 2 and outcome is not None else "fail",
                "stop_reason": str(result.stop_reason),
                "events": events,
                "kind": getattr(outcome, "kind", None),
                "message": _redact(getattr(outcome, "message", None) or "", key)[:400],
                "elapsed_s": elapsed,
                "input_tokens": usage.get("inputTokens"),
                "output_tokens": usage.get("outputTokens"),
                "tool_use_emitted": any(e.startswith("tool-start:ping_") for e in events),
                "multi_tool_loop": len(custom_ends) >= 2,
                "reasoning_content_warnings": [
                    w for w in warnings if "reasoningContent" in w
                ],
                "other_warnings": [w for w in warnings if "reasoningContent" not in w][:8],
            }
        except Exception as exc:
            elapsed = round(time.perf_counter() - started, 3)
            row = {
                "model_id": model_id,
                "status": "error",
                "error_type": type(exc).__name__,
                "error": _redact(str(exc), key)[:400],
                "events": events,
                "elapsed_s": elapsed,
                "tool_use_emitted": any(e.startswith("tool-start:ping_") for e in events),
                "multi_tool_loop": False,
                "reasoning_content_warnings": [
                    w for w in warnings if "reasoningContent" in w
                ],
                "other_warnings": [w for w in warnings if "reasoningContent" not in w][:8],
            }
        finally:
            timer.cancel()
        return row
    finally:
        root.removeHandler(handler)


def main() -> int:
    load_local_env()
    settings = load_settings()
    key = api_key()
    record: dict[str, object] = {
        "provider": settings.provider,
        "base_url": settings.base_url,
        "key_present": key is not None,
        "timeout_s": TIMEOUT_S,
        "models": [],
        "verdict": "not-started",
    }
    if key is None:
        record["verdict"] = "pending-condition"
        LOG_PATH.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print("pending-condition: ST_AGENT_API_KEY is missing")
        return 2

    models: list[dict[str, object]] = []
    for model_id in AUTHORIZED_MODELS:
        print(f"probe {model_id} ...", flush=True)
        row = probe_model(model_id, base_url=settings.base_url, key=key)
        models.append(row)
        print(
            f"  status={row.get('status')} tools={row.get('events')} "
            f"elapsed_s={row.get('elapsed_s')}",
            flush=True,
        )
    record["models"] = models
    reliable = [m["model_id"] for m in models if m.get("status") == "pass"]
    any_tool = [m["model_id"] for m in models if m.get("tool_use_emitted")]
    if reliable:
        record["verdict"] = "not-provider-limited"
    elif any_tool:
        record["verdict"] = "partial-tool-use"
    else:
        record["verdict"] = "provider-limited"
    record["reliable_models"] = reliable
    LOG_PATH.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"verdict={record['verdict']} reliable={reliable}")
    return 0 if reliable else 1


if __name__ == "__main__":
    raise SystemExit(main())
