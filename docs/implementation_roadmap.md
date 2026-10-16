# Poliscope — Implementation Roadmap

Revision 0.1 · 2026-10-16 · Planning baseline; implementation has not started.

## 1. Purpose, authority, and document map

This roadmap translates the [global game design](design_doc.md) and [technical specification](tech_spec.md), both revision 0.2 dated 2026-10-13, into an executable delivery plan. Those documents define product and architecture requirements; this roadmap defines implementation order, work ownership, deliverables, dependencies, and evidence of completion. Where this plan proposes fixture contents, effort ranges, repository paths, or review procedures, those are planning decisions rather than additional claims made by the specifications.

The inspected repository baseline is `c837d25da60fd3ed5710e5cedddc27180f84187c`: README, license, ignore rules, and the two specifications. There are no application sources, dependency manifests, lockfiles, runnable development scripts, or tests. README development commands describe the intended workflow, not a working implementation. All work packages below begin **not started**. No milestone, native platform, scientific model, or provider capability is certified by this document.

| Document | Use |
|---|---|
| This roadmap | Scope, milestones, execution sequence, staffing, decisions, and release gates |
| [Shared work packages](roadmap/work_packages.md) | WP-001–WP-056: platform, engine, storage, UI, content infrastructure, timeline, AI, portability, and delivery |
| [Domain work packages](roadmap/domain_work_packages.md) | DOM-01–DOM-12: concrete work and validation for every domain |
| [Verification and traceability](roadmap/verification_matrix.md) | Coverage of both specifications, integrated scenarios, test ownership, and release evidence |

Read the roadmap first, then the relevant package and its prerequisites. A package ID identifies scope; its numerical position alone does not authorize starting it. Dependency fields are authoritative. Source references use **D §n** for the design document and **T §n** for the technical specification.

## 2. Product scope and completion contract

The delivery target is a local, single-player educational desktop sandbox in which a player can create a civilization, inspect any of twelve domains, preview and apply choices, understand shared consequences, experiment through time, branch and compare, and export their work. The complete target includes optional BYOK assistance with first-class OpenRouter support. An offline milestone is an intermediate delivery, not permission to omit AI from the complete product.

The following constraints apply to every package and review:

1. **Player agency:** no assigned goals, default civic policies, hidden objective function, campaign progression, automatic redesign, or winner ranking. An explicitly selected reference civilization may supply labeled historical choices; an ordinary new sandbox may not.
2. **One world:** shared people, assets, resources, time, rights, obligations, and institutions have canonical identities. Domains contribute definitions and mechanisms without maintaining independent copies or spending shared capacity twice.
3. **Python authority:** Python owns arithmetic, allocation, transitions, numeric comparisons, goal observations, cost aggregation, and SQLite writes. TypeScript handles presentation, process boundaries, and provider protocols.
4. **Honest claims:** distinguish numerical/procedural/qualitative/partial/unsupported modeling, source/evidence status, and authored/imported/player/AI origin. Unknown is not zero; partial coverage is not whole-system sufficiency.
5. **Explicit assumptions:** no invented universal legitimacy, happiness, fairness, or cohesion meters. Every behavioral effect needs a declared population, rule, time basis, evidence, uncertainty, and validity limits.
6. **Reversible inquiry:** immutable committed states, pure previews, stale apply rejection, idempotent recovery, preserved alternate futures, and explicit model migration. Counterfactual redesign and a future effective policy change remain separate.
7. **Offline ownership:** authored interviews, simulation, history, exploration, and reports work without accounts or provider access. No background civilization upload. Keys are excluded from engine state, logs, saves, prompts, and exports.
8. **Desktop boundaries:** Electron main owns lifecycle, filesystem dialogs, key protection, and provider networking; sandboxed renderer uses a named preload API. One Python child communicates through bounded versioned stdio messages, not a web backend.
9. **Accessible inquiry:** core actions work by keyboard, visual status has text, graphs/matrices have list or table equivalents, and results identify civilization, scope, branch, revision/time, and model.
10. **Complete architecture, bounded models:** all twelve domains and the source map's branches must be represented. Release scope names which mechanisms are implemented and which remain explicit gaps. Completing one representative mechanism per domain is a minimum integration condition, not evidence that an entire society is numerically modeled.

