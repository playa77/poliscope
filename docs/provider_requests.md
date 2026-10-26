# Provider request construction and output validation

WP-044 supplies a pure TypeScript request builder and response normalizer in
Electron main. It does not dispatch, obtain a key, authorize disclosure/spending,
retry, execute tools, apply proposals or mutate society history. WP-045 owns the
network/fragmented SSE lifecycle; WP-046 and WP-048 supply sharing and spend gates.
`stream: true` and `false` construct the documented request bodies; the normalizer
accepts complete nonstreamed replies or a completed response assembled by the
future stream consumer. Partial chunks must never be passed as a completed reply.

Canonical Python generation-plan v1 definitions generate JSON Schema/TypeScript.
They are schema definitions only, with no Python generation command. Existing
provider settings v1 remain cold-readable: new controls are optional; older
profiles acquire no model fallback, price ceiling, ZDR or reasoning choice.
The settings UI saves the controls separately from keys. Selection is a preference,
not proof of support. It never triggers generation or another billable call.

## Construction contract

`buildGenerationRequest(view, plan, evidence, now)` returns an immutable request
containing the fixed POST `/chat/completions` route, canonical endpoint, serialized
body, selected/allowed model IDs and the inspected input. It accepts no header,
credential, arbitrary HTTP method, URL override or send callback. The caller must
revalidate the saved profile revision and all gates immediately before dispatch;
a previously built request is not an authorization token.

Main-owned evidence binds profile, canonical endpoint, revision and each model.
Models must be listed, observed within 24 hours (not in the future), have explicit
text input/output support and known context/completion limits. Saved declarations
cannot turn unknown catalog capabilities into support. Unsupported/unknown chosen
parameters, tools, schema output and reasoning reject. No hardcoded model enum.
Every explicit fallback must pass the complete validation independently.

Token budget receipts bind the exact messages, tool descriptions/schemas and
response format to a model with SHA-256. They contain an input-token upper bound
from a trusted tokenizer or documented conservative model bound. Missing/changed
receipts, unknown limits, oversized completions or input-plus-output exceeding
context reject. This package does not invent a universal tokenizer or equate byte
length with token count. Future main consumers must supply trustworthy receipts;
renderer estimates and catalog visibility do not constitute them. Input in this
package is bounded text messages plus tool definitions; attachment processing and
tool-result continuations are later consumers, not implicitly enabled modalities.

OpenRouter provider `order`, `only`, `ignore`, `allow_fallbacks`,
`require_parameters`, `data_collection`, `zdr`, simple `sort` and `max_price` are
encoded without dropping explicit choices. Unspecified data collection/ZDR remain
omitted; they are not assurances of privacy. Contradictory provider lists, duplicate
models, order combined with sort and disabled parameter enforcement with selected
controls reject. The caller can resolve the conflict; the builder never relaxes it.
Provider fallback permits another provider for the same model. Only the separately
saved ordered `model_fallbacks` list permits another model; it encodes `models`
in primary-first order. No client retry or implicit fallback is implemented.

Price ceilings use USD per million prompt/completion tokens, USD per request or
image, exactly as the routing API documents. They are distinct from catalog
per-token prices and local spending grants. Negative/empty ceilings and decimals
that cannot round-trip to the numeric wire form without changing the value reject.
No billing arithmetic is implemented in JavaScript.

Generation preferences include temperature, top-p, output limit, frequency/presence
penalties, seed, stop and reasoning. Omitted controls remain omitted. Ranges,
model-supported parameters, declared efforts, mandatory reasoning and supported
reasoning budgets are checked. Effort and a token budget are mutually exclusive in
this implementation. Reasoning output is included in the overall output limit;
its explicit budget must be smaller. Other provider parameters, advanced sort
objects, quantization, provider-specific headers and other undeclared controls
are rejected by the closed contract, never silently forwarded or discarded.

