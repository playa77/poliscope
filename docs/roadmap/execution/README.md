# Implementation execution ledger

Implementation began on 2026-10-17 at base
`4b9cac6fd994491db92518fccebf4e9142b42e03`. The planning registers remain the
scope authority; this directory records execution rather than rewriting their
historical baseline. WP-001 and G0/M0 planning acceptance are complete under SV; WP-002 adds the
minimal desktop/managed-engine scaffold ([evidence](WP-002.md));
no application milestone has passed. [Parent acceptance](WP-001.md) records the
full checklist, evidence and explicitly permitted named decision blockers.

## Allocation and current queue

One development agent is available: Codex `/root`, controlled by the requesting
repository user through this chat. The user authorized starting the roadmap.
Execution is sequential; no additional agents or external issues are allocated.
Validation route: SV, with a separate inspection pass and deferred agent review.
Delivery uses one full WP per task, a branch from current `main`, completed
checks, a commit and push, and a regular non-draft PR against `main`. The handoff
includes that PR URL; an uncommitted workspace is not a delivered package.
The existing `/workspace/poliscope` checkout is reserved to this sole agent;
there are no competing writers or application runtime data. Future concurrent
allocations require isolated checkouts and nonoverlapping write reservations.

Execution includes the following bounded children. Parent acceptance still
requires all its original deliverables, including full leaf traceability.

| Child | Status | Dependencies | Scope / next action |
|---|---|---|---|
| WP-001-baseline | solo-validated; agent review deferred | None | Package template, execution ledger and machine-readable gate selection; [evidence](WP-001-baseline.md) |
| WP-001-requirements | solo-validated; agent review deferred | WP-001-baseline | 1,053 clauses, all 34 top-level mappings, all 68 planning parents, 178 candidate child scopes and concrete early DAG; see [traceability](traceability.md) |
| WP-001-decisions | solo-validated; agent review deferred | WP-001-requirements | DEC-01–12 dispositions, initial domain inventory, benchmark definitions, RT-01–14 ownership, resource forecast and allocation dry runs; see [decisions](decisions.md) |
| WP-002-layout/python/desktop/commands | verified; solo-validated; agent review deferred | WP-001 merged at `ab9d957` | Sequential child contracts and evidence in [WP-002](WP-002.md) |
| WP-002 parent | verified; solo-validated; agent review deferred | WP-001 verified | Full scaffold, frozen installs, root commands and native bootstrap shell; [scope/evidence](WP-002.md) |
| WP-003 harness/CI/integration | solo-validated; agent review deferred | WP-002 merged at `d86aa12` | Candidate-bound evidence, isolated fixtures and Linux CI; [scope/evidence](WP-003.md) |
| WP-005-wire | verified; solo-validated; agent review deferred | PR #9 merged at `3cac56b` | Protocol-1 contract merged in PR #10 at `e0e1828`; [scope/evidence](WP-005-wire.md) |
| WP-005-world | verified; solo-validated; agent review deferred | PR #10 merged at `e0e1828` | Bounded world inspection DTOs, generated schemas and shared fixtures; [scope/evidence](WP-005-world.md) |
| WP-005-evidence | verified; solo-validated; agent review deferred | PR #11 merged at `1775a36` | Evaluation coverage/findings, source/assumption lineage and traces; [scope/evidence](WP-005-evidence.md) |
| WP-009-store | verified; solo-validated; agent review deferred | PR #12 merged at `5009987`; WP-002 / WP-005-wire | Versioned SQLite transaction foundation; [scope/evidence](WP-009-store.md) |
| WP-010-transport | verified; solo-validated; agent review deferred | PR #13 merged at `3785021`; WP-002 / WP-005-wire | Production stdio producer and main consumer; [scope/evidence](WP-010-transport.md) |
| WP-010-history-read | verified; solo-validated; agent review deferred | PR #14 merged at `0b828b5`; WP-005-evidence / WP-009-store | Bounded schema-1 trusted historical reader and main-only launch; [scope/evidence](WP-010-history-read.md) |
| WP-011-shell | verified; solo-validated; agent review deferred | PR #15 merged at `b56f7cf` | Selected historical evidence desktop; PR #16 merged at `51b6764`; [scope/evidence](WP-011-shell.md) |
| WP-011-ipc | verified; solo-validated; agent review deferred | PR #16 merged at `51b6764` | Named IPC validation, bounded errors, production resource/permission policy and hostile renderer checks; [scope/evidence](WP-011-ipc.md) |

| WP-006-numeric | verified; solo-validated; agent review deferred | WP-005-world merged at `1775a36`; base PR #17 at `1a2b343` | Exact Decimal/unit/account semantics and residual transfer staging; [scope/evidence](WP-006-numeric.md) |

Reassess ready work and available agents at each boundary. Record owner,
controller, scope, dependencies, exact upstream SHA, validation route and
acceptance criteria before starting the next child. Existing active assignments
stay fixed for all six capacity changes in delivery §7. Unexpected interruption
preserves the assignment and checkpoint; a replacement needs a separate recovery
record. No speculative completion date is assigned.

## Executable gate manifest

`gates.json` version 1 transcribes verification §5.1 exactly. Each application
case carries its scope, first gate and production prerequisite. Gate selections
are cumulative: a complete G2 run includes G1's mandatory application case.
G0 has no application cases. Setup/contracts/native/domain/provider acceptance
requirements remain additional obligations in the verification matrix.