Explicit exclusions from this roadmap are multiplayer, competing playable empires, a persistent cloud service, mandatory 3D terrain, individual-agent simulation at civilization scale, arbitrary imported/generated code execution, and paid live-provider tests in ordinary CI. The named-target capacity-bound calculation is included as an optional model capability; it cannot become a hidden social optimizer.

## 3. Delivery strategy and milestone gates

Build the stable contracts before expanding content. Prove the offline choice-to-consequence loop with a deliberately small, labeled test fixture. Expand through a shared domain framework; do not implement twelve separate simulators. Introduce time after static state, accounts, and history are reliable. Start provider and packaging work early enough to expose platform constraints, but accept them only with integrated evidence.

The planning fixture for the early vertical slice is a small resource/service arrangement with two locations, overlapping membership/jurisdiction, finite shared labor and stock, an institution, and an unresolved alternative. It is synthetic test data with documented arithmetic, not a canonical civic policy or required player starting scenario. The education relationship path in D §5.7 is later used as an integration test across all domains, not as a mandated gameplay entry point.

| Milestone | Scope and work packages | Entry | Exit evidence |
|---|---|---|---|
| **M0 — Implementation baseline** | WP-001 | Specifications available | Requirement ledger, ownership, release coverage policy, decisions and risks recorded; source contradictions identified |
| **M1 — Trustworthy desktop/runtime foundation** | WP-002–WP-011 | M0 | Frozen install and generated contracts work; secure desktop launches Python, handshakes, opens local storage, recovers from child failure; native packaging feasibility recorded |
| **M2 — Offline design vertical slice** | WP-012–WP-024 | M1; package-level prerequisites satisfied | Create → inspect → preview → apply → trace → undo/fork → compare → close/reopen works offline with independently checked shared accounts; stale/duplicate requests are safe |
| **M3 — Twelve-domain design workspace** | WP-025–WP-032 and DOM-01–DOM-12 | M2 for integrated acceptance; pack/domain preparation can start earlier | All twelve modules and source branches registered; each has reviewed executable behavior plus honest gaps; atlas, matrices, world, evidence and distribution views navigate the same world; all-domain static integration passes |
| **M4 — Time, uncertainty, and experiments** | WP-033–WP-038; transition portions of all domain packages | M2 for generic time framework; M3 for integrated acceptance | Schedule/advance/cancel/replay/fork/compare works; shared transition reduction, multirate boundaries, lifecycle, hazards, deterministic streams and uncertainty semantics verified |
| **M5 — Portable local ownership** | WP-039–WP-041 | M2 for design export; M4 for complete experiment archive | Full-state round trips, safe rejection, privacy defaults, reports/CSV, backup/migration, and historical read-only behavior pass with no silent recomputation |
| **M6 — Complete optional AI/BYOK** | WP-042–WP-050 | M1 for provider infrastructure; M2 for proposal flow; M3/M4/M5 for full integrated acceptance | Full provider capability matrix exercised, grounded tools cannot commit, context consent and costs are visible, mock failures are safe, bounded authorized live checks have explicit outcomes |
| **M7 — Release candidate and native distribution** | WP-051–WP-056 | Earlier milestone evidence integrated | Performance and accessibility budgets met; recovery and security checks pass; Windows x64, macOS arm64/x64 and Linux x64 packages work without system Python; release evidence and limitations are published with artifacts |

Milestone exits are conjunctive: passing a UI demo does not waive arithmetic or storage evidence. M7 requires M3, M4, M5, and M6, including all domain packages. A milestone remains blocked if a required behavior is untested or an unexplained failure remains. A scoped preview may be released earlier only with its omissions explicit; it must not be labeled complete architecture delivery.

### 3.1 Dependency structure and work that can overlap

```mermaid
flowchart TD
    M0["M0: baseline and decisions"] --> M1["M1: contracts and desktop/runtime"]
    M1 --> M2["M2: offline design loop"]
    M2 --> M3["M3: twelve-domain design integration"]
    M2 --> TIME["Time framework implementation"]
    M3 --> M4["M4: integrated experiments"]
    TIME --> M4
    M2 --> PORT["Archive and report implementation"]
    M4 --> M5["M5: complete portable ownership"]
    PORT --> M5
    M1 --> AI["Provider infrastructure and mocks"]
    M3 --> M6["M6: full optional BYOK integration"]
    M4 --> M6
    M5 --> M6
    AI --> M6
    M1 --> PKG["Early native packaging probes"]
    M3 --> M7["M7: release candidate"]
    M4 --> M7
    M5 --> M7
    M6 --> M7
    PKG --> M7
```

