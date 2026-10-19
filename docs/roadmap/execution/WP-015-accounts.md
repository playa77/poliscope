# WP-015-accounts — Shared account materialization

Started 2026-10-19 on merged PR #25 `2048425e20a1a1b32dc6033f712cd390925e3202`.
Owner Codex `/root`; controller requesting user; sole sequential writer,
branch `codex/wp-015-accounts`. Route SV: separate inspection; agent review
is deferred. Prerequisites are merged numeric, world membership, mechanisms and
policy children on that baseline. No agents allocated.

Scope: strict version-1 account, actual posting, claim, reservation and subtotal
contracts; pure bounded account materialization with exact quantum balances.
Accounts distinguish stock, flow and capacity, unit/scope and explicit periods,
physical/budget/ledger invariants. Boundary supplies/imports/production and
uses/exports/losses are separate; internal postings conserve exact quantities.
Reservations earmark availability once, and actual fulfillment replaces that
hold. Claims expose actual/unmet values without choosing precedence or granting
access. Subtotal leaves cannot overlap, nest cyclically or be added twice.

Acceptance: independently derived stock, labor/capacity, finite import, loss,
reservation, unmet/access and subtotal fixtures; duplicate/unknown references,
overdraw, incompatible units/periods, precision loss and mutable DTO defenses.
Reuses WP-006 exact arithmetic and residual transfer staging. Allocation policy,
transformation yields/graph solving, access/funding decisions, storage publication,
public IPC and full parent/application acceptance remain subsequent work.

## Implementation and separate inspection

Implemented Python contracts with generated JSON Schema/TypeScript, a pure
snapshot account book and detached results. Exact rational accumulation and
per-posting/closing WP-006 policy checks reject precision loss and overdraw.
All inputs are already-solved actuals; the service never selects priority.
Reservation fulfillment reduces the hold and stock together; actual and remaining
hold cannot exceed the claim. Full declarations, source/mechanism references and
posting IDs remain inspectable. Compatible subtotal expansion rejects repeated
leaves, unknown references and cycles without recursive graph traversal.

A separate inspection checked reservation double deduction, duplicate namespace
identities, unreserved use against outstanding holds, missing values, nested
mutable DTOs and bypassed validation, incompatible units/scopes/periods,
finite external supply, signed residual postings and aggregate precision.
It added a remaining-claim hold check and expanded posting-reference capacity to
the batch limit, with negative fixtures for both. Expected arithmetic is stated
independently in the synthetic tests. No independent reviewer is claimed.

Validation: 50 new account cases; 672 full Python tests and 24 subtests pass;
206 Vitest tests and 40 roadmap unittests pass. Frozen uv/npm installation,
typecheck, generated contracts, content inventory, roadmap/baseline and whitespace
checks pass. Frozen lockfiles are unchanged. Final candidate-bound suite evidence
and Linux packaging results are recorded below after validation.

Outcome: **solo-validated; agent review deferred**. The allocated accounts child
is complete. WP-015-allocation remains next; full parent acceptance still needs
finite allocation, access/funding and transformation/graph integration evidence.
Host world identity/authorization, scientific validity, durable publication and
full application/native platform gates remain outside this bounded service.

Linux x64 engine and Electron packaging pass. Local packaged desktop launch is
unrun because this image has no virtual display runner; hosted CI owns the
existing launch/security scenarios. Windows/macOS and independent review remain
unverified. Final candidate-bound engine/unit evidence is recorded and verified
under `/tmp/poliscope-accounts-engine` and `/tmp/poliscope-accounts-unit`.
