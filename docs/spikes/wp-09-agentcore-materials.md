# AgentCore go/no-go materials (WP-09)

This file prepares facts for a later user decision. It is not a go or no-go.

## What local P0 already is

- Single-process Windows Streamlit app
- User-selected local case folders as the only recoverable task site
- B-AI over an OpenAI-compatible API
- Eight project-owned tools; no unrestricted filesystem, HTTP, or shell tools
- No database, worker queue, custom API server, multi-agent graph, MCP server, or container platform

Architecture section 1 states P0 does not require AgentCore deployment.

## What an AgentCore move would change

- Hosting and process model (no longer "one local Streamlit process")
- Credential handling (today: `ST_AGENT_API_KEY` in local env only)
- Workspace authority (today: the user-selected folder on disk)
- Network surface and operator model

None of those changes are in WP-09.

## Gate that must pass first

Local release gate **G-07** (fresh Windows install, README, architecture diagram, representative case, expected artifacts) is the P0 package. The user may consider AgentCore only after that gate is recorded as pass or as an explicit pending-condition. This package does not decide.