The likely critical path is contracts → canonical quantities/world → shared accounting/evaluation → transactional preview/apply → offline integrated loop → domain coupling → multirate/replay → complete portable state → integrated release evidence. This is a planning hypothesis; update it from actual package durations and platform/provider blockers. Provider compatibility, content licensing, and native signing can become independent critical paths.

Parallel work is safe only after its input contracts have fixtures and versioned schemas. Content inventory can proceed alongside engine foundations. Domain implementations can proceed independently once WP-027's harness exists, but domain acceptance waits for counterpart integration. Provider fixtures and catalog work can overlap M3/M4. Packaging probes begin in M1; final packages wait for the actual application. Performance, accessibility, privacy, and numerical review are continuous concerns, with final gates in M7.

## 4. Work package execution rules

Each package defines an accountable role, dependency IDs, size class, outputs/actions, and testable acceptance criteria. Domain packages have separate **start prerequisites** and **integration acceptance dependencies** to avoid circular scheduling. References to another domain's interface do not authorize writing its state directly.

Use the following lifecycle in the issue tracker when implementation starts: `not started` → `ready` → `in progress` → `review` → `verified`, with `blocked` carrying a named prerequisite and owner. Do not infer completion from merged code alone. Link each implementation issue/PR to its package, source sections, affected contract versions, tests, evidence, and any remaining model gaps. This roadmap creates no external issues or assignments.

**Ready checklist:** prerequisites verified or an explicit reviewed stub contract exists; inputs/outputs and owner agreed; evidence/fixture available; data ownership settled; package acceptance can fail for the relevant broken behavior. A stub permits development, not milestone acceptance.

**Common definition of done:**

- Deliverables implemented in the agreed repository area; exact dependencies/locks and generated artifacts updated where necessary; no secrets or personal data committed.
- Existing meaningful tests plus package-specific positive, incomplete/conflict, and failure cases pass; test counts and skips are recorded. Expected failures remain distinct from passes.
- Boundary and schema changes regenerate contracts and document compatibility/migration. Numeric expectations have independent derivations; UI snapshots alone do not establish correctness.
- Traceability identifies source/assumption/model status; core functionality remains offline; accessibility and privilege boundaries are preserved.
- Documentation covers usage, limitations, and recovery; evidence links are attached; independent reviewer accepts the behavior and scope. An author does not self-certify empirical validity.

**Package split rule:** split any L package or estimate above ten focused engineer-days into child issues before implementation. Preserve parent ID, dependency edges, acceptance criteria, and integration responsibility. Common reusable work must be implemented once and referenced by domains.

## 5. Repository and command plan

WP-002 establishes the concrete layout and script wiring. The following are responsibility boundaries, not claims that files already exist:

```text
desktop/main/         lifecycle, process bridge, files, keys, providers
desktop/preload/      named and validated renderer API
desktop/renderer/     synchronized React workspaces and accessible components
engine/world/         identities, scopes, population, institutions, shared accounts
engine/domains/       twelve registered modules
engine/simulation/    graph evaluation, allocation, solvers, transitions, randomness
engine/storage/       SQLite, revisions, experiments, backup and migration
engine/explanation/   measurements, findings, traces and context assembly
content/              manifests, catalogs, evidence, reviewed mechanisms and fixtures
contracts/            generated schemas, TypeScript bindings and compatibility fixtures
tests/                cross-boundary, numerical, desktop, provider and native tests
docs/                 architecture, roadmap, decisions, model reviews and user guidance
```

Use Node 24 LTS, Python 3.12, uv, npm's committed lockfile, Pydantic 2, Decimal, Electron/Forge/Vite, React/TypeScript, TanStack Query, Recharts, SQLite, and PyInstaller. Select mutually compatible supported stable dependency releases in WP-002 and pin them; this roadmap does not guess exact future release numbers.

WP-002/WP-003 must make the README workflow executable from the repository root:

```sh
npm ci
uv sync --frozen --python 3.12
npm run dev
npm run content:validate
npm run contracts:check
npm run typecheck
uv run --frozen pytest
npm test
npm run test:desktop
npm run package
```