Generic OpenAI-compatible requests have a separate path through the builder:
`max_completion_tokens` and the common chat controls, with `reasoning_effort`
only when declared. OpenRouter provider preferences, model fallback and its
reasoning object cannot leak into generic bodies. `require_parameters` has a
local validation meaning for compatible endpoints; no routing object is sent.
Model-list identity alone is insufficient: a trusted, explicitly sourced
`declared:` model capability/limit record is required. This package exposes no UI
that promotes unverified settings to such a record. Unknown compatible endpoints
therefore remain blocked until the main consumer has verified declarations.

Per-provider endpoint metadata, if supplied, must be schema-valid and fresh.
Display names are not guessed to be routing slugs. Model-level validation does
not certify every provider endpoint. OpenRouter's `require_parameters` is sent
so incompatible endpoints reject rather than dropping controls. Provider limits
and availability can change after inspection; a later rejection remains explicit.

## Structured output and response evidence

Formats are text, JSON object and named strict JSON Schema. Tool definitions use
the same local schema checks and documented function shape; this is not a tool
execution capability. A named tool choice must name a supplied function.

The supported local JSON Schema dialect includes primitive and nullable types,
closed objects with defined required properties, arrays, primitive enums, anyOf,
numeric bounds, Unicode string lengths and array lengths. Definitions are bounded
to 32 KiB, 16 levels and 1,024 schema nodes. Unknown keywords, remote/local `$ref`,
regex patterns, executable extensions, malformed limits and open objects reject
before construction. No schema keyword is silently ignored. Data validation is
bounded to 1 MiB, 64 levels and 100,000 nodes; no coercion, default injection,
external fetching or dynamic code execution occurs. This is an explicitly limited
dialect, not a claim to implement all JSON Schema.

Normalization preserves selected versus reported actual model/provider identity
and finish reason; absent identity remains null. Unexpected models cannot produce
a successful result. Only a single complete `stop` reply without refusal can
produce locally validated JSON. Truncation, filters, tool calls, unknown finish
reasons, malformed JSON, extra properties, wrong units/types and unsupported
schemas cannot become validated proposals. Local schema validity alone does not
establish semantic validity or permission to apply a game change. Error prose,
headers and raw metadata are not diagnostics: only fixed statuses and known
parameter names survive. Live transport must also enforce credential-echo redaction
before presenting provider content, as the metadata controller already does.

## Official schema evidence

Retrieved 2026-10-26 with the web source reader, without authentication, credentials
or paid generation. Tests use synthetic future-model fixtures and literal wire
expectations in `tests/desktop/provider-requests.test.ts`. Retrieval and mock
coverage do not establish live compatibility.

| Official source | Assumptions used |
| --- | --- |
| [OpenRouter API reference](https://openrouter.ai/docs/api_reference/overview) | POST `/api/v1/chat/completions`, messages, stream flag, chat completion choices/finish reason and model identity; tools and response formats |
| [OpenRouter parameters](https://openrouter.ai/docs/api_reference/parameters) | Sampling controls are optional, temperature 0–2 and bounded penalties; omitted controls preserve upstream defaults. This implementation conservatively requires top-p greater than zero. |
| [Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection) | Provider ordering/filters, fallback, parameter enforcement, data collection, ZDR, sort and price ceilings; prices have different units than catalog pricing |
| [Model fallback](https://openrouter.ai/docs/guides/routing/model-fallbacks) | Explicit primary-first `models` list, applied provider preferences and reported actual model |
| [Structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs) | `response_format.json_schema` with name, strict and schema; support is per endpoint and must be checked |
| [Reasoning](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens) | Reasoning object, effort/budget/exclude/enabled, model-declared effort/mandatory/budget options and combined reasoning/output context |
| [OpenAI chat reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) | POST chat completions, `max_completion_tokens` and `reasoning_effort`; identity/listing does not imply parameter or modality support. Compatible fields and effort values still require explicit endpoint evidence. |

No live provider, real key, real keychain, native Windows, fragmented SSE,
sharing/spending gate or full M6/G6 acceptance is claimed here.
