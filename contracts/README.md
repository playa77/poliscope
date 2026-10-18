# Runtime wire contract, protocol 1 / schema 1

Canonical source: `engine/poliscope_engine/contracts/__init__.py`. Generate with
`uv run --frozen python scripts/generate_contracts.py`; `npm run contracts:check`
fails on drift. TypeScript and tool inputs derive from the same JSON Schema.
Main's `wire.ts` validates inbound and outbound messages. WP-010 must integrate
these validators into live routing; today's bootstrap is a separate scaffold.

UTF-8 JSON Lines use LF, no CR, at most 1 MiB including LF. IDs are opaque,
nonempty bounded strings. Progress correlates request and operation IDs; null total
means unknown, never zero. Counts are bounded exact integers in both runtimes.
Diagnostics never belong on stdout. Error messages must be safe static descriptions,
not echoes of private payloads. Cancellation acceptance does not promise rollback
of an already committed result; status unknown does not prove no commit.

Only protocol 1 is supported. A handshake must offer 1; unsupported envelopes fail
with UNSUPPORTED_PROTOCOL before dispatch. Schema/application/protocol versions
are distinct; application changes alone do not change the wire version. Unknown
fields fail closed. Additive fields require coordinated schema regeneration and
consumer validation before use; breaking changes require a new negotiated protocol.
No legacy adapter or compatibility window exists yet (bootstrap is not protocol 0).
Future adapters need explicit fixtures, owners and retirement criteria.
Historical-read, replay, privacy and spending contracts are later WP-005 children.
Runtime status does not certify replay or computation compatibility.

`fixtures.json` is synthetic compatibility evidence, shared by Python and TypeScript.
It covers each runtime variant and rejects unknown versions/operations/fields and
malformed/oversized frames. Domain decimal/unknown/infeasible evaluation fixtures
belong to world/evidence children, not invented runtime results.

## World inspection, world schema 1

`world.inspect` adds a read-only projection contract. Canonical DTOs live in
`engine/poliscope_engine/contracts/world.py`; they generate through the same wire
schema, TypeScript types and tool-input schemas. This is a coordinated additive
contract extension: existing runtime fixtures remain accepted. Existing consumers
must be regenerated/validated before a world service sends these new variants.
There is no legacy-world adapter; no world service is implemented by this package.
WP-010 will dispatch runtime messages; later world services own these reads.

Every request binds data-store, civilization, branch and immutable revision IDs,
collection, explicit nullable cursor and a limit of 1–100. A response returns that
context, independent catalog/model/numeric-runtime identities, effective simulation
tick/calendar, and exactly one typed page. All pages cap items at 100; the 1 MiB
UTF-8 frame limit still applies to their combined size. Services must reduce the
page size to fit; a count cap alone does not guarantee a frame fits. `next_cursor`
is null only at the end. Cursor tokens are bounded opaque strings: the future
service must bind them to the complete authorized context/collection, reject
cross-context reuse, respect the requested limit, and never silently switch a
historical request to the current head. The DTO validator cannot prove that binding.

Scopes and entities are stable-ID projections. Typed, separately versioned edges
carry membership/aggregation semantics explicitly as weight, partition or
non-aggregating. They do not imply geographic containment, duplicate ownership,
or universal local precedence. Mechanism instances pin definition versions and
declare inheritance, typed parameter data and modeling status. Unknown mechanisms
may remain qualitative/unsupported; no code or expressions execute from DTOs.

Partition values keep conditions, design, assumptions, dynamic state, observations
and goals separate and carry scope, effective time and provenance references.
`quantity` preserves a bounded finite decimal spelling (including exponent strings)
with unit, time-basis and denominator references. `unknown` carries a reason and
has no numeric value; `0` remains a known quantity. Labels and references are
separate variants. This package checks structure, not Decimal representability,
unit existence/conversion, membership weight ranges, graph consistency, referenced
entity existence, or model validity. WP-006/007 and the producer services own those
checks. Source/assumption references become richer evidence objects in
WP-005-evidence. These projections do not authorize writes or establish evaluation
sufficiency; findings, unavailable-model/stale-revision and preview/apply contracts
remain their allocated children. Effective simulation time is not wall-clock time.

Shared `world:*` fixtures cover all page types, state partitions, entity/scope and
relationship kinds, inheritance/modeling/origin enums, exact quantities, unknown,
pagination and negative inputs. Python and TypeScript reject malformed types,
schemas, decimals and oversized lists/frames in both directions. Synthetic DTO
validity does not certify production world or simulation behavior.
