# WP-006-numeric — Canonical arithmetic and quantity semantics

Started 2026-10-18 at main `1a2b343f1a260f6b64fc427cfa17088959c78f84`
(merged PR #17). Owner Codex `/root`; controller requesting user. One sequential
agent in `/workspace/poliscope`, branch `codex/wp-006-numeric`. Route SV with
separate inspection; agent review deferred. Prerequisite WP-005-world merged at
`1775a36` (see its ledger evidence); world DTOs remain unchanged and preserve raw
decimal strings. Scope: engine numeric primitives, extensible unit and quantity
semantics, immutable account policies and pure transfer staging, independent
numeric fixtures/tests and execution records. No storage mutation, solver,
calendar choice, domain mechanism or renderer arithmetic is allocated.

Acceptance: bounded decimal strings and canonical encoding; isolated 28-digit
half-even contexts; no binary-float authority; exact conversion validation across
unit dimensions, kinds, time bases and explicit population denominators; money
cannot convert to physical resources. Immutable runtime identity covers encoding,
precision, bounds and account rules. Account policies declare quantum, range and
reject/retain residual behavior. Unsupported resolution and lost transfers fail
before publication; integer/Fraction oracles prove exact balance, including the
1E29 stock/unit-withdrawal witness. Separate display rounding does not mutate
stored values. Frozen installs, engine and unit suites, contracts, typecheck,
roadmap checks and whitespace review pass. No application gate claimed.

## Separate inspection and validation

Inspected parsing/canonical round trips at the exponent and 28-digit boundaries,
context/default-context independence, dimensional/kind/scope checks and explicit
rate/population direction. Compact scientific encoding prevents canonical output
at extreme exponents exceeding the bounded input grammar. The synthetic year
factor is explicit, not a calendar decision. Spatial reaggregation fails until
world membership semantics exist. Money/entitlements remain distinct kinds.

Inspected account ranges, half-even quantum ties, source funding, destination
limits and both signs of retained remainder. Transfers stage the requested debit,
rounded credit and an actual residual balance together; a negative remainder
requires residual-account funding. Independent exact quantum/rational sums check
the complete candidate. All inputs are immutable. Unsupported resolution fails
before a consumer can publish a state. The `1E29`/unit witness rejects an invalid
unit-resolution policy and repeated lost unit transfers under a valid coarser
policy; an accepted 1000-unit withdrawal matches exact integer counts. Yield/loss
fixtures account for all 125 input units as 100 product and 25 loss. These are
synthetic arithmetic witnesses, not production scientific mechanisms.

Frozen uv/npm installs succeeded with unchanged locks. Engine suite: 334 tests
plus 24 subtests pass; Vitest: 204 tests pass; roadmap unittest suite: 40 pass.
Typecheck, generated contracts, content inventory, roadmap/baseline and whitespace
checks pass. Shared numeric fixtures travel through actual TypeScript wire
encoding/decoding as authoritative strings, preserving values beyond Number
precision. A first npm test run completed Vitest but its Python tail could not
write the default cache; rerun with a writable /tmp uv cache passes. Final
candidate-bound engine/unit evidence is captured and verified with
`scripts/evidence.py` under `/tmp/poliscope-wp006-{engine,unit}`.

Linux packaging/Electron smoke is not rerun: this package adds pure engine
primitives with no bootstrap, desktop service, dependency or wire-schema change.
Windows/macOS/native reproducibility remain untested. Store transaction integration,
world scope aggregation, calendars, production yields/solvers and application gate
acceptance remain later packages. Numeric runtime v1 deliberately rejects inexact
arithmetic/conversions; rounded postings require an explicit residual policy.
See the [runtime contract](../../../engine/poliscope_engine/numeric/README.md).

Outcome: **solo-validated; agent review deferred**. Allocated WP-006-numeric scope
is complete; full planning-parent/milestone acceptance remains additional.
