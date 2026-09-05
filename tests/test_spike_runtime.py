"""S-01 wiring without claiming a live Bedrock pass."""

from __future__ import annotations

from st_agent.outcomes import TurnOutcome
from st_agent.spike import bound_turns_hook, credential_probe, ping_runtime


def test_turn_outcome_schema() -> None:
    outcome = TurnOutcome(kind="question", message="Need the portrait file.")
    dumped = outcome.model_dump()
    assert dumped["kind"] == "question"
    assert dumped["message"].startswith("Need")
    assert dumped["artifact_refs"] == []


def test_ping_tool_is_project_owned() -> None:
    result = ping_runtime(note="spike")
    assert "spike" in result
    assert "st-agent" in result.lower() or "ok" in result.lower()


def test_credential_probe_does_not_expose_secrets() -> None:
    status = credential_probe()
    text = str(status)
    assert "AKIA" not in text
    assert "secret" not in text.lower()
    assert status.available is False or status.available is True
    assert status.region_source in {"env", "session", "unset", "sdk-default"}


def test_bound_turns_hook_cancels_after_limit() -> None:
    cancelled = {"n": 0}

    class _Agent:
        def cancel(self) -> None:
            cancelled["n"] += 1

    class _Event:
        def __init__(self, agent: _Agent) -> None:
            self.agent = agent

    agent = _Agent()
    hook = bound_turns_hook(max_tool_turns=1)
    hook(_Event(agent))
    assert cancelled["n"] == 1
