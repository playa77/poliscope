# Poliscope — Work-Package Delivery Plan

Revision 0.4 · 2026-10-16 · One to three development agents under human control. Implementation is **not started**. Parent: [roadmap](../implementation_roadmap.md); scope: [shared packages](work_packages.md), [domain packages](domain_work_packages.md), [verification](verification_matrix.md).

## 1. Allocation unit and responsibilities

The executable work package is the unit of assignment. Before it starts, allocate an available development agent and record its controlling person, any collaborators, division of work, write scope, dependencies, deliverables, interfaces, validation route and acceptance criteria. Keep this execution plan stable until the package completes.

Human controllers maintain priorities, agent availability and the authoritative package ledger. They select ready work at package boundaries and retain required human authorization decisions. Development agents implement, test, document and review their assigned packages. Required capabilities belong to package definitions; agent identities are recorded only when packages are allocated. An agent may implement an engine package and later a desktop, content or review package if qualified.

One to three agents may execute compatible packages concurrently. Availability changes affect the allocation of unstarted packages. They do not change the owner, collaborators, division of work or validation route of another package already in progress. Agents enter or leave after completing their own package; other active packages continue. No common milestone, sprint or whole-team completion barrier is required for the next allocation.

Large inventory packages may be decomposed **before execution** into bounded executable packages. Each child has its own ID, inputs, outputs and acceptance criteria. The parent becomes an aggregate scope/evidence record; children inherit its requirements. Each child is allocated once at its start and retains that allocation through completion. Existing assignments are not changed by relabeling in-progress work as smaller packages.

## 2. Package lifecycle and boundary allocation

| State / event | Required action | Assignment rule |
|---|---|---|
| Planned | Define capability, scope, dependency and acceptance requirements; decompose if needed | No project-wide agent reservation |
| Ready | Verify actual prerequisites or validated contract fixtures, write-scope compatibility and evidence requirements | Eligible for allocation to any available qualified agent |
| Start | Record owner agent/controller, collaborators, division of work, validation route, base SHA and contract versions | Freeze the package execution plan |
| In progress | Implement, checkpoint and submit reviewable changes against that plan | Availability changes do not reassign the package |
| Review / integration | Execute the recorded review, checks and integration; correct defects within the package | Retain assignment and acceptance requirements |
| Complete | Record accepted candidate/evidence, remaining limitations and integration result; release its reserved capacity/write scope | This is a boundary for choosing the next ready package |
| Next allocation | Reassess currently available agents, ready work, review backlog, controller access and integration priority | Assign only unstarted packages; other active packages remain unchanged |

WP-001 establishes templates, readiness and allocation rules. The same start/completion procedure applies to every later package; WP-001 does not assign the project workforce in advance. Record availability updates when known and use them for the next package starts. Allocate only work the agent/controller can commit to completing under the agreed package plan.

Selection order is: required corrective or review work, integration-path blockers, ready feature/content packages, then independent preparation. An available agent takes one executable package at a time. Its implementation, inspection, validation and integration are included in the package effort. Reserve nonoverlapping write scopes for simultaneous packages. Shared contract, migration, registry and lockfile changes require coordinated scope declarations before either package starts.

### 2.1 Capacity at the next start

| Available agents | New package allocation | Active work |
|---|---|---|
| 1 | Select one ready package; execute its planned work sequentially | Preserve all active package plans |
| 2 | Select up to two compatible ready packages, including implementation/review work as required | Preserve all active package plans |
| 3 | Select up to three compatible ready packages, balancing integration and validation capacity | Preserve all active package plans |

Concurrency includes existing active packages. A newly available agent takes only an unstarted ready package with unreserved write scope. The roadmap has no permanent engine, desktop or content agent. Capacity affects which ready packages start next and their start dates; scope and acceptance evidence remain constant.

For example, an engine package may remain in progress while a UI package completes. The UI agent can finish its allocation and leave; another available agent can start the next ready content or review package. The engine package's owner and plan remain unchanged throughout.

## 3. Package contract and durable context

Each executable package records:

```text
Package ID / parent scope ID / status:
Objective / required capabilities / deliverables:
Owner agent identity / human controller:
Collaborators / agreed division of work:
Declared write scope / interfaces / exclusions:
Prerequisites / base main SHA / contract-model-fixture versions:
Validation route / review package or assigned reviewer / human approvals if required:
Acceptance criteria / commands / independent expected results:
Checkpoint commit / branch or PR / completed work / next action / blockers:
Completion candidate / evidence links / outcome / limitations:
```

