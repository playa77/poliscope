# Grounded assistance and proposal authority (WP-046)

The optional assistant can explain an explicitly selected public projection from
one saved design revision. Select a civilization/revision in the workspace, enter
its scope ID (the initial scope is `home`), enable grounded context, choose the
collections and enter a task. The local Python service assembles the manifest;
preparation does not send anything to a provider. Review its immutable context,
entries, classifications, coverage, limitations, destination and exact complete
payload before approving a send. Society tools remain usable offline.

## Projection and limits

A manifest pins the data store, civilization, branch, revision, scope, task,
versions and effective time. Its digest covers all entries and selection fields.
Facts are exact declared world conditions; choices are retained scoped design
values. Account rows and calculation traces come from retained engine evidence.
Point assumptions retain their public definitions, origin and uncertainty form;
source entries retain reached public attribution metadata. No source URL or file
is fetched by a tool. Quantities retain Decimal strings, units and provenance;
unknown inputs remain unknown. Source descriptions and player/model text remain
untrusted data. None establishes scientific validity or a recommended design.

Only the explicitly selected collections in this scope are eligible. Private
notes, rationale, attachments, unrelated scopes/branches and their existence
indexes are excluded. Private/unavailable or out-of-scope provenance taints the
complete dependent row, including through public assumption/source descriptors.
Derived world values without a classified retained trace are withheld. Cross-scope
trace dependencies withhold their whole dependent trace/account row. No private
opt-in or attachment sharing is offered here; those require a separate explicit
sharing path. Other branches require a fresh selected context and review.

The projection admits at most 60 entries, approximately 24 KiB of entry data and
32 KiB overall. Oversized/unrepresentable rows are withheld with a generic partial
projection limitation, without counts/IDs of excluded data. Narrow the selection
and prepare a fresh request to include other eligible entries. Context beyond the
selected grant is never retrieved implicitly. A source-only selection without
reached rows can be empty.

## Read-only tools and continuations

Enabling tools requires fresh model metadata declaring tool and parameter support.
No-tool models can explain the same supplied manifest with visible limitations.
The sole function, `inspect_context`, is generated from the canonical Python DTO.
It accepts an operation, approved entry ID, optional second approved entry ID and
optional bounded typed value JSON. It cannot accept context IDs, paths, URLs,
commands, model graphs, credentials, arbitrary operations or an apply action.

`read`, `inspect` and `retrieve` return an already approved manifest entry.
`compare` performs a Python exact structural comparison of two approved entries
from one collection. It does not invent a civilization score or substitute an
unapproved branch comparison. `validate` and `preview` accept only an existing
editable point assumption used by a registered mechanism, preserving its scope,
value kind, units, denominator and time basis. They run the real pure ordinary
parameter preview. Unsupported mechanism/model edits stay unavailable.

Only completed, schema-validated tool calls are executable. Denied, missing,
private, malformed, unsupported and backend-failed lookups all return the same
fixed `unavailable` object. Tools do not probe denied references. Their context
and local store remain the original grant even after navigation. Neither read-only
access nor provider instructions expand sharing authority.

The player explicitly runs local calls and reviews the resulting next request.
Every continuation includes its exact tool calls/results and included prior
messages for review; no hidden history, errors or existence metadata is appended.
Each send requires its own exact-byte approval and durable spending reservation.
Dispatch IDs differ; turn/session/profile spending scopes remain the original
ones. Initial exposure still counts against continuation limits. Revocation
propagates to every round. Asynchronous reservation is followed by capability,
profile and sharing revalidation immediately before POST. Uncertain/cancelled
requests retain exposure and never trigger automatic paid regeneration.

A turn allows three continuation rounds and eight total calls. The cumulative
complete-payload disclosure ceiling is 192 KiB, including repeated history bytes
in each distinct payload; each reviewed payload is additionally bounded by the
assistant IPC contract (64 KiB). Provider responses remain subject to WP-045's
2 MiB transport and bounded decoder limits. Context accounting covers serialized
messages, roles, IDs, call arguments, tools and schemas, plus a conservative
1024-token framing reserve per message/tool and one outer unit for declared GPT
byte-BPE models. Unknown tokenizer/endpoint capability evidence still blocks
execution. This bound is an explicit supported-model assumption; catalog discovery
alone does not establish execution suitability or a tokenizer for other models.

## Proposals and player Apply

An AI parameter preview returns an ordinary typed proposal with `ai_proposed`
origin, request identity, manifest digest and coverage. Pending proposals remain
local to this session. Select a proposal to open the ordinary evidence preview;
this main-owned action checks the currently selected immutable context, refuses
to replace an unrelated draft and grants no model apply authority. Read its exact
parameter change and ordinary engine differences. Only the player's separate
**Apply evidence edit** action commits it. Cancel leaves history unchanged.
Historical or stale contexts cannot silently become the current branch head.
Uncertain Apply retries retain the same operation/candidate identity.

Accepted proposal origin and coverage are retained in the public assumption
reference descriptor/description inside immutable revision inputs. The contract
represents authored, player and AI proposal origins. A subsequent ordinary player
edit records player origin while earlier history retains the AI receipt. These
receipts are game-design provenance, never a claim that generated numbers or
hypothetical mechanisms are scientifically supported. New mechanisms, arbitrary
model edits, topology changes and timeline mutations have no assistant tool.

## Evidence boundary

Synthetic Python tests exercise real revisions, point-parameter previews,
idempotent/stale Apply and privacy canaries. Desktop units exercise fixed denials,
round/call/byte caps, revocation, distinct same-turn grants and exact continuation
review. The packaged Linux test uses real Electron networking, bundled Python
projection/tool hosts and SQLite spending against a local synthetic provider;
parallel approved/hostile calls cannot disclose excluded private-note text or
an unrelated civilization. Official wire assumptions remain those documented in
[provider requests](provider_requests.md) and [generation](provider_generation.md).
Windows, real provider/keychain compatibility and paid calls are unrun. This
package does not claim full M6/G6 acceptance, attachment handling, transcript
persistence/deletion (WP-049), or cost reconciliation (WP-048).
