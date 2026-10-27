# Provider compatibility and limitations

Evidence date: **2026-10-26**. This table describes application behavior tested
with synthetic provider data. **No live model/provider is certified.** WP-050's
live acceptance and G6/M6 remain blocked: the user requested offline evidence only,
and this environment has no configured provider credential or paid-run authorization.
Offline authored interviews, simulation, reports and history remain independent.

The executable [matrix](../tests/fixtures/providers/acceptance-matrix.json) selects
all deterministic suites for `npm run test:providers`. That command runs Vitest
and the five Python contract/grounding/spending suites with no paid calls. The
broader unit checks and packaged-test limitations are recorded in the
[package evidence](roadmap/execution/WP-050.md). Synthetic `m`, `future/model`,
`synthetic/gpt` and loopback endpoints are fixtures, never real compatibility claims.

## Capability paths

“Supported locally” means implemented paths pass the cited synthetic tests;
provider/model availability, privacy promises and billing remain unverified.
“Unsupported” is an explicit application rejection, not a provider-wide assertion.
Every live row is **access-blocked / untested**; no live run date, selected model,
actual route, provider version, authorized cost ceiling or charge exists.

| Path | Local behavior and evidence | Live limitation |
|---|---|---|
| Keys and endpoint binding | Supported locally: temporary entry, replace/remove, protected-store abstraction or session-only, no redirect forwarding. `providers`, `provider-network`, `provider-isolation` suites | Native OS keychains and authenticated account limits untested here |
| Catalog, variants, search and cache | Supported locally: timestamps, pagination, unknown/removed capability metadata, offline cache and explicit refresh. `provider-adapters`, `provider-metadata`, `provider-generation` | Current catalog visibility does not establish model execution suitability |
| Routing and privacy | Supported locally: order/only/ignore, independent provider/model fallback, required parameters, deny/allow, ZDR, sort and price ceilings. Unsupported combinations fail before dispatch. `provider-requests`, `provider-acceptance` | Provider compliance with selected routing/privacy controls untested |
| Text generation | Supported locally: stream/nonstream, sampling/output controls, finish/refusal/partial results, selected and reported identity. `provider-requests`, `provider-stream`, `assistant` | Representative real stream/nonstream generation required |
| JSON object/schema | Supported locally: bounded schema subset, local validation and explicit invalid result. `provider-requests`, `provider-stream` | Server/model schema enforcement untested; grammar/Python response modes unsupported |
| Fragmented parallel tools | Supported locally: indexed fragments validated before execution, complete result sequencing, explicit continuation review, bounded 3 rounds / 8 calls. `provider-stream`, `grounding`, `provider-acceptance` | Real fragmented/parallel tool and continuation behavior untested |
| Reasoning and history | Supported locally: visible reasoning separated, compatible opaque history only on pinned identity/route; incompatible history needs a new request. `assistant-content`, `provider-requests`, `provider-stream` | Real model-specific reasoning controls and opaque history untested |
| Text attachments | Supported locally: explicit local UTF-8 excerpt, provenance, ownership and session deletion. `assistant-content`, `assistant` | No implicit history or file upload; attachment bytes enter only reviewed turns |
| PNG input | Supported locally only for registered GPT-4o accounting, low detail, at most 512×512. `assistant-content`, `provider-requests` | Real selected image-input model/provider required |
| WAV input/output | Supported locally only for declared OpenAI audio model paths: canonical mono PCM16 16 kHz input and streamed WAV output; bounded inert artifacts. `assistant-content`, `provider-stream` | Real modality negotiation/output untested; no autoplay/decoder |
| Video / PDF / image generation | Unsupported locally while trusted accounting or dedicated API integration is absent. Explicit rejection in `assistant-content`, `provider-requests` | A catalog modality flag cannot bypass these limits |
| Usage and spending | Supported locally: exact monetary observations, independent Python Decimal accounting, durable concurrent/continuation gates, late reconciliation and cancellation uncertainty. `assistant`, `provider-generation`, `provider-acceptance`, Python `test_spending` | Upstream charge/cancellation semantics and generation lookup untested |
| Errors and retries | Supported locally: auth/credits/rate/model/provider/redirect failures, malformed/partial SSE and safe redaction; no automatic generation retry. `assistant`, `provider-network`, `provider-stream` | Live account, quota and error behavior untested; cancellation cannot promise zero cost |
| Context, proposals and transcript ownership | Supported locally: immutable revision/scope, approved collections, fixed denied-result projection, explicit new inclusion, ordinary player Preview/Apply and independent deletion. `grounding`, `assistant`, `transcripts`, `provider-acceptance` | A successful live reply would not prove privacy, local gates or scientific validity |
| Generic OpenAI-compatible adapter | Discovery/settings and common request/response serialization tested. Routing/account endpoints are explicitly unsupported; discovered capabilities/context/tokenizer remain unknown, so production generation fails closed. `provider-adapters`, `provider-requests`, `provider-generation` | No generic endpoint/model is certified. A compatible `/models` listing cannot authorize execution |