Use an isolated clone/worktree and private application data/environment per executing agent. At package start, fetch/pull the current source baseline, inspect applicable instructions, install or rebuild from committed configuration where available, and verify relevant contracts/checks. Preserve in-flight edits when refreshing a package branch. Changes to upstream dependencies are reconciled explicitly without altering ownership or silently accepting changed contracts.

Keep source, decisions, derived fixtures, commands and evidence in Git/PR/package records. A subsequent package must be executable by a different agent using those records. Agent session restarts reload the same package assignment and checkpoint; session identity changes do not create a new collaborator or count as independent review. Controller identities and package authorship history remain traceable across sessions.

## 4. Contracts and package decomposition

Define canonical Pydantic boundaries in proposed `engine/contracts/`; generate JSON Schema, TypeScript/tool types and versioned fixtures under `contracts/`. WP-002 confirms actual paths. A contract package defines operation/port identity, context, units, schema/errors, examples, producer/consumer requirements, compatibility and migration. Validate and merge it before dependent consumer packages start.

Producer and consumer packages have separate scopes and may be implemented by the same agent sequentially or different agents concurrently. Their start records identify the same approved contract version. Integrate production operations as they become available; development fixtures cannot satisfy application acceptance. Breaking changes require a separately planned contract change, affected-consumer work and explicit compatibility/rejection/migration behavior. Existing active packages retain their assignment and reconcile declared dependency changes before acceptance.

| Planning package / executable split | Capability / scope | Boundary result |
|---|---|---|
| WP-001 allocation process | Delivery coordination and requirements | Package template, ready queue, allocation and completion procedure |
| WP-002 scaffold; WP-003 checks | Python/desktop setup and CI | Frozen dependency roots, documented setup, isolated checks |
| WP-005 minimum wire contract | Pydantic/schema/TypeScript | Handshake/read/result/error and decimal/unknown/version fixtures |
| WP-010 engine producer / desktop consumer | Separate engine stdio and main-process scopes | Production handshake, bounded parser/correlation and failure behavior |
| WP-011 secure shell | Electron main/preload/renderer | Named API and trust boundary |
| WP-018 preview/apply contract and services | Engine history/transactions | Context, candidate identity, stale/idempotency behavior |
| WP-020/021 creation/interview consumers | Desktop interaction | Fixture-backed preparation followed by production-engine integration |
| WP-023 comparison service / view | Separate Python comparison and desktop scopes | Compatible numerical differences and preserved branch context |
| WP-027 conformance contract / harness | Shared domain interfaces | Canonical IDs/accounts, ownership checks and positive/negative fixtures |
| WP-034 transition service / WP-037 timeline | Separate engine boundary and desktop scopes | Atomic boundary, progress/cancel and reproducible presentation |
| WP-039 archive format / dialogs | Separate validation/storage and file/UI scopes | Data-only format, privacy controls and real round trip |
| WP-046 context service / tool adapter | Separate Python fact assembly and main-owned tools | Context-bound read/proposal authority |
| WP-048 cost ledger / provider events | Separate Decimal reconciliation and networking scopes | No double charge, explicit estimate/actual/unknown states |

These are capability requirements and executable splits, not named-agent allocations. Remaining packages use the same pre-execution decomposition rule. Each resulting package retains its assignment through acceptance. Parent scope, dependencies and integration requirements remain unchanged.

## 5. Domains and parallel compatibility

The [domain register](domain_work_packages.md) defines all twelve domains and their counterpart checks. Publish each executable domain package's owned state, ports, mechanism card, scope and expected fixtures before implementation. WP-027's validated contract can support development before the complete harness is accepted; static acceptance requires the production harness, content evidence and actual counterparts.

Select domain packages from the ready queue according to available capabilities and write scopes. Provisioning, governance, infrastructure and other domains are not permanently attached to an agent or a fixed pair. With one agent, implement counterpart packages sequentially. With two or three, compatible packages can proceed concurrently; both use the same canonical account/entity and contract definitions. Introduce institutional as well as material behavior early enough to validate the shared architecture.

Integrate affected counterparts whenever a package completes and rerun affected existing fixtures. A package may have a validated local result before its parent all-domain gate passes; record the distinction. WP-032 and WP-055 remain the all-domain integration/release gates. Decompose static and transition work before execution where needed so later transition packages can be allocated independently without changing an active static package's owner.

## 6. Validation and human authority

