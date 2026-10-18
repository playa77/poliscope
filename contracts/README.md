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
Future adapters need explicit fixtures, owners and retirement criteria. World,
historical-read, numeric-runtime, replay, privacy and spending contracts are later
WP-005 children. Runtime status does not certify replay or computation compatibility.

`fixtures.json` is synthetic compatibility evidence, shared by Python and TypeScript.
It covers each runtime variant and rejects unknown versions/operations/fields and
malformed/oversized frames. Domain decimal/unknown/infeasible evaluation fixtures
belong to world/evidence children, not invented runtime results.
