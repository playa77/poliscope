# Timeline framework v1

`contracts.timeline.TimelinePlan` is a strict data-only schedule tied to an opening
revision and integer simulation day. `fixed-364-v1` has seven-day weeks, 91-day
seasons and 364-day years. `time_basis(period)` supplies explicit simulation
durations to the existing numeric `Registry.convert`; calendar names never imply
ecological or social effects. All authoritative rates retain their unit/scope.

`boundaries(plan, target_day, after_day=last_confirmed_day)` lazily yields each
required boundary, excluding the opening and including the target. Mechanism
instances declare their first boundary and interval. Display resolution cannot
skip daily updates. No aggregate optimization is registered.

At each boundary, a trusted reducer calls `stage_changes` with the confirmed
opening policies/conditions and `read_revision=revision_service.read`. Dated
condition events precede approved adoptions. Each category orders by `(order,id)`;
mechanism IDs are sorted. Return values are private candidates, not confirmed
world state. Events can change authored conditions, not physical stocks or civic
choices. An adoption names explicit binding deltas from an accepted parent/child
revision, expected binding digests/absence, affected scopes and prerequisites.
Disjoint deltas compose; a conflict leaves the entire adoption unapplied. Unknown
prerequisites block application; unsupported migration/delay remains a coverage
gap. `schedule_digest` binds the semantic plan and scheduler convention.

Only selected approved policy bindings are returned. Callers preserve running
stocks/assets/cases and unrelated configuration, never copy the source revision
snapshot. Design alternatives and explicit retrospective forks use `Revisions`;
past schedule edits require a fork. Whole-configuration replacement is unsupported.

WP-034 owns active mechanism resolution and transition reduction; WP-036 owns
atomic durable confirmation, cancellation/recovery and checkpoint/replay. These
APIs do not write storage, publish state, grant renderer access or certify G4.

The full trusted-host WP-036 controller is now implemented in `experiments.py`.
See [experiment operations and recovery](EXPERIMENTS.md) for checkpoint selection,
recorded/verified replay, durable pause/cancel and retrospective forks. Renderer
presentation and full G4 acceptance remain subsequent work.