Choose the validation route before package start. More available agents do not automatically change an active package's validation route; fewer available agents do not waive its required review. Human-controller permissions and repository rules remain stable across ordinary agent-count changes.

- **Agent review:** assign a nonauthor development agent, or a separately scoped review package, to inspect the declared candidate, requirements, independently derived fixtures, risks and checks. Record author/reviewer identities and candidate SHA. A fresh session continuing the author's assignment is author validation. Distinct agent review provides technical peer evidence, not independent human signoff or empirical certification.
- **Solo validation (SV):** the owner performs a separate inspection pass, derives expectations independently of the implementation and runs required candidate/integration checks. Record `solo-validated; agent review deferred`, candidate SHA, outcomes, residual risk and the follow-up review item. A later agent can take a review package after completion. Required external evidence and approvals remain blocking for the affected claim/action.
- **Human authority:** controllers allocate packages and exercise actions allowed by their actual repository/service permissions. Required human approvals, publication authorization and model/source permissions are recorded separately from agent technical review. Multiple agents using one GitHub account do not create multiple GitHub reviewer identities. Follow actual branch protection; record a pending required approval rather than fabricating nonauthor account approval or changing protection because the agent count changed.

Every route requires independently derived numerical/procedural expectations, meaningful positive/failure checks, current candidate identities, production integration and documented limitations. Model/scientific claims, offline behavior, native execution, privacy, replay and provider verification remain governed by the source specifications. Review findings return to the same package owner for correction. Review packages are allocated under the same stable execution rules.

## 7. Agent-count changes at package boundaries

Availability can be updated at any time for planning. Apply additions, departures and changed allocation only when the affected agent completes its current package or before an unstarted package begins. Other packages remain in progress under their original plans. Update the ready queue and forecast; preserve all accepted evidence and pending package requirements. A new agent verifies its environment and reads the relevant records before starting its first assigned package. A departing agent publishes completion/handoff evidence for its final package.

| Capacity change | Next package allocation | Invariant for other active packages |
|---|---|---|
| 1 → 2 | Allocate an additional compatible ready package to the joining agent | Existing owner, collaborators, scope and validation route unchanged |
| 1 → 3 | Allocate up to two additional compatible ready packages to the joining agents | Existing owner, collaborators, scope and validation route unchanged |
| 2 → 1 | After one agent completes its final package, the remaining agent selects subsequent ready work sequentially | Existing owner, collaborators, scope and validation route unchanged |
| 2 → 3 | Allocate one additional compatible ready package to the joining agent | Existing owner, collaborators, scope and validation route unchanged |
| 3 → 1 | Departing agents complete their final packages; the remaining agent selects subsequent ready work sequentially | Existing owner, collaborators, scope and validation route unchanged |
| 3 → 2 | After one agent completes its final package, the remaining agents select compatible ready work | Existing owner, collaborators, scope and validation route unchanged |

Replacing an agent at the same count follows the same completion/start procedure. Update only the next allocation. Package completion and new allocation can occur while another package is still running.

An unexpected interruption marks that package blocked, preserves its assignment and records the last confirmed checkpoint. Resume the same assignment from durable context when possible. If recovery requires another owner, the controlling person explicitly closes the interrupted execution and defines a separately scoped recovery/successor package with its own start contract and links to preserved work. This is an exception record, not routine reassignment inside an active package.

## 8. CI, integration and forecast updates

All packages use short-lived PR branches, required checks on a candidate containing current main and the package's recorded validation evidence. Use the repository's merge queue where available, otherwise update/recheck before merge. Changed behavior invalidates stale evidence. Agent review artifacts supplement the repository's actual account-level approval requirements.

Required checks cover frozen setup, generated-contract compatibility, content integrity, engine invariants, independently derived fixtures, desktop/provider mocks and actual Electron/child/SQLite behavior. Domain/contract changes run affected counterpart and integrated-slice checks. Native and live-provider evidence remain explicit; ordinary checks use synthetic data and no paid calls. The exact checks follow each package's scope and source requirements.

At each completion/start boundary, controllers update available agents, ready work, reserved scopes, review backlog, integration blockers, required access and the remaining forecast. Measure agent execution/setup cost, context restoration, validation/correction cycles, integration and human waiting separately. Agent-count changes affect future start dates; they do not rewrite completed effort or active package contracts. WP-001 creates the process and templates; every package boundary executes them.

Applicable COL-01–COL-08 scenarios in the [verification matrix](verification_matrix.md) verify the allocation model, stable active execution, review provenance and handoff. All operational workflow evidence is **unrun** until implementation exercises it.
