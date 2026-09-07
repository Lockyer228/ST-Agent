# ST-Agent

ST-Agent is a local Windows Python application for independent role-play creators, interactive-fiction writers, and narrative designers. It turns an English story idea and optional source files into a SillyTavern Character Card, an optional PNG Character Card from a user-provided portrait, and a standalone and/or embedded Lorebook.

This repository is the **product source**. Shared planning files live outside this Git tree.

**Acceptance platform:** Windows. Application paths use `pathlib` and avoid POSIX-only assumptions. Other operating systems are not promised without evidence.

## Target creator

The intended user is a single local creator who already writes in American English and wants SillyTavern-ready files without a hosted service. The app is not a multi-user studio, not a cloud agent platform, and not a replacement for SillyTavern itself.

## Architecture

One Streamlit process owns the UI and the agent. The one-page UI (New / Resume / Send / downloads) calls `submit_turn` only. The case controller persists the user turn, runs a fresh Strands agent against B-AI, and binds eight tools: `save_brief`, `save_content_document`, `build_character_card`, `build_lorebook`, `build_png_card`, `check_official_sources`, `validate_deliverables`, and `finish_case`. Case state lives in the user-selected folder (`case.json`). File locks, atomic writes, crash `.tmp` files, and close/abandon hygiene recover work. Delivery is gated: a model text claim cannot skip missing or invalid artifacts.

See `docs/TECHNICAL-ARCHITECTURE.md` for the system diagram.

## Requirements

- Windows
- Python 3.12 (`python3.12`; do not use a Microsoft Store `python` alias)
- [uv](https://docs.astral.sh/uv/) 0.12 or later
- A B-AI API key in the environment (`ST_AGENT_API_KEY`)

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

Pinned versions used for this release candidate are recorded in `uv.lock`. Runtime packages include `strands-agents==1.54.0`, `streamlit==1.63.0`, `pydantic==2.13.5`, `pillow==12.3.0`, and `httpx==0.28.1`. Dev tools include `pytest==9.1.1` and `ruff==0.16.6`.

## Configuration

Copy `.env.example` to `.env` for local defaults. `.env` is gitignored. Development credentials are loaded from `project/Collaboration/b-ai-development-provider.env` when that file is present (outside this Git tree).

| Variable | Purpose |
| --- | --- |
| `ST_AGENT_PROVIDER` | Development model provider. Default: `B-AI`. |
| `ST_AGENT_BASE_URL` | OpenAI-compatible API base URL. Default: `https://api.b.ai/v1`. |
| `ST_AGENT_MODEL_ID` | Preferred model ID. Default: `hy3`. Authorized chain: `hy3`, `mimo-v2.5`, `glm-5.3-flash`, `qwen3.8-flash`. Runtime tries that list in order until one call succeeds. |
| `ST_AGENT_API_KEY` | B-AI API key. Local env only; never commit. |

Do not commit `.env`, API keys, or session tokens. Do not put secrets in case files, logs, or generated artifacts.

Story text and uploads are sent to B-AI. Keep that dependency explicit.

## Supported inputs

Content is sniffed from bytes. File extensions are not trusted.

| Accepted | Notes |
| --- | --- |
| UTF-8 text / Markdown | Story drafts and notes |
| JSON | Existing character cards or lorebooks |
| PNG, JPEG, WebP, BMP | Portraits; PNG with `chara`/`ccv3` chunks is treated as an existing card |
| Existing SillyTavern card JSON or PNG | Modification cases merge unknown fields as overlay |

| Rejected | Reason |
| --- | --- |
| GIF, TIFF, HEIC, SVG | Not in the image codec set |
| PDF, Word, ZIP, 7z, RAR | Archives and office documents are not accepted |
| Damaged JSON or image bytes | English error; the original file is not overwritten |

Limits: 10 files, 2 MiB per text file, 20 MiB per image, 16 megapixels, 50 MiB total.

## Data handling

- Case files live in a user-chosen workspace folder. The app does not overwrite user originals.
- Do not place a user workspace inside the application source tree.
- Case folders use the English layout `00-work/` through `04-exports/`. `00-work/case.json` is the recoverable state; `status.md` is generated from it.
- Exports land under `04-exports/character-cards/card.json`, `04-exports/png-cards/card.png`, and `04-exports/lorebooks/lorebook.json` when those deliveries were requested and validated.
- Closed-case downloads follow the `Deliverables:` list in the case `README.md`. Paths outside `04-exports/` are rejected.
- Close and abandon remove temporary work files. Deliverables stay on disk.
- Debug logs must not include prompt bodies, uploaded content, credentials, or hidden reasoning.

## Limitations

- Local single-user Windows demo. No accounts, no multi-case cloud memory, no AgentCore deployment in this package.
- American English product and generated text. CJK in product files is out of scope.
- PNG delivery requires a user-provided portrait. The app does not invent an image.
- One live model invocation is bounded (about 90 seconds and a small turn budget). Long jobs continue with Resume / another Send. Default `hy3` may spend that budget on canonical-document repair and B-AI Chat Completions `reasoningContent` warnings; authorized fallback only starts if the first model fails before the budget ends.
- Official format checks use a small allowlisted URL set. A source change blocks delivery until the local profile is updated.
- Ordinary user cases are not imported into SillyTavern as a project gate. Frozen golden fixtures in `tests/fixtures/golden` are the project-level format suite.

## Run

```text
uv run streamlit run app.py
```

The shell starts a local Streamlit page.

1. Choose a workspace folder that is not inside this repository.
2. **New**: enter a story name. Optionally check modify-mode if you will upload an existing card.
3. **Send** a message (and optional files). Story text goes to B-AI. Watch sanitized tool events (`tool-start` / `tool-success` / `tool-failure`).
4. Answer one question when the case is waiting, or **Resume** after an interruption.
5. When delivery is gated and the case closes, download files listed under Deliverables.
6. **Abandon** drops the case without claiming success. **New modification** starts a follow-up case from a delivered card.

A scripted representative case (same `submit_turn` path as Send) lives in `docs/spikes/wp-09-run-case.py`. Input and expected artifacts are in `docs/spikes/wp-09-case-input.md`.

## Test

```text
uv run pytest
```

```text
uv run ruff check src tests app.py
```

Live B-AI smoke (`tests/test_wp06_smoke.py`) skips when `ST_AGENT_API_KEY` is absent.

## Engineering baseline

Approved architecture and project plan (C-029) are copied into `docs/` so this repository does not depend on sibling concept or planning files:

- `docs/TECHNICAL-ARCHITECTURE.md`
- `docs/project-plan.md`

## Repository layout

```text
app.py                 Streamlit entry
pyproject.toml         Python 3.12 project and exact tested lock (uv.lock)
src/st_agent/          Importable runtime package
src/st_agent/ui/       One-page Streamlit UI and Streamlit-free view helpers
src/st_agent/application/  Case controller, eight tools, hooks
src/st_agent/resources/methods/  English Q&A, creation, and ST mapping rules
tests/                 Unit, integration, golden, and UI AppTest suites
docs/                  Approved engineering baseline and spike evidence
```
