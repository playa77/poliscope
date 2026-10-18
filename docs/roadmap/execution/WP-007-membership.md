# WP-007-membership — Relationships and membership aggregation

Started 2026-10-18 at merged PR #19, `e8f0c65`; owner Codex `/root`,
controller requesting user, sole writer in `/workspace/poliscope`, branch
`codex/wp-007-membership`. Route SV: separate inspection; agent review deferred.
Prerequisites: WP-007-identities at this base; protocol/world DTO v1 and numeric
runtime `decimal28-half-even-exact-v1`. Write scope: pure world graph service,
synthetic engine tests, runtime documentation and execution ledger.

Acceptance: independently typed/versioned relationships, existing endpoints and
unique IDs, acyclic containment with cyclic networks/jurisdiction permitted;
explicit weighted or partition membership; canonical union aggregation for
shared accounts/cohorts without duplicated stocks; exact arithmetic and compatible
quantity metadata; unknown remains unknown; pure atomic graph replacement.
No public command, persistence, external response mechanism or spending service.

## Separate inspection and evidence

Inspected endpoint/type checks, DTO revalidation/detachment, shared ID namespace,
iterative containment DFS, graph candidate atomicity and independent exact
Fraction sums. Inspection added effective tick/calendar compatibility to quantity
checks so observations at different simulation times cannot be silently summed.
Partition semantics explicitly deduplicate the same indivisible member; weighted
edges declare disjoint shares and overallocated or mixed unions fail closed.
Relationships cannot create a stock slot or change its existing state owner.

Full engine suite: 392 passed plus 24 subtests, including 25 new synthetic graph
cases. Frozen Python install, generated contracts, roadmap/baseline validators,
40 roadmap unittests and whitespace checks pass. No dependency or wire changes.
Engine candidate-bound evidence is recorded/verified locally with
`scripts/evidence.py` in `/tmp/poliscope-membership-engine`. Desktop/typecheck,
packaging and native flows are not rerun for this pure engine child. No hosted
CI, independent review, full parent or application gate is claimed.

Outcome: **solo-validated; agent review deferred**. External interface response
assumptions, physical asset alias detection, spending and durable publication
remain subsequent service acceptance, as at the identities boundary.
