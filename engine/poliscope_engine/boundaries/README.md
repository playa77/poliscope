# Confirmed-boundary storage v1

`BoundaryStore` is a trusted Python host service over the production `Store` and
`Revisions` providers. It is not a renderer endpoint, an experiment simulator or
an arbitrary persistence grant. Main must authorize access before invoking it.
The approved WP-036-boundary-store child is the early provider for WP-034; full
WP-036 checkpoint/replay/fork acceptance is still pending.

- `create(CreateExperiment)` copies the committed opening revision and complete
  accepted evidence, checks the fixed calendar and scheduled instance identities,
  validates every future policy approval and freezes the schedule.
- `confirm(ConfirmBoundary)` checks the expected confirmed outcome, next required
  schedule boundary, WP-033 events/adoptions, canonical closing state and retained
  evidence identity. It requires a host-configured `validator` and versioned
  `validator_id`. The validator receives a detached `BoundaryValidation` and
  must raise on invalid conservation, capacity, ownership or model invariants.
  Storage checks are not proof of domain/scientific validity. No content registers
  code, and no permissive production validator is supplied by this child.
- State/evidence chunks, event/adoption results, immutable journal/head and the
  operation outcome are persisted in one `BEGIN IMMEDIATE` transaction. The
  journal is the sole head; there is no separately published in-memory candidate.
  Validation happens privately, with a second head/outcome check under the lock.
  Reentrant queries on that same connection fail with
  `unconfirmed_write_in_progress`; other connections continue to read the last
  confirmed boundary. This prevents SQLite read-your-own-writes from exposing
  staging through a cancellation or other host callback.
- `read(context, sequence=None)` reads one confirmed boundary and complete retained
  evidence without a numerical registry, transition validator or cache.
  `status(request)` and identical completed retries replay before stale-head or
  current execution-availability checks. Changed payload/action reuse conflicts;
  operation identity includes the experiment and its store/civilization context.

The request binding uses a canonical payload digest so large accepted closures do
not exceed the storage row bound. State and evidence are immutable, bounded
64 MiB blobs split into chunks below the schema-1 1 MiB row limit; the schedule
metadata and boundary journal rows retain that 1 MiB bound. No schema migration,
dependency or arbitrary-code serialization is introduced. Clearing caches cannot
remove boundaries, evidence or operation outcomes.

Cancellation is checked before validation, after validation, under the write lock
and after writes before COMMIT. No cancellation check runs after COMMIT. A lost
acknowledgment is uncertain to the caller until exact status/retry; it must not
cause a new operation ID. Failures before COMMIT discard staging. Reopen reads
the confirmed journal, including a boundary committed before a process crash.

WP-034 now supplies the production `TransitionReducer` validator in
`simulation/`. Transition-enabled configurations freeze a typed transition plan
and retain a complete receipt with the closing state. These coordinated additive
v1 contracts preserve old state/request identities when the extensions are absent;
consumers of transition-enabled records use the regenerated schemas/types.
