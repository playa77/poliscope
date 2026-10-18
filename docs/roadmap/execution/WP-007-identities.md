# WP-007-identities — Canonical identity and state ownership

Started 2026-10-18 from main `1195f1ce4636e28eaa0142f98806820cab028619`
(merged PR #18 / WP-006-numeric). Owner Codex `/root`; controller requesting
user; one sequential agent, `/workspace/poliscope`, branch
`codex/wp-007-identities`. Route SV: separate inspection; agent review deferred.
Prerequisites: numeric at that exact merge; world DTOs from PR #11 at `1775a36`.

Write reservation: pure engine world registry, synthetic engine tests, runtime
contract and execution records. No wire schema/dependency changes. Acceptance:
caller-supplied stable IDs for all existing entity/scope kinds; duplicate and
missing references rejected; exactly one civilization and explicit cohort role;
unique writer per entity/property/partition across scopes; immutable snapshots
and detached queries; pure atomic candidate validation; goal writes cannot alter
conditions/dynamic state; IDs cannot be rebound to another slot or scope.

This completes the identities child, not the membership child or planning parent.
Relationships, containment cycles, weighted aggregation, external interface
behavior/finite-capacity mechanisms, account spending and durable publication
remain subsequent services. Registry ownership is structural validation; trusted
services select writers, and it is not a public authentication boundary.

## Separate inspection and validation

Inspected identity uniqueness across entity/scope/value namespaces, exact single
civilization binding, reference existence, single role for every cohort, unique
state slots across scope aliases, owner uniqueness and batch partition checks.
Existing identities cannot migrate scope/slot through an update. DTO instances are
reparsed even after `model_copy` bypass; nested mutable provenance lists are
snapshotted and queries return detached copies. No database, network, wall clock,
random identity generation or float arithmetic enters registry execution.

33 synthetic registry tests exercise all canonical entity kinds, all five
non-goal partitions against goal writes, detached nested lists, duplicate IDs,
foreign references, invalid population declarations, numeric precision rejection,
cross-domain writes, identity rebinding and failed multi-change atomicity. Full
pytest: 367 pass plus 24 subtests; Vitest: 204 pass; roadmap unittests: 40 pass.
Typecheck, generated contracts, bootstrap content inventory, roadmap/baseline and
whitespace checks pass. Frozen uv/npm installs succeed with unchanged locks.
Initial npm setup could not write its default cache; retry with a writable `/tmp`
cache succeeds. npm lifecycle scripts were disabled because this pure Python
package does not require downloading/running Electron.

Final candidate-bound engine/unit evidence is captured and verified using
`scripts/evidence.py` under `/tmp/poliscope-identities-final-{engine,unit}`.
These are local mechanical checks, not hosted CI or independent review. No
packaging, Electron smoke or native-platform checks were rerun for this
unintegrated pure engine child. No full parent/application gate is claimed.

Outcome: **solo-validated; agent review deferred**. The allocated identities child
is complete. Next ready scope is WP-007-membership after this boundary is merged;
its overlap/aggregation and containment acceptance remain explicitly outstanding.
