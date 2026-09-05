# ST-Agent

ST-Agent is a local Python application for independent role-play creators, interactive-fiction writers, and narrative designers. It turns an English story idea and optional source files into a SillyTavern Character Card, an optional PNG Character Card from a user-provided Portrait, and a standalone or embedded Lorebook.

This repository is the **product source**. Shared planning and collaboration files live outside this Git tree.

**Acceptance platform:** Windows. Application paths use `pathlib` and avoid POSIX-only assumptions. Other operating systems are not promised without evidence.

This baseline provides install, configuration, test, static-check, and Streamlit shell entry points. Character-card and lorebook workflows are not implemented yet.

## Requirements

- Windows
- Python 3.12 (`python3.12`; do not use a Microsoft Store `python` alias)
- [uv](https://docs.astral.sh/uv/) 0.12 or later

## Setup

From the product source checkout:

```text
uv sync --group dev
```

This installs the locked runtime and development dependencies into `.venv`.

Editable install (not lock-pinned; prefer `uv sync`):

```text
uv pip install --python 3.12 -e .
```

Confirm the import:

```text
uv run python -c "import st_agent; print(st_agent.__version__)"
```

## Configuration

Copy `.env.example` to `.env` if you want local defaults. `.env` is gitignored and must never contain credentials.

| Variable | Purpose |
| --- | --- |
| `AWS_REGION` or `AWS_DEFAULT_REGION` | AWS region for Amazon Bedrock. No default is locked in this baseline. |
| `ST_AGENT_MODEL_ID` | Bedrock model ID. Default: `global.anthropic.claude-sonnet-4-6` (architecture starting point; later work may replace it after access, quality, latency, and cost checks). |
| `AWS_PROFILE` | Optional named profile for the standard AWS credential chain. |

Credentials use the **standard AWS provider chain** (environment, shared credentials file, or other chain sources). Do not write access keys, session tokens, or profiles into this repository, case files, logs, or generated artifacts.

User content that later work packages send to Bedrock is untrusted story material. The UI and this README will keep that dependency explicit.

## Run

```text
uv run streamlit run app.py
```

The shell starts a local Streamlit page. It shows the runtime version, configured region, and model ID. It does not create cases or write user files.

## Test

```text
uv run pytest
```

Baseline smoke tests cover package import, environment settings without credentials, `pathlib` application paths, and the Streamlit shell module.

## Static check

```text
uv run ruff check src tests app.py
```

## Data, paths, and cleanup

- Credentials, local workspaces, generated cases, internal planning, and private reference material stay outside runtime source and logs.
- This baseline does not write user case files and does not overwrite originals.
- Later work packages must keep user originals, preserve unrelated unknown fields, and write uniquely named outputs.
- Do not place a user workspace inside the application source tree.
- Debug logs must not include prompt bodies, uploaded content, credentials, or hidden reasoning.

## Engineering baseline

Approved architecture and project plan (C-029) are copied into `docs/` so this repository does not depend on sibling concept or planning files:

- `docs/TECHNICAL-ARCHITECTURE.md`
- `docs/project-plan.md`

## Repository layout

```text
app.py                 Streamlit entry
pyproject.toml         Python 3.12 project and exact tested lock (uv.lock)
src/st_agent/          Importable runtime package
tests/                 Baseline smoke tests
docs/                  Approved engineering baseline
```
