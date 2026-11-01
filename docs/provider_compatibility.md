# Provider compatibility and limitations

Evidence date: **2026-11-01**. The production guardrailed OpenRouter setup passes
bounded live validation with `z-ai/glm-5.3-flash`, automatic provider selection,
no model fallback and actual route `Z.AI`. The existing key/configuration works;
no manual provider pin is required for the tested agentic loop. See the
[dated live review](roadmap/execution/WP-055-live-review.json),
[run instructions and allocation](provider_live_validation.md), and
[executable matrix](../tests/fixtures/providers/acceptance-matrix.json).

The matrix selects all deterministic suites for `npm run test:providers`.
Synthetic `m`, `future/model`, `synthetic/gpt` and loopback endpoints are fixtures.
The final live JUnit was source/hash verified before later test/docs-only edits;
original reports and failed attempts remain separately retained.

| Path | Current evidence | Limits |
|---|---|---|
| Keys/metadata | Native catalog, authenticated key/catalog/endpoints/account metadata, session-only key removal pass live | Real OS keychains remain owner-run |
| Routing | Exact selected GLM model; OpenRouter chooses within key guardrails; no fallback; explicit price/privacy controls | Remote privacy promises and all other routing combinations are not independently certified |
| Generation | Nonstream/stream identity and finish handling pass live | Other models/providers remain untested |
| Structured output | JSON object returned and validated live; strict schema correctly rejected from authenticated capability metadata | No live strict-schema enforcement claim for this route |
| Tools | Real selected-fact retrieval and separately approved completed continuation pass live using `auto` | Fragmented/parallel calls have deterministic integration coverage; forced-function/none modes are not advertised by Z.AI |
| Reasoning/history | Low effort accepted; standardized unsigned text/summary can continue on the exact model with automatic routing; real-controller/Python regression verifies preservation | Encrypted, signed, native-reference and unknown formats remain affinity-bound. Final visible reasoning absent; earlier tool response reported 59 reasoning tokens |
| Usage | Canonical snapshot alias reconciles through the fresh selected catalog row; actual cost is durable; unrelated IDs reject | Cancelled/failed upstream charges remain uncertain; no aggregate actual-cost claim |
| Cancellation/failures | Live abort/key removal pass; actual 404/502 failures retained with safe diagnostics | Auth/credit/rate/redirect injection remains deterministic; cancellation does not promise zero cost |
| Context/proposals | Live synthetic selected facts/tools plus actual-service sharing and SQLite reservation regressions | Private/other-branch canaries, proposals and concurrent grants use synthetic controlled sinks; generated text never commits game state |
| Modalities | Explicit bounded local attachment/media paths retain deterministic tests | GLM image/video accounting and live media unvalidated; audio unsupported. No implicit media fallback |
| Generic compatible endpoints | Discovery/common serialization; unsupported routing/account/context stays explicit | No generic endpoint/model is certified |

Numeric endpoint `discount` annotations stay in raw metadata and do not become
billable token rates. Empty provider lists are omitted. Strict tool schemas are
requested only when advertised; all arguments still undergo local schema and
sharing validation. The complete workflow uses production Electron networking,
controllers, Python and SQLite, rather than substituting a Node HTTP provider.

## Contract and model evidence

The pinned [OpenRouter OpenAPI projection](../tests/fixtures/providers/openrouter-contract-2026-10-26.json)
was retrieved on 2026-10-26, API version `1.0.0`, full source SHA-256
`385cedf846f292aeab67572de5ce4413786a5e323dc78ed32ad96ac363bb63ee`.
A 2026-11-01 repeat full OpenAPI fetch returned HTTP 403; it is not reported as a
fresh schema retrieval. Current native/authenticated metadata and live requests
verify the exercised field/endpoint behavior. Model-specific metadata, including
canonical snapshot aliases and tool-choice submodes, remains authoritative.

`provider.max_price` strings preserve exact USD/M-token or per-request ceilings.
The still-supported, capability-checked `max_tokens` field remains an explicit
compatibility choice; saved settings are not silently migrated. Context bounds
are separately reviewed in [provider context bounds](provider_context_bounds.md).
Catalog visibility alone cannot authorize execution or establish scientific value.

The final lifetime allocation retains all 24 dispatches and exactly USD 10 maximum
reserved exposure, including failed/cancelled attempts. It is exhausted. Ordinary
tests/CI/packaging make no paid requests and do not require a provider key.
