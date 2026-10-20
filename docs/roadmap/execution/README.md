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
| Native runners/signing | Unverified; WP-004 inventories Windows x64 and Linux x64; blocks native claims |
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

## Current boundary after PR #19

PR #19 merged WP-007-identities at `e8f0c65`. The next sequential allocation is
[WP-007-membership](WP-007-membership.md): independent relationship snapshots,
containment validation, explicit direct membership and exact canonical union
aggregation. One agent and SV inspection remain in effect. External interfaces,
account spending, durable publication and full parent/application acceptance
remain separate. Reassess WP-008-packs and WP-004-probe after this child merges.

## Current boundary after PR #20

PR #20 merged WP-007-membership at `cbf71c1a72673346cd3ed705ecb1b1c99c3ea9a5`.
[WP-008-packs](WP-008-packs.md) is the next sequential allocation: bounded data-only
pack archives, source/license integrity, versioned identity/dependency contracts,
and explicit uncertainty relationships. One agent and SV inspection remain in
effect. Reassess WP-012-contract after merge. Production content, trusted numerical
mechanisms, persistence and full application/native gates remain separate.

## Current boundary after PR #21

PR #21 merged WP-008-packs at `b946dbf30e65b039d6c7868d3db204f5c99c1301`.
[WP-012-contract](WP-012-contract.md) delivers the next sequential child: versioned,
data-only mechanism declarations, typed scoped ports, owned state, claims and
allocation dependencies, explicit support/coverage and evidence/fixture metadata.
One agent and SV inspection remain in effect. Reassess WP-012-registry after merge
for trusted registration, external reference resolution and activation checks;
WP-012-expressions retains bounded graph/operator validation and execution.
No scientific, full-parent or application acceptance is claimed.

## Current boundary after PR #22

PR #22 merged WP-012-contract at `683e9a371712d20d114057f3b7c139a83a8829ea`.
[WP-012-registry](WP-012-registry.md) delivers immutable registration, trusted
implementation and review checks, external reference resolution, exact pack
attachment, typed cross-domain bindings and owned-state proposal guards.
One sequential agent and SV inspection remain in effect. Reassess
WP-012-expressions after merge for bounded graph validation/execution. Runtime
evaluation, durable state publication and full parent/application acceptance
remain separate; scientific validity is not established by registration.

## Current boundary after PR #23

PR #23 merged WP-012-registry at `862ad9cb45550bb07a6e60438abc1d7279fdf41e`.
[WP-012-expressions](WP-012-expressions.md) is the next sequential allocation:
bounded data-only operator DAGs, typed exact arithmetic, missing propagation and
graph-content-bound review. One agent and SV inspection remain in effect.
Policy resolution, cross-mechanism runtime/solver execution and durable state
publication retain separate acceptance; no application gate is claimed.


## Current boundary after PR #24

PR #24 merged WP-012-expressions at `487a28348c40f75e82bf2e46ed184b56295a9c03`.
[WP-013-policy](WP-013-policy.md) delivers scoped institutional resolution:
mechanism-declared exclusive/composable/bounds/delegation semantics, explicit
jurisdiction, host-selected authority/scope rules, and typed inspectable conflicts.
One sequential agent and SV inspection remain in effect. Reassess WP-015-accounts
after merge. Finite allocation, numerical graph compilation, durable publication
and full parent/application acceptance remain separate; no scientific claim.

## Current boundary after PR #25

PR #25 merged WP-013-policy at `2048425e20a1a1b32dc6033f712cd390925e3202`.
[WP-015-accounts](WP-015-accounts.md) delivers shared account materialization:
strict actual-posting/claim/reservation contracts, exact quantum conservation,
single-deduction physical holds, inspectable unmet demand and disjoint subtotals.
One sequential agent and SV inspection remain in effect. Reassess
WP-015-allocation after merge for declared finite procedures, access/funding and
transformation actuals. Numerical graph integration, durable publication and full
parent/application acceptance remain separate.

## Current boundary after PR #26

PR #26 merged WP-015-accounts at `69f6772802cf9a9ec86bf7df0ae16738d0977879`.
[WP-015-allocation](WP-015-allocation.md) delivers declared global priority and
ordered all-or-nothing procedures, separate access/funding/entitlement budgets,
reservation fulfillment and exact actual-input product/residual/loss accounting.
One sequential agent and SV inspection remain in effect. Reassess WP-014-compiler
after merge for typed claim/allocation/actual-output dependencies. Coupled graph
solving, durable publication and full parent/application/native acceptance remain
separate; no default civic rule or scientific validity is inferred.

## Current boundary after PR #27

