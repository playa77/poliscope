# Poliscope — Distributed Delivery Plan

Revision 0.2 · 2026-10-16 · Execution plan for two concurrent contributors, expandable to three. All implementation packages remain **not started**. Parent: [roadmap](../implementation_roadmap.md); requirements: [shared packages](work_packages.md), [domain packages](domain_work_packages.md), [verification](verification_matrix.md).

## 1. Team and work boundaries

The baseline allocation comprises contributors A and B. Each uses an independent clone, Python environment, Node dependencies, application user-data directory, SQLite database and credentials. Versioned fixtures and source definitions are distributed through Git. The runtime architecture remains as specified in T §§2 and 11.

A owns the engine stream, B the desktop stream. Both implement assigned domain modules and review the other's work. C has the assignments specified in the three-contributor matrix. Names, expertise, IANA time zones, available hours, working days, next review window, repository permissions and native runner access are filled in WP-001. Where expertise suggests a better allocation, swap named slots or record a specific transfer before work starts.

Agent-assisted work follows the same child ledger, path ownership and review controls. The supervising contributor remains accountable for submitted changes. Concurrent tasks use isolated worktrees and exclusive child/path claims. Capacity forecasts include only allocated contributor availability.

## 2. All-package assignment matrix

Each cell specifies **accountable owner / independent peer reviewer**. The owner coordinates child allocation, integration and evidence. Child authorship follows the producer/consumer allocation in §3. Assign contributor names and required specialties in the issue ledger before implementation.

In the three-contributor allocation, C owns the assigned content, evidence and integration packages. A/B retain engine/desktop stewardship, domain conformance code and desktop adapters. All contributors follow the same WIP limits.

| Package | Two developers | Three developers |
|---|---|---|
| WP-001 | B / A | B / A |
| WP-002 | B / A | B / A |
| WP-003 | B / A | B / A |
| WP-004 | B / A | B / A |
| WP-005 | A / B | A / B |
| WP-006 | A / B | A / B |
| WP-007 | A / B | A / B |
| WP-008 | A / B | C / A |
| WP-009 | A / B | A / B |
| WP-010 | B / A | B / A |
| WP-011 | B / A | B / A |
| WP-012 | A / B | A / B |
| WP-013 | A / B | A / B |
| WP-014 | A / B | A / B |
| WP-015 | A / B | A / B |
| WP-016 | A / B | A / B |
| WP-017 | A / B | A / B |
| WP-018 | A / B | A / B |
| WP-019 | B / A | C / A |
| WP-020 | B / A | B / A |
| WP-021 | B / A | B / A |
| WP-022 | B / A | B / A |
| WP-023 | A / B | A / B |
| WP-024 | B / A | B / A |
| WP-025 | B / A | C / A |
| WP-026 | B / A | C / A |
| WP-027 | A / B | A / C |
| WP-028 | B / A | B / A |
| WP-029 | A / B | A / B |
| WP-030 | B / A | B / A |
| WP-031 | B / A | B / A |
| WP-032 | B / A | C / A |
| WP-033 | A / B | A / B |
| WP-034 | A / B | A / B |
| WP-035 | A / B | A / B |
| WP-036 | A / B | A / B |
| WP-037 | B / A | B / A |
| WP-038 | A / B | A / B |
| WP-039 | A / B | A / B |
| WP-040 | B / A | B / A |
| WP-041 | A / B | A / B |
| WP-042 | B / A | B / A |
| WP-043 | B / A | B / A |
| WP-044 | B / A | B / A |
| WP-045 | B / A | B / A |
| WP-046 | A / B | A / B |
| WP-047 | B / A | B / A |
| WP-048 | A / B | A / B |
| WP-049 | B / A | B / A |
| WP-050 | B / A | B / C |
| WP-051 | A / B | A / B |
| WP-052 | A / B | C / B |
| WP-053 | A / B | A / B |
| WP-054 | B / A | B / A |
| WP-055 | B / A | C / A |
| WP-056 | B / A | C / B |
| DOM-01 provisioning | A / B | A / C |
| DOM-02 economy | A / B | A / C |
| DOM-03 governance | B / A | B / C |
| DOM-04 law_conflict | B / A | B / C |
| DOM-05 social_organization | B / A | C / B |
| DOM-06 knowledge_culture | B / A | C / A |
| DOM-07 health | A / B | C / A |
| DOM-08 infrastructure | A / B | A / C |
| DOM-09 communication | B / A | B / C |
| DOM-10 environment | A / B | A / C |
| DOM-11 meaning_identity | B / A | C / B |
| DOM-12 security_risk | A / B | B / C |

