# Poliscope — Delivery and Staffing Plan

Revision 0.3 · 2026-10-16 · Execution plan for one to three active contributors. All implementation packages remain **not started**. Parent: [roadmap](../implementation_roadmap.md); requirements: [shared packages](work_packages.md), [domain packages](domain_work_packages.md), [verification](verification_matrix.md).

## 1. Staffing configurations and invariants

Select the configuration matching current available contributors at any implementation stage. A/B/C are assignment slots mapped to named people in the delivery ledger. Slots may be rebound after a departure; any remaining qualified person occupies A in solo mode. Record effective dates, availability, access, current parent/child owners, validation mode and forecast impact. Temporary absence that removes committed review or implementation capacity triggers the same reassignment process.

| Active contributors | Execution | Validation | Coordination |
|---|---|---|---|
| 1 | A owns every parent and executes producer, consumer, content and domain children sequentially by dependency | Solo validation (SV), with independent peer review explicitly deferred | A maintains the ledger, decisions, risks, evidence and resume checkpoints |
| 2 | A/B split engine/desktop and assigned domains; approved children run concurrently | Assigned nonauthor review; independently derived fixtures and integration checks | B maintains delivery status; A maintains numerical/architecture decisions |
| 3 | A/B retain shared-engine/desktop boundaries; C takes listed content/domain/integration parents | Assigned nonauthor reviews, including affected consumers; C coordinates designated evidence | Responsibilities follow the matrix and recorded availability |

All configurations preserve one accountable owner per child, exclusive active path claims, versioned contracts, bounded WIP and the same functional acceptance requirements. Each environment uses an independent clone/worktree, Python environment, Node dependencies, user-data directory, SQLite database and credentials. Versioned fixtures and source definitions are distributed through Git. Runtime boundaries remain as specified in T §§2 and 11.

Agent-assisted tasks follow the same ledger, isolation and validation controls. The supervising contributor remains accountable. Agents do not increase the available human roster or provide independent peer approval. Required empirical expertise, native execution and provider access are recorded as external prerequisites when unavailable.

## 2. All-package assignment matrix

Each cell is **accountable owner / validation assignment**. `SV` denotes the solo-validation procedure in §3, not a reviewer identity. Two- and three-contributor cells specify an independent peer. Assign actual names before work starts. Parent ownership covers child allocation, integration and evidence; producer/consumer authorship follows §4. The selected column applies immediately after a recorded roster transition.