Suite labels above refer to `tests/desktop/<label>.test.ts`. The machine matrix
contains full paths, including shared suites and explicit per-family live blockers.

## Official contract inspection

Retrieved [OpenRouter OpenAPI](https://openrouter.ai/openapi.json), API version
`1.0.0`, on 2026-10-26. Complete source SHA-256:
`385cedf846f292aeab67572de5ce4413786a5e323dc78ed32ad96ac363bb63ee`.
The checked-in [selected schema projection](../tests/fixtures/providers/openrouter-contract-2026-10-26.json)
retains literal provider preferences, chat field names and metadata routes.
It is a dated input to tests, not a claim of automatic future compatibility.

The current schema defines `provider.max_price` values as **strings**. The builder
now preserves decimal strings exactly, including zero and values that cannot
round-trip through a JavaScript number. Units remain USD per million prompt or
completion tokens, or per request/image. These route ceilings do not replace
local spending grants. The schema still lists `max_tokens` but deprecates it in
favor of `max_completion_tokens`; the existing capability-checked builder's
`max_tokens` path remains a documented compatibility limitation, not a silent
migration of saved settings.

The API schema is not exhaustive for every model-specific extension. The
[official reasoning guide](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)
was also retrieved on this date; reasoning budget/exclusion and opaque-history
support remain model-specific and fail closed when their required metadata is
missing. No undocumented field or catalog flag is treated as live proof.
An attempted obsolete chat-documentation URL returned HTTP 404; successful
OpenAPI and reasoning-guide retrievals are the contract evidence used here.

## Required live completion

No live test is part of `npm test`, `npm run test:providers`, CI or packaging.
No live request was made and no key was read for this delivery. To resume the
remaining parent, first obtain separate authorization for a concrete plan naming:

- Exact model IDs and provider routes suitable for each required capability,
  including text, tools/schema, reasoning, image and audio.
- A securely configured dedicated limited key, account credits and provider-side
  hard allowance; never place a key in chat, tracked files or command arguments.
- Maximum output/context, dispatch count, per-dispatch and total USD exposure,
  deadline and cancellation point, with no automatic paid retries.
- Synthetic prompt/attachment fixtures, explicit route/privacy preferences and
  isolated private runtime folder; no personal civilization data.

The separate authorized run must use production Electron transports, builder,
sharing and Python spending paths; capture only allowlisted outcomes/identities,
metadata observation time, provider/API/model versions where reported, cost and
unknowns. Inspect authenticated metadata, stream and nonstream text, schema,
parallel tools plus reviewed continuation, reasoning, supported modalities,
routing, usage lookup and cancellation. Record each capability as supported,
unsupported, failed, untested or access-blocked with its exact outcome. An
unavailable model, denied route, missing credits or unknown cost is an explicit
prerequisite/limit, never a passing result. The live harness and run remain part
of this blocked acceptance; no executable live-run command is claimed here.
