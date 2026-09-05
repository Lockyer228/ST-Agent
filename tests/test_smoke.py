"""Baseline smoke tests for the WP-01 runtime package."""

from pathlib import Path


def test_package_imports() -> None:
    import st_agent

    assert st_agent.__version__


def test_settings_load_without_credentials(monkeypatch) -> None:
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("ST_AGENT_MODEL_ID", "test-model")

    from st_agent.config import load_settings

    settings = load_settings()
    assert settings.aws_region == "us-west-2"
    assert settings.model_id == "test-model"


def test_settings_use_documented_defaults(monkeypatch) -> None:
    monkeypatch.delenv("ST_AGENT_MODEL_ID", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)

    from st_agent.config import DEFAULT_MODEL_ID, load_settings

    settings = load_settings()
    assert settings.model_id == DEFAULT_MODEL_ID
    assert settings.aws_region is None


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