| Package | One contributor | Two contributors | Three contributors |
|---|---|---|---|
| WP-001 | A / SV | B / A | B / A |
| WP-002 | A / SV | B / A | B / A |
| WP-003 | A / SV | B / A | B / A |
| WP-004 | A / SV | B / A | B / A |
| WP-005 | A / SV | A / B | A / B |
| WP-006 | A / SV | A / B | A / B |
| WP-007 | A / SV | A / B | A / B |
| WP-008 | A / SV | A / B | C / A |
| WP-009 | A / SV | A / B | A / B |
| WP-010 | A / SV | B / A | B / A |
| WP-011 | A / SV | B / A | B / A |
| WP-012 | A / SV | A / B | A / B |
| WP-013 | A / SV | A / B | A / B |
| WP-014 | A / SV | A / B | A / B |
| WP-015 | A / SV | A / B | A / B |
| WP-016 | A / SV | A / B | A / B |
| WP-017 | A / SV | A / B | A / B |
| WP-018 | A / SV | A / B | A / B |
| WP-019 | A / SV | B / A | C / A |
| WP-020 | A / SV | B / A | B / A |
| WP-021 | A / SV | B / A | B / A |
| WP-022 | A / SV | B / A | B / A |
| WP-023 | A / SV | A / B | A / B |
| WP-024 | A / SV | B / A | B / A |
| WP-025 | A / SV | B / A | C / A |
| WP-026 | A / SV | B / A | C / A |
| WP-027 | A / SV | A / B | A / C |
| WP-028 | A / SV | B / A | B / A |
| WP-029 | A / SV | A / B | A / B |
| WP-030 | A / SV | B / A | B / A |
| WP-031 | A / SV | B / A | B / A |
| WP-032 | A / SV | B / A | C / A |
| WP-033 | A / SV | A / B | A / B |
| WP-034 | A / SV | A / B | A / B |
| WP-035 | A / SV | A / B | A / B |
| WP-036 | A / SV | A / B | A / B |
| WP-037 | A / SV | B / A | B / A |
| WP-038 | A / SV | A / B | A / B |
| WP-039 | A / SV | A / B | A / B |
| WP-040 | A / SV | B / A | B / A |
| WP-041 | A / SV | A / B | A / B |
| WP-042 | A / SV | B / A | B / A |
| WP-043 | A / SV | B / A | B / A |
| WP-044 | A / SV | B / A | B / A |
| WP-045 | A / SV | B / A | B / A |
| WP-046 | A / SV | A / B | A / B |
| WP-047 | A / SV | B / A | B / A |
| WP-048 | A / SV | A / B | A / B |
| WP-049 | A / SV | B / A | B / A |
| WP-050 | A / SV | B / A | B / C |
| WP-051 | A / SV | A / B | A / B |
| WP-052 | A / SV | A / B | C / B |
| WP-053 | A / SV | A / B | A / B |
| WP-054 | A / SV | B / A | B / A |
| WP-055 | A / SV | B / A | C / A |
| WP-056 | A / SV | B / A | C / B |
| DOM-01 provisioning | A / SV | A / B | A / C |
| DOM-02 economy | A / SV | A / B | A / C |
| DOM-03 governance | A / SV | B / A | B / C |
| DOM-04 law_conflict | A / SV | B / A | B / C |
| DOM-05 social_organization | A / SV | B / A | C / B |
| DOM-06 knowledge_culture | A / SV | B / A | C / A |
| DOM-07 health | A / SV | A / B | C / A |
| DOM-08 infrastructure | A / SV | A / B | A / C |
| DOM-09 communication | A / SV | B / A | B / C |
| DOM-10 environment | A / SV | A / B | A / C |
| DOM-11 meaning_identity | A / SV | B / A | C / B |
| DOM-12 security_risk | A / SV | A / B | B / C |

If a multi-contributor child is authored by the parent's assigned reviewer, assign a different nonauthor to that child. Each contributor reviews the other author's work when both contributed to a parent. In solo mode record SV per child and aggregate it in parent evidence. Model validity is assessed against documented evidence and assumptions in every mode; specifically required external expertise remains an acceptance prerequisite.

## 3. Validation and merge policy

### 3.1 Solo validation (SV)

Solo mode supports implementation, PR merge, milestone acceptance and release preparation subject to these controls:

1. Record the active roster and `SV` in the child/PR. State behavior, changed boundaries, applicable requirements and required checks before acceptance.
2. Derive expected numerical/procedural results separately from the implementation, using explicit worked examples, invariants or a distinct reference method. Commit the derivation with fixtures. Expected values generated by the code under test are insufficient.
3. Run required structural, engine, desktop, content, compatibility and affected integration checks on the candidate containing current main. Use a clean isolated checkout for setup/packaging evidence. Exercise applicable failure, stale/retry, privacy and recovery paths.
4. Perform a separate manual inspection after implementation/local checks, covering the final diff, contract/model identities, traceability, migration/recovery and residual risk. Record its checklist and outcome. This inspection is author validation, not independent peer review.
5. Record `solo-validated; independent review deferred`, candidate SHA, check results, reviewer availability, residual risk and the deferred review item. Link each item to the affected boundary/model and prioritize by consequence. Track the backlog at every checkpoint; sustained growth reduces optional implementation capacity.
6. Accept only when all applicable technical evidence passes. Missing required scientific evidence, specifically mandated external signoff, platform execution or authorized provider validation remains blocking for the affected claim/action. SV does not waive a product requirement or authorize release publication.

When a second or third contributor becomes available, assign deferred independent-review work to a competent nonauthor before optional new work. Review current affected behavior and historical evidence where needed; preserve the original SV record. Correct defects through ordinary validated children. A pending deferred review alone does not invalidate previously accepted evidence; discovered defects block affected gates until resolved.

### 3.2 Peer review and repository controls