PR #27 merged WP-015-allocation at `4db0de133c5fad0b8c47012579770a685a97278c`.
[WP-014-compiler](WP-014-compiler.md) delivers review-gated typed static dependencies,
shared account/claim/allocation/actual-consumption expansion, production feedback,
stable condensation ordering and explicit unresolved cycles. Institutional and
documentary cycles remain separate. One sequential agent and SV inspection remain
in effect. Reassess WP-014-solvers after merge for declared finite/linear/iterative
execution and actual-output/final-account integration. No numerical evaluation,
scientific validity or full parent/application/native acceptance is claimed.

## Current boundary after PR #28

PR #28 merged WP-014-compiler at `ad81c319388064c217b5ce232b0b60cd616a45ba`.
[WP-014-solvers](WP-014-solvers.md) is the next sequential allocation: reviewed
graph execution, declared Decimal linear and bounded iterative solvers, finite
allocation actuals and final-account staging. One agent and SV inspection remain
in effect. WP-016 retains precondition/policy/evaluation orchestration, coverage,
cache identity and durable publication. Coupled finite SCCs without an applicable
solver and missing joint funding procedures remain explicit unresolved states.
No scientific or application milestone acceptance is claimed.

## Current boundary after PR #29

PR #29 merged WP-014-solvers at `8c791c0`.
[WP-016](WP-016.md) is the next sequential allocation: pure evaluation orchestration,
explicit input/policy/precondition resolution, numerical/account integration,
coverage, distributions, trace dependencies and complete deterministic identities
with bounded host-local caching. One agent and SV inspection remain in effect.
The authoritative pure WP-016 scope excludes durable publication despite older
solver handoff notes; persistence remains WP-018/store work. Reassess WP-017 after
merge. Measurements, optional player targets, sampling, public IPC, native platform
and full application/scientific acceptance retain their own gates.

## Current boundary after PR #30

PR #30 merged the complete WP-016 evaluation/identity/cache package at
`bba4ead98bf26c3d04e6a49b3c31cfd0305ff39a`.
[WP-017](WP-017.md) covers both measurements and trace services: pure named
observations, optional isolated goals, typed findings, complete calculation and
accounting trace DAGs, detached accepted-evidence closure and classified public
projections. One sequential agent and SV inspection remain in effect. Reassess
WP-018 immutable revisions/preview/apply after merge; durable acceptance, IPC/UI,
portable archives and application/native/scientific gates remain separate.

## Current boundary after PR #31

PR #31 merged WP-017 measurements/traces at
`13dae88279e68c9b120a42a39887760bbd722d5b`.
[WP-018](WP-018.md) covers world creation/open/query, immutable revisions, pure
base-bound preview, transactional apply, accepted evidence and operation recovery,
plus rename/fork/undo/redo with retained alternate futures. One sequential agent
and SV inspection remain in effect. Reassess WP-019's independent headless slice
after merge; author-written service tests do not certify that independent gate.
Public IPC/UI integration, model migration, archives and application/native gates
retain separate acceptance.


## Current boundary after PR #32

PR #32 merged WP-018 immutable revisions/preview/apply at
`3114c5f3b9dff81a0a3d8717a986765ee786f7de`.
[WP-019](WP-019.md) completes the independently derived synthetic headless slice
under the existing sequential SV route: production create/query/evaluate/preview/
apply/trace/undo/fork/reopen, finite stock and labor, recovery, retained alternatives,
complete accepted evidence, explicit M2 engine subcase selection and four detected
invariant mutations. It also corrects the discovered dated-capacity/undated-stock
integration gap and versions evaluator semantics. No renderer, provider, native,
scientific or full application gate is claimed. Reassess WP-020 creation/navigation
after merge. Reference-desktop and scaled benchmark acceptance remain open.

## Current boundary after PR #33

PR #33 merged the independently derived WP-019 headless slice at
`d0509d2`. [WP-020](WP-020.md) is the full sequential creation/navigation allocation:
production revision-backed local sandbox creation and reopen, explicit editable
reference conditions, shared selected-state context, twelve-domain navigation,
scoped Python queries, retained-revision presentation and main-owned IPC grants.
One agent and SV inspection remain in effect. Reassess WP-021 interviews,
alternatives and preview/apply UI after merge; these controls, domain numerical
models, simulation checkpoints and provider integration retain separate acceptance.
No scientific or cumulative application/native milestone is claimed.

## Current boundary after PR #34

PR #34 merged WP-020 sandbox creation/navigation at
`478611041fd620413fa82fdf7f3e56957c7e67af`.
[WP-021](WP-021.md) allocates the complete cards, preview-ui and proposals parent
to one sequential owner with SV inspection. Original synthetic contextual templates
reuse the Definition content contract; no society corpus is inferred. Condition
variants and qualitative commitments use the production immutable preview/apply
service. Full alternatives retain original wording, scope, origin/evidence,
requirements and model gaps; private rationale is separately stored behind
classified references. Numerical social mechanisms, imported corpus, indicators,
comparison tools and the full offline/application gate retain their later packages.
Reassess WP-022 after merge; independent agent review remains deferred.

