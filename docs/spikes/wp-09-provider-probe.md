# WP-09 provider mini-probe

Recorded 2026-09-08 on the Windows implementation host. No API keys.

Driver: `docs/spikes/wp-09-provider-probe.py`. Each authorized model is pinned
for one Strands invocation that must call `ping_alpha` then `ping_beta`, then
return a `TurnOutcome`. Client timeout 40s; cancel 45s. JSON:
`docs/spikes/wp-09-provider-probe.json`.

## Verdict

**not-provider-limited.** Three models completed a multi-tool Chat Completions
loop. Continue WP-09 live retry (timeout, canonical-save bound, manifest
recovery). Do not switch providers.

## Results

| Model | Status | Wall clock | Tokens in/out | Custom tools | `reasoningContent` |
| --- | --- | --- | --- | --- | --- |
| `hy3` | pass | 11.907s | 1785 / 324 | alpha, beta, TurnOutcome | warning, not fatal (3 log lines) |
| `mimo-v2.5` | error `EventLoopException` / `APIError` "Upstream request failed" | 15.765s | — | alpha and beta completed; structured output request failed | warning, not fatal |
| `glm-5.3-flash` | pass | 24.884s | 1030 / 717 | alpha+beta parallel then TurnOutcome | warning, not fatal (1 log line) |
| `qwen3.8-flash` | pass | 17.456s | 3099 / 565 | alpha, beta, TurnOutcome x2 | warning, not fatal (6 log lines) |

Reliable models: `hy3`, `glm-5.3-flash`, `qwen3.8-flash`.

## Alibaba-Token / `deepseek-v4-flash-0731` (2026-09-08)

User authorized a single-model live chain. OpenAI-compatible base URL only (no key in this file). JSON: `wp-09-provider-probe-deepseek.json`.

| Model | Status | Wall clock | Tokens in/out | Custom tools | `reasoningContent` |
| --- | --- | --- | --- | --- | --- |
| `deepseek-v4-flash-0731` | pass | 8.862s | 2321 / 523 | alpha, beta, TurnOutcome | warning, not fatal (3 log lines) |

Verdict: **usable**. Multi-tool Chat Completions loop completed. Authorized product chain is this model only (`AUTHORIZED_MODELS`).

## Notes

- the model provider accepted tool-result follow-up messages on every model that reached a
  second completion. `mimo-v2.5` failed on a later upstream call, not on the
  first tool round-trip.
- `reasoningContent is not supported in multi-turn conversations with the Chat
  Completions API` is a Strands log warning. Passing models still returned a
  valid `TurnOutcome`.
- Prior WP-09 glm run with no tool events was the full product prompt under a
  shared 90s budget, not an inability to emit `tool_use`. This mini-probe
  shows glm does call tools on a short instruction.