With two or three active contributors, require one nonauthor approval and review by affected boundary consumer owners. The author cannot supply their own independent approval. Keep children small enough to assign a nonauthor; if all available contributors authored a change, split independently reviewable children or obtain a qualified external nonauthor review. A reviewer who becomes unavailable is replaced through §7; if staffing falls to one, the change follows SV and its approval status is relabeled explicitly.

All modes use short-lived branches, PR records and passing candidate checks containing current main. Use a merge queue where available; otherwise update/recheck the branch before merge. New behavior changes invalidate stale approval/evidence. WP-003 documents branch protection for each mode: one independent approval with multiple contributors; required checks plus recorded SV without a peer-approval requirement in solo mode. Mode changes are performed only by an authorized maintainer and are logged. If settings cannot be changed, record the permissions blocker and keep affected remote merges pending while independent work continues; do not report unavailable enforcement as active or bypass an enforced rule.

Release evidence names its validation mode. Required publication authorization, scientific claims, native/provider verification and product gates are unchanged by staffing level.

## 4. Initial handoffs and package splits

The following child work defines the initial producer/consumer boundaries. A/B authorship and peer references in this table describe multi-contributor allocations; **with one contributor, A executes every listed child and replaces peer approval with SV**. Parent ownership in three-contributor mode remains as specified in §2. Each child retains its parent's actual acceptance dependencies. Publish and validate the minimum scaffold and wire contract before consumer coding.

| Child / multi-contributor author | Start input | Deliverable for the other stream | Acceptance / peer |
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

Deliver WP-005 by service boundary according to consumer dependencies. WP-008's pack and WP-027's conformance contracts can precede full content activation/inventory. Synthetic packs enable framework implementation; source-derived content requires WP-025/026 provenance/license evidence. In solo mode author the contract/fixtures, producer and consumer as separate children; integrate the operation before moving to unrelated features. With more contributors, approved producer/consumer children may run concurrently. The production handshake is the initial W1 integration target; M1 requires its complete evidence.

## 5. Domain sequence and integration

Publish each domain's ports, owned state and mechanism card before implementation. Develop against validated WP-027 contract children; static acceptance requires the production harness, counterpart tests and content activation. Implement selected transitions under WP-034. Cross-domain acceptance edges do not impose circular development-start prerequisites.

| Batch | One contributor: sequential order | Two contributors: A | Two contributors: B | Shared checkpoint |
|---|---|---|---|---|
| D1 | DOM-01 → DOM-03 | DOM-01 provisioning | DOM-03 governance | Stock/service claims and institutional capacity share entities |
| D2 | DOM-02 → DOM-04 | DOM-02 economy | DOM-04 law_conflict | Rights/entitlements, finite stock and conflicting authority |
| D3 | DOM-08 → DOM-05 | DOM-08 infrastructure | DOM-05 social_organization | Facility reach and care/work/time share capacity |
| D4 | DOM-10 → DOM-06 | DOM-10 environment | DOM-06 knowledge_culture | Shared land/stock and education staffing/resources |
| D5 | DOM-07 → DOM-09 | DOM-07 health | DOM-09 communication | Eligibility, service reach and delivery limits |
| D6 | DOM-12 → DOM-11 | DOM-12 security_risk | DOM-11 meaning_identity | Continuity/response and accommodation share capacity |

One contributor alternates the next domain child with its required projections/content/view child, and integrates each batch before expanding. Two contributors alternate assigned domain children with shared-engine or content/UI work according to their resource queues. With three contributors, A takes DOM-01/02/08/10, B DOM-03/04/09/12, C DOM-05/06/07/11; use the same batch checkpoints and counterparts, with C's domains in a serial queue. Every configuration reruns affected earlier fixtures as counterparts land. WP-032 aggregates incremental results into the all-domain education scenario.

The parent roadmap's W0–W7 table defines all staffing execution modes. In three-contributor W1/W2, C prepares WP-008/019/025/026; W3/W4 adds assigned domains and WP-032 evidence; W5/W6 adds content/archive/provider review; W7 assigns C WP-052/055/056. All tasks share the same per-person capacity and WIP limits. Staffing changes resume the next unfinished child under the selected configuration, preserving accepted domain work.

## 6. Contracts, shared paths and asynchronous work

