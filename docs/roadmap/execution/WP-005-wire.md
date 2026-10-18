# WP-005-wire — Runtime boundary contract

Started 2026-10-18 on main `3cac56b3a33a28a9dd69f89901f892c6930d7fbb` (PR #9 merged).
Owner Codex `/root`; controller requesting user; one sequential agent.
Validation route SV: separate inspection; solo-validated; agent review deferred.
Branch `codex/wp-005-wire`; reserved checkout `/workspace/poliscope`.
Prerequisite WP-003 harness merged at the base above.

Scope: canonical Python runtime request/result/error/progress contracts, generated
JSON Schema/TypeScript/tool inputs, strict main-side boundary validation and
positive/negative cross-language fixtures. Contract protocol 1, schema 1;
application identity is independent. Write scope engine contracts, desktop main
wire validator, contracts/, generation/check scripts, tests and execution records.
Acceptance: deterministic drift detection; lossless Python/TS fixture validation;
unsupported versions and malformed data rejected with stable codes; 1 MiB UTF-8
line limit; typed handshake/health/status/cancel/shutdown and correlated progress.
Consumer implementations remain WP-010; bootstrap stays operational until then.
World/evidence/timeline/privacy messages remain later WP-005 children; parent
acceptance is not claimed. No production gate or native-platform claim.

## Separate inspection and validation

Inspected generated-reference resolution, strict field/union validation, version
negotiation rejection, frame byte counting, Unicode decoding, exact integer
boundaries and outbound revalidation. Pydantic literal coercion of booleans and
JavaScript floating-point parsing differed initially; shared negative fixtures
now reject boolean literals, noninteger numeric spelling, unsafe counts and lone
surrogates. Tool-input schemas carry the complete referenced definitions.
Generation rejects modified/missing outputs and unregistered artifacts; three
isolated negative tests demonstrate these failures without editing the candidate.

Frozen npm/uv installs succeeded with unchanged locks. Python/TypeScript shared
synthetic fixtures cover every runtime request/result variant, errors, progress
with unknown versus known totals, old/future versions, malformed framing, UTF-8,
extra fields and oversized input. Relevant engine/unit harness runs and current
candidate verification are recorded locally under `/tmp/poliscope-wp005-*`.
Typecheck, contract drift, roadmap/baseline, empty-content and whitespace checks
pass. 95 pytest tests and 35 Vitest tests pass with zero skips. The root npm test
also passes its 40 roadmap unittest cases. No dependencies added.

Outcome: **solo-validated; agent review deferred**. Consumer integration, packaged
Electron smoke for this candidate, hosted CI and independent review are unrun.
This package adds contracts and validators, not live production RPC; WP-010 must
use them at dispatch. No application milestone or WP-005 parent acceptance claimed.
After merge reassess WP-005-world and WP-010-producer prerequisites; no consumer
is started against an unmerged contract. One agent remains available.