A child authored by the parent's assigned reviewer must be reviewed by the other developer (or a competent nonauthor in three-person mode). Parent evidence aggregates the independently reviewed children; a parent review cannot override missing child review. Where both developers contributed to a feature, each reviews the other's changes and independently checks the fixture/derivation they did not author. External scientific review is explicitly required only when the claim needs expertise/evidence the team lacks; unsupported effects stay labeled gaps.

## 3. First handoffs and package splits

The following child work defines initial producer/consumer handoffs. Each child retains its parent's acceptance dependencies. The minimum scaffold and wire contract establish the initial boundary for parallel implementation.

| Child / owner | Start input | Deliverable for the other stream | Acceptance / peer |
|---|---|---|---|
| WP-001-plan / B | Current specifications and this revision | Named A/B availability, assignment ledger, ready queues, required checks and access/runner gaps | A checks model scope, critical dependencies and resource loading |
| WP-002-layout / B, A supplies Python portion | Reviewed WP-001 scope | Minimal npm/uv roots, exact locks, directory/module boundaries and README bootstrap that launches a minimal child | A reproduces JS setup; B reproduces Python setup in independent clean checkout |
| WP-003-bootstrap / B | Merged minimal scaffold | Engine/desktop harness entry points and candidate CI; initial checks exercise real bootstrap behavior | A verifies failures propagate; empty suites not accepted as readiness |
| WP-005-wire / A | Minimal scaffold/harness; reviewed boundary proposal | Pydantic handshake/read/result/error envelope, generated TS schema, decimal/unknown/version fixtures | B reviews/generates/consumes it; merge before consumer coding |
| WP-010-producer / A | Merged wire child | Real stdio handshake/read router with bounded protocol behavior | B checks actual child; storage-dependent behavior remains open |
| WP-010-consumer / B | Same merged wire child | Main child launcher, parser/correlation and fake-child failure harness | A checks launch/fragmentation boundary; no database acceptance from a fake |
| WP-011-shell / B | Wire/consumer fixture; documented security API | Secure main/preload and renderer connection/error shell | A reviews trust boundary; final acceptance uses real process/storage |
| WP-018-preview-contract / A | WP-005 plus WP-007/012/017 interface children | Create/query/preview/apply DTOs, stale/idempotency errors, versioned account/trace fixtures | B reviews consumer needs; apply semantics frozen before UI coding |
| WP-020/021-consumers / B | Approved preview contract and shell | Creation/interview/preview UI with fixture transport restricted to development/tests | A reviews; WP-024 later requires actual engine/database |
| WP-018-real / A | All parent's actual acceptance dependencies | Transactional real preview/apply/history and recovery services | B independently checks stale/lost-response paths and swaps UI to real operations |
| WP-023-engine / A; WP-023-view / B | Approved comparison/history fixtures; real dependencies for acceptance | Python compatible deltas, then branch/compare UI | Each reviews the other's child; A integrates parent evidence |
| WP-027-contract / A | WP-012 module contract and reviewed WP-008/026 pack fixtures | Domain IDs, owned-state/port declarations, shared accounts, positive/negative conformance examples | B (C when active) reviews; domain coding may start, static acceptance waits for real WP-027 dependencies |
| WP-034-boundary / A; WP-037-view / B | Approved calendar/event/progress/cancel fixtures | Atomic transition API and timeline consumer in parallel | Real replay/atomicity required before M4 acceptance |
| WP-039-format / A; WP-039-dialogs / B | Approved archive/privacy/version fixtures | Versioned data-only archive producer/validator and main-owned file/UI consumer | No round-trip acceptance before real experiments and import transaction |
| WP-046-context / A; WP-046-tools / B | Approved context/tool/proposal/error schemas | Python fact/context assembly and main-owned tool adapter | Nonauthor reviews each child; no tool may apply |
| WP-048-ledger / A; WP-048-events / B | Approved usage/money/cancel fixtures | Decimal reconciliation and provider usage events/settings | Independently derived cost fixture before integrated acceptance |

Deliver WP-005 incrementally by service boundary, according to consumer dependencies. WP-008's pack contracts and WP-027's conformance contract can be split ahead of full content activation/inventory. A synthetic minimum pack allows framework work; actual source content still requires WP-025/026 provenance/license review.

For other multi-language parents, apply the same producer/consumer split: A owns Python queries/writes/calculations; B owns main/preload/rendering/networking; parent owner integrates. Specify child ownership and dependencies before starting. The production process handshake is the initial W1 integration target. M1 completion requires its full acceptance evidence.

## 4. Parallel domain sequence and third-developer work

Once WP-027's contract child is merged, domain authors develop against common fixtures. Static acceptance still requires the full real harness, counterpart tests and content activation. Each domain first publishes ports/owned-state and a reviewed mechanism card, then implements static behavior, then integrates counterpart fixtures. It later implements selected transitions under WP-034. There is no requirement to finish a counterpart domain before starting the local module.

