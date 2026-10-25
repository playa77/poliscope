# WP-036-boundary-store — Atomic confirmed-boundary persistence

Allocated 2026-10-25 to sequential Codex `/root`, controlled by the requesting
repository user, on `codex/wp-036-boundary-store`. Base/main reconciled by fetch
and fast-forward: `a92b7cb950108a534451126a591fa898c6ea5783` (PR #103). No stash,
existing edits, lock changes or discarded user work. The initial mistaken WP-033
edits were removed before this allocation; they are not part of this delivery.

The user explicitly authorized the early child: **“Yes, deliver the required
boundary-store child first”**. [The required early-production route](../distributed_delivery.md#41-required-early-production-children)
requires this provider before WP-034 acceptance; WP-036's remaining parent work
continues to depend on WP-034/035. Full parent completion is not claimed.

Prerequisites in this base: actual schema-1 `Store` transactions and immutable
records (WP-009-store); real `Revisions.read/evidence/create/preview/apply` and
payload-bound outcomes (WP-018); merged WP-033 contracts, schedule traversal,
accepted-delta verification and staging (`d42791a` / PR #103). WP-005-timeline's
required data contracts exist through that WP-033 delivery. No synthetic provider
is substituted for these production paths.

Contract version 1. Write scope: engine boundary contracts/repository, bounded
storage blobs, generated boundary artifacts/generator, focused engine/harness
tests, the explicit-authorized-child receipt guard and execution records.
Validation route: **solo-validated; agent review deferred**, including a separate
inspection pass. A fresh author session is not independent or scientific review.

## Acceptance and validation route

- Opening snapshots and fixed schedule/model identity come from actual committed
  design revisions, not caller-provided opening snapshots or previews.
- Every confirmation atomically persists state, complete accepted-result/trace
  closure, due/event/adoption outcomes, immutable head journal and exact
  context/payload-bound operation result before return/publication.
- Stale requests, substituted evidence, invalid host invariants, missing validators,
  skipped required boundaries, cancellation and failures retain the last confirmed
  boundary. There is no queryable private candidate.
- Completed retries/status replay their original result before checking current
  head or requiring a numerical model/validator. ID changes, foreign contexts and
  changed payloads cannot reveal or overwrite another result.
- Real subprocess crashes immediately before/after commit reopen exactly the
  confirmed boundary. Cache eviction preserves evidence and operation outcomes.
- Focused and existing scheduling/revision/storage regressions, full engine suite,
  schemas/content/TypeScript, roadmap/baseline checks, guard failure fixtures and
  a separate author inspection provide the child evidence. G4 and native Windows
  transition/application acceptance remain open.

## Completed child evidence

All six receipt criteria passed. The **24 new boundary cases** use real schema-1
SQLite, the production revision/scheduling/evidence services and a separately
selected synthetic stock validator with an independent Fraction consumption
oracle. The additional workflow regression checks that only an explicit scoped
user authorization can deliver a child while leaving its parent open.

| Criterion | Evidence |
| --- | --- |
| Opening | `test_create_freezes_real_revision_plan_opening_and_complete_evidence` reads the actual accepted opening and retains its schedule, full inputs and evidence independently of caller mutations. Invalid opening/cancellation leaves no experiment or operation. |
| Atomicity | `test_failure_at_every_storage_write_discards_all_effects` injects a failure after every state/evidence/journal/operation write; all four cancellation checkpoints preserve original table counts and confirmed head. |
| Recovery | Real subprocess crashes use `os._exit` immediately before/after SQLite COMMIT. Reopen returns exactly sequence 0/1 respectively. Before-commit exceptions and lost acknowledgments recover by exact status/retry. Completed retries still return their original boundary after later head advancement and removal of validator/numeric registry. |
| Isolation | A second connection sees only the previous confirmed result at every write. Same-connection and same-store reentrant reads/status/retries fail during writes. A competing confirmed advance during validation wins once; the stale candidate cannot publish. |
| Schedule/state/evidence | Actual approved policy deltas and a dated condition event retain applied/conflicting/unsupported outcomes across reopen. Skipped daily boundaries, substituted closing evidence, unknown experiments, foreign stores, changed-payload/action ID reuse and invalid host invariants fail closed. Prior stocks/assets/cases, unrelated policies and design history survive. Large actual payloads use a compact operation binding; multi-chunk Unicode blobs detect corruption; cache eviction preserves retained results and operations. |
| Validation | Full Python/unit validation and separate author inspection below; all 24 boundary cases and the new authorization regression pass. |

## Executed validation

```sh
UV_CACHE_DIR=/tmp/poliscope-uv uv sync --frozen --python 3.12
npm_config_cache=/tmp/poliscope-npm ELECTRON_CACHE=/tmp/poliscope-electron npm ci
UV_CACHE_DIR=/tmp/poliscope-uv uv run --frozen pytest tests/engine/test_boundaries.py tests/engine/test_timeline.py tests/engine/test_storage.py tests/engine/test_revisions.py tests/harness/test_delivery_workflow.py -q
UV_CACHE_DIR=/tmp/poliscope-uv uv run --frozen python scripts/evidence.py engine --output artifacts/wp036-boundary-engine
UV_CACHE_DIR=/tmp/poliscope-uv uv run --frozen python scripts/evidence.py verify --output artifacts/wp036-boundary-engine
npm exec -- vitest run
UV_CACHE_DIR=/tmp/poliscope-uv uv run --frozen python -m unittest discover -s tests/roadmap -q
UV_CACHE_DIR=/tmp/poliscope-uv uv run --frozen python scripts/generate_contracts.py --check
UV_CACHE_DIR=/tmp/poliscope-uv uv run --frozen python scripts/build_content.py --check
npm run typecheck
UV_CACHE_DIR=/tmp/poliscope-uv uv run --frozen python scripts/check_roadmap.py
UV_CACHE_DIR=/tmp/poliscope-uv uv run --frozen python scripts/check_baseline.py
python scripts/check_review_record.py --base a92b7cb950108a534451126a591fa898c6ea5783
git diff --check
```

The full Python run passed **4,572 tests**, zero failures/skips, in 250.27 seconds.
Four existing hostile-input serializer warnings remain expected. Its exact
implementation fingerprint is
`fc65decfa4b8f7f879bbd7c7e7ab3308f7f59b4a7542749a37995c0cb3fc4c1c`, based on
`a92b7cb950108a534451126a591fa898c6ea5783`, and its evidence verified before
receipt/documentation finalization. All **232 Vitest** and **51 roadmap unittest**
cases passed. Contracts, immutable content, types, roadmap/baseline and whitespace
checks passed. The last reentrant-query regression ran in the full suite after
the earlier affected selection; this is included in the 24-case boundary total.

Only execution documentation/receipts and the child execution status change after
the verified full run; engine, tests/helpers, scripts, generated schemas/types and
locks retain their tested contents. Reuse follows the verification matrix's
impact rule; CI creates fresh delivery-HEAD evidence. Setup initially encountered
read-only home caches; explicit `/tmp` cache directories resolved it without lock
changes. Commands needing network used the command sandbox's network permission,
with the configured proxy and trust settings preserved.

Separate author inspection traced committed-source validation, schedule identity,
closing-state/evidence binding, model/runtime freeze, all precommit failures,
write-lock head checks, immutable state/evidence chunks, payload/context binding,
replay-before-availability checks, cache independence and data-only historical
reads. It identified and fixed same-connection read-your-own-writes exposure;
public reentrant queries now fail before seeing staging. It also identified that
full request bindings could exceed the storage row bound; a canonical request
digest now binds the complete retained payload, verified with actual large data.
The explicit child guard requires the scoped user instruction, a changed child
and parent record, passing child evidence and an open parent; ordinary undeclared
partial handoffs still fail. This is author inspection, not nonauthor review.

Handwritten engine/contracts/storage additions: **447 lines**; desktop: **0**.
Tests and fixture helpers: **529 lines**; standalone new source fixtures: **0**.
Generated schema/types/inventory: **5,777 lines**. Script additions/deletions:
**19/3 lines**. Execution/API documentation is separate from those counts.

## Remaining parent work and next action

This delivery is only WP-036-boundary-store. It exposes trusted-host Python APIs;
there is no new renderer scheduling endpoint or permissive production transition
validator. WP-034 must supply actual finite-capacity/conservation/ownership/model
validation. No source transition model or scientific capability is activated.
Full WP-036 checkpoints, stochastic identity/replay, retrospective experiment
forks, progress/pause workflows and parent/cumulative G4 acceptance remain open.
Native Windows and packaged desktop behavior were not rerun for this engine-only
provider. After this child is reviewed and merged, allocate the full WP-034
parent from current main with the provider's exact merged SHA. Do not merge
without the user's authorization.
