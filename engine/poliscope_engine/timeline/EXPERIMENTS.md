# Durable trusted-host experiment API v1

Construct `Experiments(TransitionReducer(revisions, catalog=reviewed_catalog))`
on the authorized local store. These APIs do not expose renderer mutation grants.

- `create(StartExperiment(...))` retains opening revision/model/assumptions,
  approved plan, random plan and immutable checkpoint spacing in boundary counts.
- `advance(AdvanceExperiment(...), cancelled=..., progress=...)` confirms up to
  1,000 boundaries. Keep the original request for exact status/retry after a lost
  response. Continue quotas from the returned head using a new operation ID.
- `control(ControlExperiment(...))` uses the last returned control sequence for
  pause, resume (`ready`) or terminal cancel. Fork to continue a cancelled run.
- `query(context, sequence=None)` returns manifest, current durable control and
  the selected retained boundary. `checkpoints(context, after=..., limit=...)`
  pages sparse checkpoint indexes without dropping intervening history.
- `status(request)` resolves exact opening/fork/control/advance requests without
  running models. Advance status distinguishes unknown, running confirmed progress
  and final outcomes. Reused IDs with another payload/action fail.
- `replay(ReplayExperiment(...))` selects a checkpoint and validates intervening
  recorded history. `mode='verify'` executes the matching runtime using retained
  draws and compares complete state, transition and accepted-result digests;
  it starts before a checkpoint target so that target is verified too. Missing
  runtime is an explicit error, while `recorded` reads remain data-only.
- `fork(ForkExperiment(...))` starts from a chosen confirmed state. Set the plan's
  opening day to that state's day and include only subsequent events/adoptions.
  Keep opening revision, calendar and mechanism schedules. Use `preserve` or
  `new_realization` with an explicit seed; parent history is immutable.

Checkpoint, boundary, accepted evidence and child operation outcome commit in one
SQLite transaction. An aggregate advance command can span multiple such commits;
its immutable intent and per-child operation records recover uncertain progress.
Sparse checkpoint indexes and optional caches never own explanation history.
Cancellation of staging commits no partial boundary. Cancellation/control between
boundaries returns the last confirmed head. A chunk cancelled by a hook resumes
with a new command ID; a completed command always replays its original outcome.