Run from the repository root with Python 3.12 (no dependencies):

```sh
python3 scripts/check_roadmap.py
python3 scripts/check_baseline.py
python3 -m unittest discover -s tests/roadmap -v
python3 scripts/check_roadmap.py --selection path/to/selection.json
```

A full G1 selection has this shape (illustrative target, not an existing test):

```json
{
  "version": 1,
  "gate": "G1",
  "cases": [
    {
      "id": "E2E-012.a",
      "service": "production",
      "tests": ["tests/desktop/security.spec.ts"]
    }
  ]
}
```

The checker fails for source/manifest drift, omitted/duplicate/unknown cases,
zero selections or empty test targets, future cases and declared mock services.
It validates selection metadata only. It does not run targets, establish that
they exist, inspect production calls, or turn claimed metadata into evidence.
WP-003 must connect this contract to actual collected/executed tests, candidate
identities, outcomes and production-service checks. Impact-based regression
selection and evidence reuse need separate recorded justification; this tool
checks full cumulative gate runs only. No fabricated passing selection is stored.

Full WP-001 manifests, maintenance rules and source clause boundaries are
documented in [traceability](traceability.md). Release scope is frozen in
`release-inventory.json`; performance targets/method are in `benchmarks.json`.
[Decisions and blockers](decisions.md) and the [resource forecast](forecast.md)
complete the baseline. `candidate.json` identifies the exact local source tree
used for the recorded results; no commit/merge is implied by a tree digest.

## Access and external prerequisites

| Prerequisite | Observation / owner / blocking point |
|---|---|
| Repository refresh | Pull succeeded; HEAD matches origin/main at the base SHA; Codex / each package start |
| Python | 3.12.14 available for bootstrap checks; WP-002 owns frozen uv setup |
| Node/uv dependencies | WP-002 pins exact tools and dependency locks; see its clean-checkout evidence |
| Native runners/signing | Unverified; WP-004 inventories Windows x64, macOS arm64/x64 and Linux x64; blocks native claims |
| Corpus license/inventory | Unverified; WP-025 owns pinned source/license evidence; blocks redistribution, not synthetic tooling |
| Reference benchmark desktop | Definitions frozen; PERF-REF-001 records exact native machine selection/measurement prerequisite for WP-019/051 |
| Provider credentials/paid checks | Not requested or inspected; WP-050 needs explicit bounded authorization for live checks |
| Independent agent review | Deferred under SV; no independent approval is claimed |

Templates live in `.github/ISSUE_TEMPLATE/work-package.md`. Creating this local
template sends no external messages and creates no hosted issues.

## Current boundary after PR #14

PR #14 merged WP-010-transport at `0b828b53d2c6a4642ffa8a31259065f98922d215`.
[WP-010-history-read](WP-010-history-read.md) completes the bounded independent
saved-evidence reader on that baseline. One sequential agent and SV validation
remain in effect. The reader's main-owned grant is not a public renderer access
boundary. Reassess WP-011-shell next for historical-mode presentation, single-child
replacement and selected-store authorization; IPC sender validation and full
lifecycle/application gates retain their own acceptance. WP-005-timeline/privacy
remain blocked on their recorded providers. No application gate is claimed.

## Current boundary after PR #15

PR #15 merged WP-010-history-read at `b56f7cf`. The current sequential allocation is
[WP-011-shell](WP-011-shell.md): main-owned store selection, historical presentation,
single-child replacement, reconnect and per-data-directory instance ownership.
WP-011-ipc remains subsequent work; no application gate is claimed.

## Current boundary after PR #16

PR #16 merged WP-011-shell at `51b6764b881d977194c30e1ed8fc359caa2f58a3`.
[WP-011-ipc](WP-011-ipc.md) completes the sequential bounded desktop IPC/resource
boundary on that baseline, including packaged hostile-content/sink and caller
checks. One sequential agent and SV validation remain in effect. Future service
groups, source-link/fetch UI, OS sandbox enforcement and native release gates
retain separate acceptance. Reassess WP-006-numeric and WP-004-probe next; no
application milestone is claimed.

## Current boundary after PR #17

PR #17 merged WP-011-ipc at `1a2b343f1a260f6b64fc427cfa17088959c78f84`.
[WP-006-numeric](WP-006-numeric.md) delivers the next ready sequential package:
canonical exact arithmetic, immutable units/time/population semantics and pure
quantized account transfer candidates with explicit residual balances. One agent
and SV validation remain in effect. Spatial aggregation, store publication,
calendar selection and domain mechanisms retain their own acceptance. Reassess
WP-007-identities and WP-004-probe after merge; native runner availability still
limits platform claims. No application milestone or full parent gate is claimed.

## Current boundary after PR #18

PR #18 merged WP-006-numeric at `1195f1ce4636e28eaa0142f98806820cab028619`.
[WP-007-identities](WP-007-identities.md) delivers the next sequential child:
immutable canonical identity registry, explicit population roles, unique state
owners and partition-bound pure candidate validation. One agent and SV inspection
remain in effect. Reassess WP-007-membership next for containment, overlapping
membership and aggregation. Account spending, external interface mechanisms,
durable world repositories and full parent/application gates remain separate.
