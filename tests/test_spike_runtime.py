"""S-01 wiring without claiming a live provider pass."""

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


def test_credential_probe_missing_key(monkeypatch) -> None:
    monkeypatch.setattr("st_agent.spike.load_local_env", lambda: None)
    monkeypatch.delenv("ST_AGENT_API_KEY", raising=False)
    monkeypatch.delenv("ST_AGENT_MODEL_ID", raising=False)
    monkeypatch.delenv("ST_AGENT_BASE_URL", raising=False)
    monkeypatch.delenv("ST_AGENT_PROVIDER", raising=False)

    from st_agent.config import DEFAULT_MODEL_ID

    status = credential_probe()
    assert status.available is False
    assert status.provider
    assert status.model_id == DEFAULT_MODEL_ID


def test_api_key_counts_as_credentials(monkeypatch) -> None:
    monkeypatch.setattr("st_agent.spike.load_local_env", lambda: None)
    monkeypatch.setenv("ST_AGENT_API_KEY", "fixture-key-not-a-secret")
    monkeypatch.setenv("ST_AGENT_PROVIDER", "openai-compatible")
    monkeypatch.setenv("ST_AGENT_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("ST_AGENT_MODEL_ID", "hy3")

    status = credential_probe()
    assert status.available is True
    assert status.provider == "openai-compatible"
    assert status.base_url == "https://api.example.com/v1"
    assert "fixture-key-not-a-secret" not in str(status)


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
