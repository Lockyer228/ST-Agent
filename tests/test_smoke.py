"""Baseline smoke tests for the WP-01 runtime package."""

import os
from pathlib import Path


def test_package_imports() -> None:
    import st_agent

    assert st_agent.__version__


def test_settings_load_from_env(monkeypatch) -> None:
    monkeypatch.setenv("ST_AGENT_PROVIDER", "openai-compatible")
    monkeypatch.setenv("ST_AGENT_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("ST_AGENT_MODEL_ID", "mimo-v2.5")

    from st_agent.config import load_settings

    settings = load_settings()
    assert settings.provider == "openai-compatible"
    assert settings.base_url == "https://api.example.com/v1"
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
    assert settings.model_id == DEFAULT_MODEL_ID == "deepseek-v4-flash-0731"
    assert settings.provider == DEFAULT_PROVIDER
    assert settings.base_url == DEFAULT_BASE_URL


def test_authorized_model_chain_starts_with_preferred() -> None:
    from st_agent.config import AUTHORIZED_MODELS, authorized_model_chain

    assert AUTHORIZED_MODELS == ("deepseek-v4-flash-0731",)
    assert authorized_model_chain("deepseek-v4-flash-0731") == AUTHORIZED_MODELS
    assert authorized_model_chain("unknown") == AUTHORIZED_MODELS


def test_load_local_env_reads_collaboration_file(tmp_path, monkeypatch) -> None:
    collab = tmp_path / "project" / "Collaboration"
    collab.mkdir(parents=True)
    (collab / "local-development-provider.env").write_text(
        "ST_AGENT_API_KEY=fixture-only\nST_AGENT_MODEL_ID=hy3\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("st_agent.config.source_root", lambda: tmp_path)
    monkeypatch.delenv("ST_AGENT_API_KEY", raising=False)
    monkeypatch.delenv("ST_AGENT_MODEL_ID", raising=False)

    from st_agent.config import load_local_env

    load_local_env()
    try:
        assert os.environ["ST_AGENT_API_KEY"] == "fixture-only"
        assert os.environ["ST_AGENT_MODEL_ID"] == "hy3"
    finally:
        os.environ.pop("ST_AGENT_API_KEY", None)
        os.environ.pop("ST_AGENT_MODEL_ID", None)


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


def test_windows_start_script_runs_streamlit_from_checkout() -> None:
    from st_agent.paths import source_root

    path = source_root() / "start-st-agent.cmd"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "cd /d \"%~dp0\"" in text
    assert "streamlit run app.py" in text
    assert "127.0.0.1:8501" in text
    assert "ST_AGENT_API_KEY" not in text
    assert "D:\\Projects" not in text