Canonical Pydantic definitions reside in proposed `engine/contracts/`; `contracts/` contains generated schema/TypeScript/tool types and fixtures. WP-002 confirms actual paths. Each proposal records operation/port ID, context, units, schemas/errors, examples, producer/consumer ownership, version compatibility and migration/retirement conditions. Fixture quantities require separate derivations; TypeScript does not duplicate authoritative arithmetic.

1. Publish a small contract/fixture proposal identifying affected consumers. Validate under §3 and merge before dependent consumer implementation.
2. Merge canonical definitions, generated artifacts and fixtures together. Pin their commit/version in dependent children; regenerate types from Python.
3. Prefer additive changes with explicit missing/unknown behavior. Test current producer/consumer and supported previous combinations. Preserve decimal-string and status semantics.
4. Breaking changes declare the relevant protocol/schema/model identity, migration or rejection behavior, and merge order. Retain compatible adapters until consumers migrate. If coexistence is unsafe, test a coordinated producer/consumer candidate with explicit old-client rejection.
5. Retire old fixtures/adapters through a separate validated change. Preserve required historical inspection and migration behavior for saved models/data.

The following steward/backup table applies to multi-contributor staffing. **In solo mode A is every steward and the backup is unavailable.** On transitions, rebind stewardship and backup to actual available people; record required expertise or access gaps rather than assigning absent contributors.

| Shared area / proposed paths | Steward / backup | Concurrent editing rule |
|---|---|---|
| Canonical contracts, units, entity IDs, core reducers | A / B | One active boundary change per operation/state partition; consumer approval required |
| npm manifests/lock, Forge/Vite, main/preload, desktop CI | B / A | Dependency/config changes in dedicated PR; rebase and regenerate lock rather than merging lock text blindly |
| Python manifest/uv lock, engine core, migrations | A / B | Distinct migration IDs, check current main before allocation; never share a live dev DB; backups/migration fixtures accompany changes |
| Domain registry and shared account/port catalog | A / B | Domain authors own their module; registry additions use coordinated small changes, not rewrites in every domain branch |
| Content manifests, source/coverage index | B / A; C / A when active | Namespaced per-domain files, deterministic index build; manifest edits coordinated with content steward |
| Domain-local code/content/tests | Assigned domain owner / assigned reviewer | One active child per module path; cross-domain work goes through ports, not direct writes |
| Release/evidence ledger and workflows | B / A; C / B for evidence when active | Evidence names exact candidate SHA; CI workflow implementation remains B-owned |

Stewards coordinate semantic changes and invariants. Backups may author changes under §3. Path ownership controls overlapping edits; contract and integration tests verify semantic compatibility. Implementation retains the specified monorepo and process boundaries.

Use GitHub issues/PRs as the durable delivery ledger during implementation. Record:

- **WIP:** one implementation child per active person, plus one validation/review item; at least one ready fallback when dependencies permit. Solo mode reserves validation capacity before taking the next implementation child.
- **Handoff/resume:** record base/candidate SHA, branch/PR, changed paths/contracts, completed behavior, checks/evidence, next action, blocker and next working window. Solo work uses the same record for resumption and future transfer.
- **Review/validation:** peers acknowledge requests in their next scheduled working period and aim to decide within that period for small children. Leave/availability updates the due window. Solo acceptance follows SV; record deferred independent review separately.
- **Decisions:** local implementation choices stay with the owner. Boundary, model, compatibility or scope changes require recorded alternatives, impacts and a decision under §3. Refer unresolved product intent to the product decision owner while independent work continues.
- **Integration:** run the production cross-boundary slice at least weekly and before gates, on a named candidate. Coordination belongs to A with one contributor, B with two and C for designated evidence with three. Rotate execution where multiple environments are available; solo uses a fresh isolated checkout for reproduction.
- **Failure:** stop affected merges, assign fix/revert ownership and keep main runnable. Preserve unaffected ready work and evidence. Staffing loss does not waive a failing engine, contract or target check.

```text
Child / owner / current roster and slot mapping / effective date:
Validation mode / peer if available / deferred review item:
Base main SHA / branch or PR / candidate SHA:
Changed paths / contract and fixture versions:
Completed behavior / unavailable behavior / checks and evidence:
Next action / blocker / requested decision / residual risk:
Next owner and reviewer working windows (time zones explicit):
```

## 7. Staffing transitions