The development command launches Electron and its managed Python engine. It must not introduce an application HTTP backend. Development tooling may use Vite's own supported development transport; runtime model IPC remains stdio. Default test commands use synthetic data and provider mocks, never paid API calls. Native packaging runs on each target OS/architecture. Any auxiliary benchmark, live-provider, or signing command must be documented when introduced and have a distinct explicit invocation.

## 6. Staffing, estimates, and forecasting

Roles below are responsibilities, not promises that this team exists. One engineer may cover multiple roles; shared ownership still needs a named integration owner.

| Role | Primary responsibility | Review counterpart |
|---|---|---|
| Technical lead (TL) | Contracts, architecture decisions, cross-stream integration | Engine and desktop leads |
| Engine engineer (ENG) | World, arithmetic, solvers, transitions, measurements | Model/evidence reviewer |
| Desktop engineer (DESK) | Electron, preload, UI, provider networking | QA/security and engine reviewer |
| Content/model engineer (MODEL) | Source extraction, domain definitions, model evidence and fixtures | Domain reviewer plus ENG |
| Quality/release engineer (QA) | Cross-boundary tests, accessibility, native builds, recovery | Feature owner and TL |
| Technical project manager (TPM) | Dependencies, gates, forecast, risk and scope accounting | Product/design owner |
| Product/design owner (PRODUCT) | Interview quality, player agency, inquiry usability, release content scope | TPM and model reviewer |

For initial forecasting, package size classes are **S = 1–3**, **M = 4–7**, **L = 8–12 focused engineer-days**. These are explicitly provisional planning envelopes for implementation plus local tests/review corrections, not commitments or empirical estimates. Every domain package is L because evidence, interfaces, content, and fixtures must be integrated. Independent domain research, scientific review, signing procurement, provider credits/access, and platform availability are separate lead-time risks; unknown research cannot be disguised as ordinary coding effort.

WP-001 must turn the package inventory into a resource-loaded forecast after owners inspect representative contracts and model sources. Sum package ranges for effort; do not divide by headcount to claim a delivery date. Schedule using dependency order, actual staffing, review capacity, integration time, platform lead times, and a separately visible uncertainty allowance. Reforecast after M1 and M2 using observed completion rates. No calendar completion date is supportable from this documentation-only baseline.

The following roll-up makes the initial sizing explicit. It is the arithmetic sum of the provisional package classes, **not a committed estimate**. Domain effort is counted once across M3/M4; it is not included again in the shared-framework rows. Package ranges include local tests/review corrections, while independent research, external waiting time and portfolio contingency remain outside these totals.

| Work stream | Packages / size mix | Provisional focused engineer-days |
|---|---|---|
| M0 baseline | WP-001; 1 M | 4–7 |
| M1 foundation | WP-002–WP-011; 9 M + 1 L | 44–75 |
| M2 offline loop | WP-012–WP-024; 5 M + 8 L | 84–131 |
| M3 shared content/exploration | WP-025–WP-032; 4 M + 4 L | 48–76 |
| All-domain implementation across M3/M4 | DOM-01–DOM-12; 12 L | 96–144 |
| M4 shared time/uncertainty | WP-033–WP-038; 3 M + 3 L | 36–57 |
| M5 portability/recovery | WP-039–WP-041; 1 M + 2 L | 20–31 |
| M6 optional assistance/provider completeness | WP-042–WP-050; 2 M + 7 L | 64–98 |
| M7 hardening/release | WP-051–WP-056; 1 M + 5 L | 44–67 |
| **Total initial package envelope** | **68 packages; 26 M + 42 L** | **440–686** |

These numbers are useful for exposing the scope of the complete architecture and comparing later estimates. They do not assume a domain's scientific research will fit inside a twelve-day coding package. If evidence or algorithms are not available, create explicit research children, update the forecast, and keep the required release behavior visible.

Recommended starting allocation, if four contributors are available: one engine lead, one desktop lead, one content/model engineer, and one quality/release engineer, with TL/TPM responsibilities explicitly allocated. With one contributor, follow dependencies serially and retain independent review for numerical/security claims. Avoid starting all twelve domains at once before the common harness is stable.

### 6.1 Initial performance fixtures and budgets

