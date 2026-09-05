"""Baseline smoke tests for the WP-01 runtime package."""

import os
from pathlib import Path


def test_package_imports() -> None:
    import st_agent

    assert st_agent.__version__


def test_settings_load_from_env(monkeypatch) -> None:
    monkeypatch.setenv("ST_AGENT_PROVIDER", "B-AI")
    monkeypatch.setenv("ST_AGENT_BASE_URL", "https://api.b.ai/v1")
    monkeypatch.setenv("ST_AGENT_MODEL_ID", "mimo-v2.5")

    from st_agent.config import load_settings

    settings = load_settings()
    assert settings.provider == "B-AI"
    assert settings.base_url == "https://api.b.ai/v1"
    assert settings.model_id == "mimo-v2.5"
    assert not hasattr(settings, "api_key")


def test_settings_use_documented_defaults(monkeypatch) -> None:
    monkeypatch.delenv("ST_AGENT_MODEL_ID", raising=False)
    monkeypatch.delenv("ST_AGENT_PROVIDER", raising=False)
    monkeypatch.delenv("ST_AGENT_BASE_URL", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)

    from st_agent.config import DEFAULT_BASE_URL, DEFAULT_MODEL_ID, DEFAULT_PROVIDER, load_settings

    settings = load_settings()
    assert settings.model_id == DEFAULT_MODEL_ID == "hy3"
    assert settings.provider == DEFAULT_PROVIDER
    assert settings.base_url == DEFAULT_BASE_URL


def test_authorized_model_chain_starts_with_preferred() -> None:
    from st_agent.config import AUTHORIZED_MODELS, authorized_model_chain

    assert AUTHORIZED_MODELS == ("hy3", "mimo-v2.5", "glm-5.3-flash", "qwen3.8-flash")
    assert authorized_model_chain("glm-5.3-flash")[0] == "glm-5.3-flash"
    assert set(authorized_model_chain("glm-5.3-flash")) == set(AUTHORIZED_MODELS)
    assert authorized_model_chain("unknown") == AUTHORIZED_MODELS


def test_load_local_env_reads_collaboration_file(tmp_path, monkeypatch) -> None:
    collab = tmp_path / "project" / "Collaboration"
    collab.mkdir(parents=True)
    (collab / "b-ai-development-provider.env").write_text(
        "ST_AGENT_API_KEY=fixture-only\nST_AGENT_MODEL_ID=hy3\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("st_agent.config.source_root", lambda: tmp_path)
    monkeypatch.delenv("ST_AGENT_API_KEY", raising=False)
    monkeypatch.delenv("ST_AGENT_MODEL_ID", raising=False)

    from st_agent.config import load_local_env

    load_local_env()
    assert os.environ["ST_AGENT_API_KEY"] == "fixture-only"
    monkeypatch.delenv("ST_AGENT_API_KEY", raising=False)


def test_application_paths_are_pathlib() -> None:
    from st_agent.paths import package_dir, source_root

    pkg = package_dir()
    root = source_root()
    assert isinstance(pkg, Path)
    assert isinstance(root, Path)
    assert pkg.is_dir()
    assert (root / "pyproject.toml").is_file()


def test_streamlit_shell_module_imports() -> None:
    from st_agent.ui import app

    assert callable(app.main)