Trigger this procedure when available implementation/review capacity changes, including planned leave, abrupt loss and a returning contributor. A joining person is allocated work only after setup, contract review and a small validated onboarding change. Until then the lower-capacity mode remains active. Rebind slots to the remaining qualified people; a transition never requires a particular original contributor to remain present.

At the effective change, record the roster and one owner for every open child/parent, pending review, contract, migration, shared path and gate. Preserve accessible WIP branches/checkpoints and their base SHA. For a planned transfer, finish a safe child or checkpoint before reassignment. For abrupt loss, transfer from the last confirmed state immediately, mark inaccessible artifacts and recover/reimplement only affected work. Review evidence for the unchanged candidate remains valid; changed behavior requires affected rechecks. Reconfigure repository review requirements through an authorized maintainer, adjust WIP/ready queues, and reforecast actual remaining effort including onboarding and deferred review.

| Transition | Ownership and sequencing | Validation and forecast action |
|---|---|---|
| 1 → 2 | Onboard the joiner; map available people to A/B; transfer B's queued parents and consumer/domain children at recorded checkpoints | Activate nonauthor review; assign deferred SV review by risk before optional new work; budget onboarding/review effort |
| 1 → 3 | Onboard both joiners; map A/B/C directly; transfer each matrix assignment from A without duplicate active path claims | Activate peers and C's evidence queue; allocate deferred reviews across competent nonauthors; forecast all three availability intervals |
| 2 → 1 | Map the remaining person to A; transfer every departed-owner/reviewer child and stewardship record; serialize engine/desktop/domain queues | Apply SV to new/unreviewed changes; preserve valid prior approvals, record new deferred reviews and update merge settings; reforecast solo capacity |
| 2 → 3 | Onboard the joiner; map A/B/C; transfer C's listed parents/domains and DOM-12 to B at checkpoints | Reassign peers, including pending reviews; budget C's onboarding, evidence and review queues |
| 3 → 1 | Map the remaining person to A regardless of former slot; consolidate all owners, stewards and review queues; preserve accessible WIP | Apply SV without waiting for departed reviewers; retain valid prior evidence, record access/expertise gaps and reforecast one-person throughput |
| 3 → 2 | Map either surviving pair to A/B by skills/access; transfer all matrix differences, including C's work and any rebound A/B scope | Assign competent nonauthor peers, replace absent reviewers and reforecast remaining implementation/review capacity |

Unchanged contributor count with a replacement uses the same onboarding, slot rebinding, checkpoint and peer reassignment rules. A temporary absence can later reverse through the corresponding upward transition. Completed acceptance evidence is not restarted solely because staffing changed. If no active person can complete a required scientific or platform check, record the external prerequisite and continue independent work.

## 8. CI, environments and forecasting

All staffing modes require frozen installs, generated-contract compatibility, content integrity/licensing, engine invariants with separate derivations, desktop/provider mocks and actual Electron/child/SQLite checks for changed boundaries. Run paired-domain and integrated-slice checks when affected. Native targets require execution evidence at probe/release gates. Default tests use synthetic data and no paid providers. Setup records exact runtime/OS/architecture/pack versions and isolated temporary user data; secrets stay in approved local/CI configuration.

Before W2, verify clean setup on every active contributor's environment; solo mode additionally verifies a fresh checkout independent of the working copy. Joining contributors reproduce the current candidate before transfer. Before expanding domains, verify production producer/consumer integration. All four native target combinations remain mandatory independent of contributor count.

Apply the parent roadmap's per-mode capacity budget. Child estimates separate implementation, author corrections, SV or peer review, integration, owner/reviewer availability, external waiting and uncertainty. Sum effort once. Maintain forecast scenarios for all three counts, and resource-load known roster changes by effective interval. Reforecast at every roster change, after M1/M2 and at least fortnightly. Track ready work, review wait/debt, blocked contracts, integration failures, evidence freshness and model/research scope. Measure throughput by accepted integrated deliverables.

Workflow acceptance requires applicable COL-01–COL-08 evidence in the [verification matrix](verification_matrix.md). Scenario plans cover all three counts and all six directed transitions. Record actual executions, simulations and inapplicable cases distinctly; a planned simulation does not certify an unexecuted contributor setup or independent review.