| Domain batch | A: two-person lane | B: two-person lane | Shared integration checkpoint |
|---|---|---|---|
| D1 | DOM-01 provisioning | DOM-03 governance | Stock/service claims and institutional capacity reference shared entities |
| D2 | DOM-02 economy | DOM-04 law_conflict | Entitlements/rights versus finite stock; conflicting authority explicit |
| D3 | DOM-08 infrastructure | DOM-05 social_organization | Facility reach and care/work/time demands use one capacity budget |
| D4 | DOM-10 environment | DOM-06 knowledge_culture | Shared land/stock and education resource/staff requirements |
| D5 | DOM-07 health | DOM-09 communication | Local service eligibility/reach and information delivery limits |
| D6 | DOM-12 security_risk | DOM-11 meaning_identity | Continuity/response and accommodation compete for real shared capacity |

B alternates ready domain and exploration/content children; A alternates projection/harness and domain children. Each batch produces a runnable combined fixture on current main, with unresolved ports recorded as gaps. Rerun affected fixtures as counterparts are integrated. WP-032 aggregates these results into the all-domain education scenario.

With C active, use the assignment matrix: A takes DOM-01/02/08/10, B DOM-03/04/09/12, C DOM-05/06/07/11. C prepares content/model cards and WP-025/026 while A/B establish their stream foundations, then alternates own domain children with paired conformance/evidence work. C's content, domain and verification work shares the capacity budget and WIP limit defined in the parent roadmap.

The W0–W7 table in the parent roadmap remains the acceptance sequence. In three-person W1/W2, C prepares WP-008/019/025/026 children against approved contracts. In W3/W4, C owns the four assigned domains, coverage ledger and WP-032 evidence. In W5/W6, C reviews content/archive/provider integration and prepares independent release fixtures while A/B finish their queues. In W7, C coordinates WP-052/055/056; A/B still execute their native/model/trust checks and peer-review C. Update milestone forecasts using measured capacity and the revised assignments.

## 5. Contract evolution and shared-file ownership

Contracts live with their canonical Pydantic definitions in the proposed `engine/contracts/`; `contracts/` contains generated schema/TypeScript/tool types and fixtures. WP-002 records the actual path once. A contract proposal records operation/port ID, context identity, units, input/result/error schemas, examples, producer/consumer owners, version and compatibility, and migration/retirement conditions. Fixture values are labeled synthetic, with independently derived numbers where needed; no duplicated TypeScript arithmetic.

1. Producer opens a small contract/fixture change with both affected consumers identified. Consumer reviews during its next working period. Both agree before dependent code begins.
2. Merge contract/fixtures and generated artifacts together. Consumers pin the merged commit/version in child records, then implement independently. Regenerate types from Python; do not hand-edit generated output.
3. Prefer additive changes with explicit missing/unknown behavior. Test current producer/current consumer plus the still-supported previous consumer/producer fixture combinations. Decimal strings and unknown status cannot silently change meaning.
4. A breaking change names a new protocol/schema/model identity as appropriate, migration or explicit rejection behavior, and a producer/consumer merge order. Keep an adapter/old path until affected consumers migrate and peer-reviewed removal is ready. If coexistence is unsafe, block old clients explicitly and merge a small coordinated producer/consumer change tested as a single candidate.
5. Delete old fixtures/adapters only in a separate reviewed retirement change. Preserve the specified historical inspection and migration behavior for existing saves and models.

| Shared area / proposed paths | Steward / backup | Concurrent editing rule |
|---|---|---|
| Canonical contracts, units, entity IDs, core reducers | A / B | One active boundary change per operation/state partition; consumer approval required |
| npm manifests/lock, Forge/Vite, main/preload, desktop CI | B / A | Dependency/config changes in dedicated PR; rebase and regenerate lock rather than merging lock text blindly |
| Python manifest/uv lock, engine core, migrations | A / B | Distinct migration IDs, check current main before allocation; never share a live dev DB; backups/migration fixtures accompany changes |
| Domain registry and shared account/port catalog | A / B | Domain authors own their module; registry additions use coordinated small changes, not rewrites in every domain branch |
| Content manifests, source/coverage index | B / A; C / A when active | Namespaced per-domain files, deterministic index build; manifest edits coordinated with content steward |
| Domain-local code/content/tests | Assigned domain owner / assigned reviewer | One active child per module path; cross-domain work goes through ports, not direct writes |
| Release/evidence ledger and workflows | B / A; C / B for evidence when active | Evidence names exact candidate SHA; CI workflow implementation remains B-owned |