## Current boundary after PR #35

PR #35 merged WP-021 interviews and guarded preview/apply at
`3452af0388761954f7672b3d5179d4209c507b7c`. [WP-022](WP-022.md) is the full
sequential overview/inspectors allocation on that refreshed baseline. It reads
retained evidence independently of numerical callbacks, preserves scoped diagnostic
and coverage semantics, exposes exact accounts/distributions and paged calculation
lineage, and compares optional session targets after evaluation. One agent and SV
inspection remain in effect. Indicator visibility and exploratory session targets
are temporary presentation state; accepted goals/commitments retain their original
revision. Reassess WP-023 after merge. Domain model/corpus, portable exports,
provider services and cumulative application/native/scientific gates remain separate.

## Current boundary after PR #36

PR #36 merged WP-022 overview and evidence inspectors at
`c59b00910387a21a2ce07c23409a05e101de152a`. [WP-023](WP-023.md) is the full
sequential history/contract/comparison allocation on that refreshed baseline.
It exposes lineage, archived alternatives, explicit local-only rationale reads,
undo/redo/rename/historical fork/restore and named retained futures. Data-only
comparisons use accepted results and exact compatible Python deltas; missing or
incompatible quantities retain reasons, independently of trace availability.
One agent and SV inspection remain in effect. Reassess WP-024's complete offline
milestone manifest after merge; native/scientific and other cumulative gates are
not implied by this package's synthetic Linux checks.


## Current boundary after PR #37

PR #37 merged WP-023 at `59e35302bf12fb009ac35e256aea0a71681fcc3c`.
[WP-024](WP-024.md) allocates the complete integrated offline validation package
to the same sequential owner under SV. Exact G2 subcases, actual bundled engine/
SQLite, offline and fault/keyboard workflows are required. Native feasibility,
independent review and COL-04 identity replacement remain explicitly unclaimed.

## Current boundary after PRs #38 and #39

PR #38 merged WP-024's exact offline application selection at
`1e11f307e93e191ca2720cc02e338b10d0f9670b`; PR #39 merged the owner's Windows x64 /
Linux x64 platform scope at `17be59874470ddf91f8b4c9273bf23036f074b57`.
[WP-025](WP-025.md) allocates the complete sequential corpus inventory/importer
package to Codex `/root` under SV. The exact source revision is available with
an MIT notice; every map leaf and ledger alternative is accounted for in the
[pinned inventory](society/inventory.json) and [source review](society/review.md).
Model/evidence review, production catalog build/activation and domain numerical
coverage remain WP-026 and subsequent packages. Native Windows evidence and
COL-04 identity replacement remain open; this continuation does not satisfy them.

## Current boundary after PR #40

PR #40 merged WP-025 at `4cbd13d4815a3d2914cddbfa9ee8381e0d6ddd6b`.
[WP-026](WP-026.md) allocates the complete sequential content build/validation,
host-reviewed activation and setup package to Codex `/root` under SV. Immutable
source/catalog/evidence artifacts retain original alternatives and licenses;
branch gaps and blocked source models remain explicit. Neutral conditions and
optional qualitative reference setups impose no player policies or goals.
Reassess WP-027 domain conformance/interface ownership after merge. Empirical
model approval, domain numerical coverage, historical setup UI, Windows evidence
and COL-04 identity replacement retain their separate acceptance.

## Current boundary after PR #41

PR #41 merged WP-026 immutable content/review activation at
`b86e365d6488bbcc744b839c7a17932bccd50e15`.
[WP-027](WP-027.md) allocates the complete domain contract/conformance parent to
Codex `/root`, one sequential agent under SV. Shared fixtures preserve canonical
resource/account/asset/cohort/institution identities; the harness uses production
mechanism, world, policy, account and pure evaluation services. All twelve domain
and 38 branch templates retain explicit missing behavior; 44 counterpart pairs
retain pending acceptance and designated domain-package integration ownership.
Real domain models, empirical review, WP-034 transition scheduling/publication,
Windows native evidence and cumulative G3/M3 acceptance remain separate.
Reassess WP-028 decision atlas/search after merge; independent agent review is
deferred under the existing SV route.

## Current boundary after PR #42

PR #42 merged WP-027 shared domain conformance at
`54ca36dc74b7e7ceb155f7c1ed9c246c4a12f153`.
[WP-028](WP-028.md) allocates the complete decision atlas and full question/
alternative search package to Codex `/root`, one sequential owner under SV.
Source adoption remains historical context; source-maintenance records remain
provenance. Retained player commitments use archived complete alternatives;
read-only discovery shares the selected revision/scope and the existing guarded
interview preview/apply path. Numerical domain models, paired-domain acceptance,
Windows native evidence and cumulative G3/M3 remain separate. Reassess WP-029
sparse matrices after merge; independent agent review remains deferred.
