# WP-012-contract — Versioned mechanism declaration boundary

Started 2026-10-18 at merged PR #21,
`b946dbf30e65b039d6c7868d3db204f5c99c1301`. Owner Codex `/root`; controller
requesting user; sole writer in `/workspace/poliscope`, branch
`codex/wp-012-contract`. Route SV, separate inspection; agent review deferred.
Prerequisites: WP-007-membership at `cbf71c1` and WP-008-packs at this base,
with merged numeric/world/evidence contracts. No other agent allocated.

Write scope: canonical mechanism declaration contracts and semantic validation,
generated schema/TypeScript and synthetic compatibility fixtures, tests, docs,
execution ledger. Contract version 1; no wire, pack, dependency or storage change.

Acceptance: stable versioned domain/mechanism identities; typed scoped ports and
owned state; explicit static/transition support and missing-input propagation;
preconditions, claims, policy semantics, evidence/assumptions, trace/diagnostic
definitions and fixture/property references. Reject ambiguous IDs, dangling
references, foreign state-write declarations, inconsistent port metadata and
executable payloads. Preserve qualitative drafts without activation, distinguish
scientific evidence from structural validity, and round-trip synthetic domains
through generated artifacts without numeric loss.

This child defines data and local consistency only. Trusted registry activation,
cross-domain unit/owner resolution and binding are WP-012-registry; bounded
operator graph validation/execution is WP-012-expressions. No mechanism executes
and no full WP-012 or application gate is claimed.

## Separate inspection and evidence

Implemented canonical Pydantic v1 declarations, generated JSON Schema and
TypeScript, and two shared synthetic domain fixtures. Generated fixture TypeScript
uses `satisfies MechanismDefinition[]`; root typecheck checks positive fixtures
and negative consumer type expectations. Python validation enforces local
reference closure, unique IDs, required-input propagation, exact claim/allocation
metadata and explicit allocation dependencies. State writes refer only to owned
dynamic state and require transition support. All implementation identifiers
remain data; no loader, registration or evaluator is introduced.

Separate inspection covered state-authority boundaries, required account and
allocation inputs, cross-field constraints versus generated structural types,
mutable nested model collections, optional-input semantics, qualitative drafts,
policy rule references, and unit-resolution limits. Inspection added a rejection
for optional shared-account inputs and explicit tests for dangling diagnostic and
precondition references and type-inappropriate unit metadata. Unknown external
unit IDs remain structurally inspectable; registry resolution must reject them
before activation. Contract README records these consumer obligations.

Validation: 49 new Python cases; full frozen Python suite 497 passed (24
subtests); 206 Vitest tests and 40 roadmap unittests pass. Root typecheck,
contract regeneration/drift, roadmap/baseline validators and whitespace checks
pass. Frozen uv/npm installs succeeded without lock changes. The initial combined
npm test reached a read-only default uv cache after Vitest passed; rerunning with
`UV_CACHE_DIR=/tmp/poliscope-uv-cache` passed the complete command.
Candidate-bound engine evidence is recorded and verified locally at
`/tmp/poliscope-mechanism-contract-engine` using `scripts/evidence.py`.
Desktop packaging/native flows were not rerun for this contract-only package.
No hosted CI, independent review, scientific validity or application milestone
is claimed.

Outcome: **solo-validated; agent review deferred**. Reassess WP-012-registry after
merge. Pack attachment, trusted implementation lookup/activation, external
unit/source/world resolution, runtime propagation, transactional mutation,
operator graphs and full parent acceptance retain their separate scope.
