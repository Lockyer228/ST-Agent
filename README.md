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

Copy `.env.example` to `.env` for local defaults. `.env` is gitignored. Development credentials are loaded from `project/Collaboration/b-ai-development-provider.env` when that file is present (outside this Git tree).

| Variable | Purpose |
| --- | --- |
| `ST_AGENT_PROVIDER` | Development model provider. Default: `B-AI`. |
| `ST_AGENT_BASE_URL` | OpenAI-compatible API base URL. Default: `https://api.b.ai/v1`. |
| `ST_AGENT_MODEL_ID` | Model ID. Default: `hy3`. Authorized list: `hy3`, `mimo-v2.5`, `glm-5.3-flash`, `qwen3.8-flash`. Runtime falls back along that list. |
| `ST_AGENT_API_KEY` | B-AI API key. Local env only; never commit. |

Do not commit `.env`, API keys, or session tokens. Do not put secrets in case files, logs, or generated artifacts.

User content that later work packages send to B-AI is untrusted story material. The UI and this README will keep that dependency explicit.

## Run

```text
uv run streamlit run app.py
```

The shell starts a local Streamlit page. It shows the runtime version, provider, base URL, and model ID. It does not create cases or write user files.

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
- Case folders use the approved English layout (`00-work/` through `04-exports/`). `case.json` is the recoverable state; `status.md` is generated from it.
- Runtime English methods live in `src/st_agent/resources/methods/`. Canonical Markdown is the creative source; JSON is not.
- Format profiles, PNG chunk rules, and official-source allowlists live in `src/st_agent/resources/formats/`. Failed builds stay in `00-work/build/` until validators pass.
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
src/st_agent/resources/methods/  English Q&A, creation, and ST mapping rules
tests/                 Baseline smoke tests
docs/                  Approved engineering baseline
```