Stewards coordinate changes and maintain documented invariants. Backups may author changes subject to independent review and CI. Path ownership controls overlapping edits; contract and paired-integration tests verify semantic compatibility. Implementation retains the monorepo and process boundaries specified in T §§2 and 15.

## 6. Asynchronous operating rules

Use GitHub issues and PRs as the delivery ledger during implementation. Package registers define the initial backlog. Record decisions, dependencies and handoffs in the shared ledger.

- **WIP:** each developer has at most one active implementation child and one active review; prepare at least one independent ready fallback. While a contract proposal awaits review, select an independent approved child, research task or fixture review.
- **Handoff:** at the end of an active working period, update the child with base SHA, branch/PR, changed paths/contract version, behavior completed, commands/results/evidence, next action, reviewer, blockers and specific decision needed. Express the next working window as a date/time interval with an explicit time zone.
- **Review:** acknowledge a request in the next scheduled working period; aim for a substantive decision within that period for a one-to-three-day child. Review targets follow recorded availability, leave and working calendars. If delayed, record a new window, use the ready fallback and reforecast blocked dependents. C may substitute only as a competent nonauthor.
- **Decisions:** implementation details within an approved contract are local owner decisions. Changes to shared state, boundaries, model claims, compatibility or product scope require a short written proposal, alternatives, affected packages and peer decision. Record an explicit peer decision. Refer unresolved product scope to the product decision owner with options and dependency impact; continue independent work.
- **Integration:** merge small reviewed children as they are ready; run a real cross-stream slice at least weekly and before every gate. Collect asynchronous evidence against the same candidate SHA. B coordinates the two-person checkpoint; C coordinates designated evidence once active. Rotate actual execution to prove both setups work.
- **Breakage:** stop merging affected changes, identify a fix/revert owner and keep main runnable. Preserve unrelated ready work. A working UI on one machine cannot waive a broken engine/contract job or another target's reported failure.

Handoff record template:

```text
Child / accountable owner / peer reviewer:
Base main SHA / branch or PR / proposed candidate SHA:
Changed paths / contract and fixture versions:
Behavior implemented / still unavailable:
Checks run / outcomes / evidence links:
Next action / blocked dependency / decision requested:
Next owner working window / next reviewer working window (time zone explicit):
```

## 7. CI, merge and environment safeguards

WP-003 implements the candidate checks and repository controls below. Submit changes through short-lived child branches and PRs. Require one independent approval and, for boundary changes, review by each affected consumer owner. Apply these controls to all contributor and agent-assisted changes.

Require a passing candidate containing current main: use a merge queue where available, otherwise update the branch with current main and rerun required checks before merge. New commits invalidate approval for changed behavior and stale candidate evidence. Configure branch protection and bypass policy explicitly. Where hosting settings or permissions prevent enforcement, record the gap and apply the same checks through a documented manual procedure.

Required checks: frozen installs/no lock drift; generated-contract drift and cross-language fixture compatibility; content integrity/licensing; Python invariants and independent numerical fixtures; TypeScript/main/provider mocks; actual Electron/child/SQLite smoke for changed boundaries. Boundary/domain changes run paired tests and the existing integration slice. Until reliable path filtering is proven, run the common suite. Native target smoke/replay evidence is required at the probe and release gates; ordinary PRs do not pay for live provider calls. Performance/accessibility/scientific evidence remains governed by the verification matrix.

Each environment records exact runtime/OS/architecture and pack versions. A fresh clone must bootstrap using committed npm/uv locks and documented commands, with no untracked generated files or another developer's local database. Use separate temporary user data per test run. Secret values remain in approved local/CI configuration; access to signing/provider credentials is not assumed for every contributor. Keep default tests offline and synthetic.

Before W2, verify clean setup in A's and B's independent environments. Before expanding domain implementation, verify an integrated producer/consumer operation from independently authored branches. Native support requires execution evidence for all four specified target combinations on provisioned native runners or machines.

## 8. Resource loading and evidence of collaboration

Use the roadmap's 60/20/10/10 capacity allocation as the initial budget. In the child forecast record implementation effort, author's correction effort, peer review effort, integration work, owner/reviewer availability, contract-ready date, external waiting time and uncertainty separately. Parent effort is rolled up once from children. Assign review and gate work to named contributors within their available capacity.

Track weekly: ready children per person, active work, review wait in working periods, blocked contract age, integration failures, shared-file conflicts, gate evidence freshness and changes in model/research scope. W1/M1 and M2 provide the first calibration. Re-estimate child work and rebalance queues if B's domain/UI/provider workload or A's engine load controls the finish. Measure throughput by accepted integrated deliverables.

Workflow acceptance requires the applicable COL-01–COL-06 evidence in the [verification matrix](verification_matrix.md). Setup, merge controls, compatibility and review-turnaround validation are **unrun** at this revision.