These are proposed engineering acceptance targets to make DEC-06 actionable, not requirements asserted by the source documents or measured capabilities. WP-001 confirms the reference machine and records any justified changes; WP-019 gathers the first measurements. Rebaseline transparently if the selected models require different scales. Never meet a latency target by skipping required calculation/transition boundaries or concealing solver failure.

Use a native reference desktop with four modern CPU cores, 16 GiB RAM and SSD storage; record exact hardware/OS and power settings. Run cold and warm caches separately, with at least 30 independent preview/query samples and labeled workload/model identities. Network latency and upstream generation time are excluded from local UI/engine targets and reported separately.

| Fixture or operation | Initial workload / target |
|---|---|
| Small classroom world | 20 scopes, 40 cohorts, 100 assets, 300 decision instances, 2,000 active typed edges; all twelve domains and explicit overlap |
| Larger exploratory world | 200 scopes, 400 cohorts, 1,000 assets, 3,000 decision instances, 30,000 active typed edges; sparse graph with declared representative coupled components |
| Long-history/trace fixture | 1,000 committed revisions, 20 named branches, 100,000 pageable trace nodes; do not materialize all records in one renderer response |
| Local static preview | p95 ≤1 second small / ≤5 seconds larger; cold versus warm figures recorded independently; expensive solver components have separately declared budgets/status |
| Visible atlas/matrix/world page | p95 ≤300 ms warm query for a page of at most 100 records; scale through pagination rather than complete-world rendering |
| Immediate UI feedback | p95 ≤200 ms for selection/navigation/cancel acknowledgement while work is running; slow computation uses visible progress |
| Cancellation and chunk boundary | Confirm cancellation or a bounded in-progress boundary status within 1 second; retain last committed state; separately measure actual boundary completion |
| Dynamic run | Complete a deterministic 365-day small fixture within 30 seconds on the reference machine, executing every required boundary; large/stochastic run throughput reported separately |
| Memory and transport | Combined main/renderer/engine peak ≤2 GiB on the larger fixture; 1 MiB IPC message limit remains mandatory; oversized traces/archives are chunked |

Reference fixture arithmetic, solver structure and transition complexity must be fixed/versioned so these counts cannot hide a trivial workload. Native targets also run correctness/replay checks regardless of performance differences. Changes to accepted budgets require an explicit decision and forecast impact, not an unreported waiver after a failed run.

## 7. Decision register before and during implementation

These decisions need an owner and recorded resolution, not a new round of stack selection. Development may proceed on independent packages while an external prerequisite is unresolved.

| Decision | Owner / due | Default or required outcome | Blocks if unresolved |
|---|---|---|---|
| DEC-01: exact dependency versions and platform support floor | TL / WP-002, WP-004 | Supported compatible stable releases, exact locks; documented OS/version matrix | Reproducible installs and native acceptance |
| DEC-02: canonical serialization, IDs, calendar, RNG and numeric identity | ENG / WP-005, WP-006, WP-033, WP-035 | Decimal 28 digits/half-even as specified; explicit canonical and day-boundary rules; versioned RNG | Digests, replay, cross-platform reproduction |
| DEC-03: source inventory and redistribution license | MODEL / WP-025 | Pin society source at stated revision initially; inspect actual licenses and amendment lineage; permission recorded | Distribution of imported excerpts or packs, not synthetic framework work |
| DEC-04: initial released model inventory | PRODUCT + MODEL / WP-001, refined WP-026 | All branches classified; every domain has substantive reviewed behavior; enumerate numerical/procedural/qualitative/gap coverage | M3 content acceptance and truthful release claims |
| DEC-05: supported solver/allocation procedures | ENG + MODEL / WP-014, WP-015 | Explicit policy-neutral implementation, limits, applicability and independent fixtures | Coupled model activation |
| DEC-06: expected world sizes and performance budgets | TL + QA / WP-001, measured WP-019 | Confirm or explicitly revise §6.1's fixture/hardware/latency/memory targets and freeze benchmark definitions | WP-051 acceptance; no undefined “fast enough” gate |
| DEC-07: native signing/notarization and runner availability | QA / WP-004, WP-054 | Windows x64, macOS arm64/x64, Linux x64 native execution; signing assets kept outside source | Signed/public native release where required |
| DEC-08: provider compatibility and live validation | DESK + QA / WP-043–WP-050 | Current official OpenRouter schemas, explicit capability table, bounded authorized live test plan | Full OpenRouter compatibility claim; offline work remains independent |
| DEC-09: privacy defaults and runtime safeguards | TL + PRODUCT / WP-039, WP-046, WP-048 | Private content excluded by default; explicit sharing; named archive/context/tool/solver limits | Import/sharing/budget acceptance |
| DEC-10: source document cross-link cleanup | TPM / WP-001 | Record that companion links currently use absent `DESIGN.md`/`TECH_SPEC.md`; plan a documentation fix without changing specification semantics | Documentation consistency, not engine development |

