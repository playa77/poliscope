# Provider generation and dispatch safeguards

Optional text assistance lives in provider settings. Save a supported model and
an output limit, refresh its catalog, enter text and bounded USD exposure/limits,
and review the exact serialized payload, destination, original context and
sharing manifest before approving a single send. No generation is sent by
catalog refresh, preparing a request, status polling or opening settings.

Text-only requests share just the explicitly entered text. WP-046 also offers an
explicitly selected public scope/task manifest and bounded read-only tools, with
fresh exact-payload review for each continuation. Private notes, rationale,
attachments and unrelated branches are excluded. See
[grounded assistance](assistant_grounding.md) for the projection and tool limits.
The original selected civilization/branch/revision and effective time remain pinned
when navigation changes. With no selected world, text-only assistance is explicitly
standalone. Provider output is rendered as text, never Markdown or active media.
AI parameter proposals can enter the ordinary preview path; only the player's
separate ordinary Apply action can commit them. Attachments and stored transcript
handling remain WP-047/049.

Each reviewed request has a main-generated identity. Duplicate sends of that
identity return its existing state. A deliberate retry creates a fresh review,
sharing approval and dispatch identity; failures, timeouts and partial output
never automatically regenerate. There is a maximum of 16 retained requests per
application lifetime; restarting clears their private in-memory text and starts a
new session. The spending ledger and profile exposure survive restart.

## Sharing and spending production children

`SharingEnvelope` binds the complete JSON body, profile revision, endpoint,
selected/allowed models, plan and original context. Explicit approval is required;
whole-body authorization runs before reservation and again immediately before
transport. The cumulative manifest records each exact payload hash once and
bounds total disclosed bytes. Revocation blocks dispatch. Altered history,
continuation, tool results, errors, attachments or other context cannot inherit an
existing exact-payload grant. The bounded WP-046 continuation action obtains these same sharing and reservation
checks for each separate dispatch; it cannot accept arbitrary context or payloads.
Only explicit user text is classified as included by this consumer. No classification
is inferred from provider prose, a tool's read-only status or model instructions.

Python owns a separate private SQLite spending ledger under application userData,
not civilization history. Main launches its packaged/development host without a
shell, key, prompt, or inherited provider environment. Canonical DTOs carry only
IDs, SHA-256 bindings, currency, exposure and limits. Every accepted reservation
atomically counts all existing reserved, uncertain and completed exposure against
each turn, session and profile limit under `BEGIN IMMEDIATE`, with FULL durability.
USD amounts have an explicit 0.000001 quantum, checked by the existing Decimal28
runtime and an exact Fraction conversion; SQLite sums integer quantum counts.
Zero/missing/unknown exposure cannot authorize sending. An explicit bounded
exposure policy is required here because catalog estimates are not implemented.

A dispatch binding includes the exact payload digest, endpoint/profile/revision,
model/request/context identity, currency and exposure-policy version. Exact grant
replays deduplicate; mismatched identity/exposure conflicts. An unsent reserved
request may amend its amount within all original limits. Limit changes cannot
silently enlarge a previously established scope allowance. Main marks uncertainty
durably **before** transport; a crash between that mark and actual send deliberately
retains exposure. Only a known no-send reservation can be released. Cancellation,
HTTP rejection, completed output, key deletion and application restart do not
release uncertain exposure. Lost reserve/transition acknowledgments fail closed.
Completion marks an observation, not settlement: full WP-048 actual-cost
reconciliation is still required. The UI cannot reset persisted profile limits or
reconcile exposure. Local limits cannot guarantee upstream billing stops or cannot
exceed the selected exposure; provider account limits remain separate.

## Context and capability bounds

