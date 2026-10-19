# WP-012-expressions — Bounded declarative arithmetic

Started 2026-10-19 on PR #23 merge `862ad9cb45550bb07a6e60438abc1d7279fdf41e`.
Owner Codex `/root`; controller requesting user; sole sequential writer in
`/workspace/poliscope`, branch `codex/wp-012-expressions`. Route SV: separate
inspection; agent review deferred. Prerequisites: WP-012-registry at this base,
merged numeric, world and mechanism contracts. No other agents allocated.

Scope: version-1 data-only expression contracts and generated artifacts, bounded
DAG validation and pure exact arithmetic, registry activation bound to graph
content and model review, typed outputs/state proposals and missing propagation.
No new dependencies, wire operations, storage or renderer changes.

Acceptance: reject unknown operators/versions, executable payloads, cycles,
dangling references, excessive graph size/depth, incompatible unit/time/scope
metadata, undeclared outputs/state, stale graph review and invalid numeric values.
Synthetic chain/diamond fixtures have independently derived exact results;
unknown values propagate without becoming zero. Static and transition support
are explicit. Graph execution cannot import code, mutate world or publish state.
Existing host evidence/fixture review requirements apply to exact graph content.
Policy resolution, cross-mechanism solver/runtime and durable publication remain
consumer packages; structural validity establishes no scientific validity.

## Separate inspection and validation

Implemented strict graph contract 1 with generated JSON Schema/TypeScript,
immutable registry snapshots, graph-digest/model/declaration-bound review,
stable topological validation of all nodes, and exact Decimal operators. Graph
outputs preserve declared input dependencies and exact unit/time/denominator
metadata. Transition state values are pure proposals; existing owned-state
staging remains mandatory. Unknown inputs propagate as `None`, while independent
known branches remain evaluable. Caller retains original missing-value reasons.

Separate inspection covered cycles/unused nodes, graph identity substitution,
mutable nested DTOs, unknown-value validation, arithmetic precision, dimensionless
unit scaling, input dependency closure, references and foreign state proposals.
Inspection tightened structural validation of unknown DTOs and added regression
cases for unused hostile operators, independent known outputs, label/reference
passthrough, graph duplication and transition ownership. No callbacks are
resolved from graph content. Operator extension requires engine changes and a
new model/review; arbitrary unit algebra is intentionally unsupported.

Validation: 34 new expression tests; full Python suite 571 passed (24 subtests),
206 Vitest tests and 40 roadmap unittests pass. Frozen uv/npm installs completed
without dependency lock changes. Typecheck, generated-contract drift,
roadmap/baseline and whitespace checks pass. Final candidate-bound engine evidence
is recorded and verified at `/tmp/poliscope-expression-engine`.
Native packaging, hosted CI, application gates and independent review are unrun;
no scientific validity or full parent acceptance is claimed.

Outcome: **solo-validated; agent review deferred**. Full allocated expression
child is complete. Reassess WP-013-policy after merge. Mechanism scheduling,
preconditions/policy enforcement, finite allocations, cross-mechanism solving,
trace/coverage publication and durable state changes retain consumer acceptance.
