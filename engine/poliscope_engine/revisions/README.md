# Immutable revision service v1

`Revisions(Store(absolute_user_data), registry=trusted_mechanism_registry)` is the
production Python service. Main selects and authorizes the store and civilization;
this class is not a renderer capability or arbitrary SQL endpoint. `data_store_id`
is generated once and stored durably. `create(CreateRequest)` accepts explicit
canonical identities, ownership/population declarations, topology, evaluation
inputs, measurements and optional goals. It evaluates and retains the root result.
`open(data_store_id=..., civilization_id=..., branch_id=...)` returns the confirmed
branch. `read(context)`, `inspect(WorldInspectParams)`, `history(HistoryQuery)` and
`evidence(context)` work without an executable model. Execution mechanism bindings
are in `read(...).inputs.design.execution.dependencies.instances`; the older
world `mechanisms` collection describes different inheritance DTOs and is rejected
explicitly. No empty or fabricated mechanism page is returned.

`preview(PreviewRequest)` reconstructs an immutable base with ordered typed
`set_values` or complete `replace_inputs` changes. Set-values delegates to WP-007
ownership and partition checks. Full replacements support entity/topology/design,
assumption and goal changes and validate the entire world/evaluation. Canonical
entity/scope/value/relationship meanings are reserved across all retained futures,
even after removal. Labels, quantities and versioned relationship metadata may
change; an old ID cannot be reassigned a different kind or endpoint. Schema,
catalog/model and numeric-runtime migration is rejected and requires a separate
explicit migration service. Trusted implementation/review, policy, arithmetic and
accounting authority stay in their existing owners.

Preview returns the complete candidate digest, input/evidence identities,
conservative affected scopes, changed value IDs, typed before/after numerical
observations and measurement findings/traces. Structural invalidity fails; valid
incomplete, insufficient or conflicted evaluations can be inspected and accepted.
Preview never writes SQLite, archives a decision or advances a head. Historical
bases can be previewed; a new apply must match the current head. No preview cache
entry, candidate object or renderer-supplied result is trusted for apply.

`apply(ApplyRequest)` receives the full preview request and digest. Inside one
`BEGIN IMMEDIATE` transaction it first checks the immutable operation ledger,
then checks head, reconstructs/evaluates the exact candidate and compares its
digest. It persists complete inputs/typed event, alternatives and selected choice,
accepted evaluation/report/source/assumption/trace closure, revision index,
branch journal entry and completed operation outcome before commit. A selected
alternative must exactly match the applied changes. Private rationale is only a
classified noncontent reference; this service never copies private note text or
transcripts. Inputs/alternatives are explicitly approved simulation content, not
an implicit promotion of private conversations. Export must separately project
revision metadata and all its private references; this package is not an export.

Operation keys bind store, civilization, operation kind (including branch action)
and ID. Bindings contain the complete canonical original request, base, branch,
payload and candidate/model identity. Decimal spelling and declared unordered
collections follow WP-016 canonicalization; ordered changes retain order. Exact
completed retries return the original outcome before current-head or executable
model checks. Conflicting reuse fails without revealing another outcome. `status`
requires the exact authorized typed request and returns the confirmed outcome or
`None` (unknown). This synchronous service has no visible pending/rejected ledger
entry. Unknown must not trigger retry with a fresh operation ID.

`change_branch(BranchRequest)` supports rename, fork, undo and redo. Branch
sequence and head checks prevent stale metadata changes, including an ABA cycle.
Fork records lineage and shares the immutable source revision. Undo/redo append
journal states. Applying to an undone head clears its active redo stack while all
old states, revisions, alternatives and evidence remain retained and queryable.
History pages use acceptance order across all civilization futures, not ID sort or
an implicit current-path filter. World/history cursors bind the selected context.
No history deletion or deduplication compaction is implemented.

All of this uses storage schema 1; no DDL change, migration or old-save rewrite.
Chunk manifests and immutable JSON-string chunks store up to 64 MiB per snapshot
while every primitive record remains under 1 MiB. Reads verify complete manifests
and content identity and fail explicitly on missing/corrupt chunks. Canonical
mutation bindings remain subject to the primitive 1 MiB request bound. Collections
and active redo stacks are bounded at 1,000 entries; branch/history sequences are
JavaScript-safe integers. A limit failure rolls back the entire mutation. Internal
Python snapshots/candidates are not wire messages: future public IPC must paginate
or chunk them and keep its 1 MiB transport limit. Existing WP-010 historical
readers retain their own envelope; revision closures use this trusted data-only
reader and are not silently adapted to a legacy envelope.

Main still owns per-directory application single-instance locking. SQLite locks
serialize independent writers; the service checks heads inside the lock. On a
process crash, SQLite either rolls back the incomplete transaction or exposes
all committed records plus the replayable outcome. Reopen/status resolves a lost
reply without re-running callbacks. Retained reads survive cache clearing and
model removal. Native runners, public IPC/UI, model migration, portable archives,
WP-019's separately allocated vertical slice and full application gates remain
separate acceptance work.