The pure WP-044 builder revalidates every selected control, model and fallback
against fresh main-owned metadata at preparation and again before obtaining the
credential lease. Renderer data cannot supply a tokenizer receipt. This consumer
supports text messages and bounded grounded-tool histories with OpenRouter's
declared `GPT` byte-BPE architecture: at most one base token per UTF-8 byte of
the complete serialized messages/tools, plus a conservative 1024-token reserve
per message/tool and one outer framing unit. Merging reduces the byte-BPE token
count. Roles, call IDs, arguments and tool schemas are included in the bound. This is an explicit
conservative model bound, not a general assertion that bytes equal tokens.
Unknown/other tokenizers and generic OpenAI-compatible catalog capabilities stay
blocked until a trusted matching bound and declared capabilities exist. Catalog
visibility and saved capability checkboxes alone cannot enable generation.

## Wire behavior and official evidence

Retrieved the official [OpenRouter streaming reference](https://openrouter.ai/docs/api/reference/streaming)
on 2026-10-26 without credentials or paid generation. The existing
[WP-044 schema references](provider_requests.md#official-schema-evidence) identify
the fixed chat-completions request and separate compatible-adapter assumptions.
Retrieval establishes schema evidence only; fixtures and loopback outcomes do not
establish live provider compatibility.

The current reference documents SSE comments, `[DONE]`, incremental deltas,
usage-only accounting, mid-stream errors and cancellation limitations. In
particular, OpenRouter's terminal usage frame may repeat the terminal
`finish_reason` with an empty content/assistant-role delta. It is accepted as an
accounting frame; repeated terminal content and post-terminal data are rejected.
The conventional empty `choices` usage frame is supported too.

Electron sends a fixed POST using the system-proxy network stack, an isolated
memory session, no cookies or interactive authentication, and manual redirects.
All redirects abort. HTTP error bodies/headers are discarded; fixed diagnostics
distinguish authentication, credits, rate limits, unavailable models, redirects,
provider rejection, malformed response and network uncertainty. There is no retry
loop. Key replacement/removal, profile changes and shutdown abort credential leases.
Raw provider error prose and credential echoes never become diagnostics or output.
A key-length suffix is withheld from streaming text until an echo can be excluded.

Responses are bounded to 2 MiB and 120 seconds. Incremental fatal UTF-8 decoding,
CR/LF/CRLF framing, multiline data, comments, usage frames and explicit end markers
work across arbitrary byte boundaries. A data event/line is bounded to 256 KiB,
with at most 16,384 events. Text/reasoning are bounded to 1 MiB each. Up to 32
indexed tool calls assemble independently; IDs, declared names, complete JSON and
the supported local parameter schema validate before a completed tool assembly is
returned. Malformed/incomplete streams remain failed/incomplete; cancelled output
never becomes complete. Whole JSON replies use the same completion/usage/tool
checks. Visible reasoning text/summary is separate from output; opaque reasoning
continuation payloads are not used by this consumer (WP-047).

Token categories and reported cost remain explicitly provider observations.
A numeric cost observation is represented as decimal text after ordinary JSON
decoding; its source precision is not authoritative. It is never added in
TypeScript or interpreted as a reconciled charge. Full WP-048 must retain exact
provider cost lexemes before using them for authoritative reconciliation. Missing usage is unknown. No actual-cost or full M6/G6
acceptance is inferred. Ordinary tests use only synthetic providers, mock protection
and loopback HTTP; real keys, paid dispatch, native Windows, authenticated proxies
and real keychain backends remain untested.

WP-046 adds [grounded context, bounded tools and ordinary proposals](assistant_grounding.md).
Its cumulative turn envelope supersedes the original single-message consumer
limits above; each continuation receives a fresh exact-payload review and a
distinct durable spending grant in the same turn. No automatic paid retry is added.

See [content and compatibility](assistant_modalities.md) for WP-047 typed inputs,
streamed audio artifacts, ownership/deletion, opaque history and the explicit
unsupported modality matrix. Earlier single-text-only bounds are superseded only
by those documented bounded paths. No general multimodal/provider certification
is inferred.