## 8. Risk register and response

| Risk | Early detection | Response / accountable package |
|---|---|---|
| Framework becomes a resource-only simulator | Institutional domains have only prose, no procedures or capacity fixtures | Require governance, rights, care, identity and communication behavior; DOM-03/04/05/09/11 and WP-032 |
| Duplicate world state or double allocation | Same asset/population represented with multiple spendable IDs | Canonical ownership registry, overlap fixtures, combined reducers; WP-007/015/027/034 |
| Source prose is mistaken for validated science | Imported range converted to mean, adopted choice treated as fact | Separate origin/evidence/coverage axes, independent numerical review, blocked activation; WP-008/025/026 |
| Graph cycles or policies silently resolved by order | Changing file order changes a result or political winner | SCC classification, solver contracts, explicit conflicts; WP-013/014 |
| History corruption or uncertain commit | Engine dies after database commit before IPC response | Operation IDs, transactional head movement, query/recovery tests; WP-018/041/053 |
| Model/replay drift after changes | Matching UI bars hide changed inputs or random streams | Complete canonical identities, isolated RNG, archived models, native fixtures; WP-016/035/036/054 |
| Long model/research scope obscures progress | Domain labeled complete without evidence inventory | Time-box framework separately; record model gaps and named review work; domain exit contract and DEC-04 |
| Provider API/capabilities drift | Catalog metadata and request controls disagree | Refreshable timestamped catalog, supported control validation, current official schema checks; WP-043/044/050 |
| Paid retries or incorrect cost totals | Uncertain completion retried; estimate and actual both charged | Deliberate generation retry, per-request reconciliation, unknown status; WP-045/048 |
| Desktop/native assumptions fail late | PyInstaller path, signing, credential backend or architecture mismatch | Early native probe plus full target matrix; WP-004/042/054 |
| AI/imported content crosses trust boundary | Tool exposes commit, generated formula executes, key leaks | Explicit operation allowlists, bounded data-only grammar, redaction and adversarial tests; WP-011/012/039/046/053 |
| Dense UI hides exclusions or local shortages | Aggregate looks sufficient while one unreachable group lacks service | Scope/distribution fixtures, text coverage labels, usability tasks; WP-022/029/030/052 |

TPM reviews risks and blocked packages at each integration checkpoint. A new requirement, model, or provider capability gets a source reference, owner, dependency impact, evidence plan, and forecast impact before entering active scope. Preserve work and source lineage; do not quietly weaken acceptance criteria to meet a date.

## 9. Verification, release, and immediate next work

The [verification matrix](roadmap/verification_matrix.md) is the release checklist. Required evidence comprises meaningful test runs with counts and skip reasons, independent arithmetic/model review, offline desktop tasks, provider capability/failure outcomes, safe round trips, native installation results, and bounded performance/accessibility results. Unit success cannot substitute for integrated behavior.

A release candidate freezes application/schema/catalog/model/numeric identities, exact locks, fixtures, pack digests, compatibility policy, and platform artifacts. QA records each gate's evidence and remaining limitations; TL accepts architecture boundaries; MODEL accepts evidence/coverage claims; PRODUCT accepts player-agency and inquiry behavior. This is an implementation review process, not a claim that approvals have already occurred.

Release notes must distinguish code/model defects, unsupported model effects, unavailable historical recomputation, untested provider capabilities, and platform limitations. No key or private civilization is included in diagnostics. A known limitation may be disclosed in a preview; missing required architecture behavior blocks calling the complete product delivered.

Begin with WP-001 to establish the issue/evidence ledger and settle the initial coverage and performance decisions. Then implement WP-002 and WP-003, start the WP-004 native feasibility probe, and define WP-005 contracts. Prepare source inventory independently in WP-025 after WP-008 provides the provenance contract. The first product demonstration is M2's offline loop; the full implementation objective remains M7.
