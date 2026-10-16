# Poliscope — Verification, Traceability and Release Evidence

Revision 0.2 · Distributed delivery baseline. Assignment and workflow authority: [distributed delivery plan](distributed_delivery.md).

This is the verification plan for the [implementation roadmap](../implementation_roadmap.md), [shared work packages](work_packages.md) and [domain packages](domain_work_packages.md). **No checks listed here have run against an application yet.** The repository is documentation-only at this planning baseline. Evidence links, counts and outcomes must be added during implementation; a planned check is not a passing check.

D references the [global game design](../design_doc.md); T references the [technical specification](../tech_spec.md), both revision 0.2. Source sections remain authoritative for behavior; proposed fixtures below make that behavior falsifiable.

## 1. Evidence requirements and outcome vocabulary

B maintains the two-person verification ledger; C takes designated integration/release evidence when active. Named contributors perform verification, model, security and product review within their allocated capacity. Each package/scenario has the accountable owner and different peer reviewer from the distributed plan. Maintain the ledger keyed by requirement/scenario, candidate identities, platform and work package. For each run record:

- Source requirement, package/issue and reviewer; command and actual selected target; run date, relevant OS/architecture and tool/runtime versions.
- Application/schema/catalog/model/numeric/protocol identities, source revision, pack/fixture digests, input/event/realization/result digests where relevant.
- Expected result and its independent derivation or behavioral oracle; actual result; executed test count; passed/failed/expected-failure/skipped/unrun breakdown and reasons.
- Current-run sanitized artifacts and logs; defect/limitation or external prerequisite; remediation owner; affected retest and acceptance decision.

Use **passed**, **failed**, **expected failure**, **skipped**, **unrun**, and **blocked by external prerequisite** distinctly. An expected failure remains a defect/known limitation, not a pass. Required checks that are unexplained failures, zero-test selections, unrun, or access-blocked cannot establish a gate. A supported application error such as stale apply rejection is a passing negative test only when the test verifies the expected error and absence of mutation.

Record model-coverage gaps separately from defects. An honestly qualitative effect may be valid released content under DEC-04; an implemented numerical rule producing wrong numbers is a defect. A structurally valid model is not automatically empirically validated. A live-provider access failure is not evidence of a simulation defect and does not erase independent offline successes.

## 2. Design-document traceability

| Requirement / source | Required delivered behavior | Implementation owners | Primary evidence |
|---|---|---|---|
| D-01 · D §1 | One civilization, open inquiry, student/designer/educator use, no prescribed optimal society | WP-001, WP-020, WP-052, WP-055 | E2E-001/002/016; inquiry usability review |
| D-02 · D §2 | Player goals optional, one world, honest coverage, reversibility, offline ownership | WP-007, WP-016–WP-024, WP-039, WP-046 | E2E-001–006/011/014; invariant and authority tests |
| D-03 · D §3 | Related scopes, separate conditions/design/assumptions/state/consequences/goals, explicit finite external boundaries | WP-005–WP-007, WP-013, WP-015, WP-020 | E2E-002/003/004/008; scope and partition fixtures |
| D-04 · D §4 | All twelve domains/branches share framework; institutional/cultural behavior is substantive | WP-025–WP-027, WP-032; DOM-01–DOM-12 | Domain conformance and inventory; E2E-004/008/016 |
| D-05 · D §5 | Shared time/population/resources, access/rights, institutions, space, meaning and coupled risk | WP-007, WP-013–WP-017, WP-030, WP-032, WP-034 | Independent accounts; education path and disruption; E2E-003/004/008/009 |
| D-06 · D §6 | Design, simulate, schedule, counterfactual/future distinction, reflect and compare | WP-018–WP-024, WP-033–WP-038 | E2E-001/005–010; history/replay fixtures |
| D-07 · D §7 | Readable interviews, full alternatives, preview before apply, clarification/deferral/templates/proposals | WP-021, WP-026, WP-028, WP-046, WP-049 | E2E-001/002/014/016; keyboard interview tests |
| D-08 · D §8 | All named workspaces synchronized to branch/revision-or-time/scope | WP-020–WP-023, WP-028–WP-031, WP-037, WP-049 | E2E-006/008/014/016; stale query/context tests |
| D-09 · D §9 | Defined diagnostic bars, units/coverage, target separation, three explanation layers | WP-006, WP-017, WP-022, WP-031, WP-038 | E2E-002/003/010; all status/threshold cases |
| D-10 · D §10 | Atlas and sparse domain/decision/scope matrices, explicit direction/type, lineage, accessible alternatives | WP-023, WP-028–WP-030, WP-051–WP-052 | E2E-008/016; sparse/asymmetric matrix and scale fixtures |
| D-11 · D §11 | Full optional BYOK/OpenRouter, visible context/spend, no assistant commit authority | WP-042–WP-050, WP-053 | E2E-013/014; provider capability and trust-boundary suites |
| D-12 · D §12 | Versioned map/content/models/evidence, imported corpus lineage, amendments and honest model status | WP-008, WP-012, WP-025–WP-027, WP-031; all DOM packages | Pack/import inventory, model review, E2E-008/011/015 |
| D-13 · D §13 | Linked design/time history, retained futures, exact runtime reproduction, explicit migration/comparability | WP-016, WP-018, WP-023, WP-035–WP-038, WP-041, WP-054 | E2E-005–007/010/015; native digest/replay matrix |
| D-14 · D §14 | Local saves, portable data, reports and educational prompts, independent privacy controls | WP-026, WP-031, WP-039–WP-040, WP-049, WP-052 | E2E-011/014/016; offline sharing/privacy review |
| D-15 · D §15 | Complete whole-game quality criteria: coupling, scope, branches, traces, AI, offline and accessibility | WP-032, WP-050–WP-056; all DOM packages | Full gate ledger and E2E-001–017 |
| D-16 · D §16 | Explicit model limits and local single-player architecture without universal social optimization | WP-001, WP-007, WP-012, WP-038, WP-052, WP-056 | Architecture/model review; no hidden score/server tests |

## 3. Technical-specification traceability

| Requirement / source | Required delivered behavior | Implementation owners | Primary evidence |
|---|---|---|---|
| T-01 · T §1 | Four cooperating subsystems share versioned state/model and context | WP-005, WP-007, WP-020, WP-049 | Boundary schemas and E2E-006/014 |
| T-02 · T §2 | Pinned chosen stack, sandboxed renderer, one Python engine, no application backend | WP-002–WP-006, WP-010–WP-011, WP-054 | Frozen installs, process/boundary tests, native launch |
| T-03 · T §3 | Catalog/world/registry/compiler/evaluation/time/measurement/explanation/history/assistant responsibilities | WP-007–WP-018, WP-026, WP-033–WP-036, WP-046 | Component contracts; integrated service surface in §4 below |
| T-04 · T §4 | Canonical ontology, weighted overlap, mechanism-defined policy inheritance, distinct state partitions | WP-005–WP-007, WP-013, WP-030 | Scope/authority/ownership fixtures; E2E-002/004/008 |
| T-05 · T §5 | Twelve module contract, typed ports, shared reducers, executable institutional procedures | WP-012, WP-015, WP-027, WP-032, WP-034; DOM-01–DOM-12 | Per-domain conformance, paired interfaces and all-domain tests |
| T-06 · T §6 | Versioned packs, bounded declarative data, safe proposals, evidence and supersession | WP-008, WP-012, WP-025–WP-026, WP-031, WP-046 | Tampered/invalid pack tests, model activation audit, E2E-011/014/015 |
| T-07 · T §7 | Decimal/units, solvers/SCCs, pure evaluation, conservation, uncertainty and deterministic identities | WP-006, WP-013–WP-019, WP-035, WP-038, WP-051 | Independent numerical fixtures, singular/nonconvergent solvers, E2E-003/007/010 |
| T-08 · T §8 | Integer-day multirate transitions, effective changes, atomic reduction, reproducible experiments | WP-033–WP-037; domain dynamic portions | E2E-007/009; boundary/fast-forward/checkpoint/cancellation tests |
| T-09 · T §9 | Explicit indicators/statuses/findings/goals/traces, empty goals and no score | WP-017, WP-022, WP-031, WP-038 | Status matrix, goal-isolation and trace completeness fixtures |
| T-10 · T §10 | Versioned bounded JSONL, all service groups, pure preview/idempotent/stale-safe apply | WP-005, WP-010–WP-011, WP-018, service owners in §4 | Fragmentation/limit tests, E2E-001/005/006; contract drift check |
| T-11 · T §11 | Sole SQLite writer, immutable history, safe data-only archives, explicit private export controls | WP-009, WP-018, WP-036, WP-039–WP-041, WP-049 | E2E-005/007/011/015; transaction/archive/migration adversarial tests |
| T-12 · T §12 | Complete-context query keys, sparse projections, accessible tables, engine comparability | WP-020, WP-022–WP-023, WP-028–WP-031, WP-037, WP-051–WP-052 | Stale-query, matrix/topology, comparability and keyboard evidence |
| T-13 · T §13 | Dedicated OpenRouter contract, safe keys/network, grounded tools, SSE/modalities/spend and optional offline AI | WP-042–WP-050, WP-053 | Capability table §7, E2E-013/014; mock + bounded live outcomes |
| T-14 · T §14 | Untrusted data boundaries, CSP, engine mismatch/crash, close/save/provider/solver failure isolation | WP-010–WP-011, WP-014, WP-018, WP-039, WP-041–WP-042, WP-053 | E2E-006/012/013/015; fault injection and threat review |
| T-15 · T §15 | Extensible shared modules, bounded performance/caching, deterministic concurrency and native bundles | WP-004, WP-012, WP-027, WP-051, WP-054 | Conformance, benchmark and native matrix evidence |
| T-16 · T §16 | Architecture-wide numerical, domain, replay, coverage, security, UI and portable validation | WP-003, WP-019, WP-024, WP-032, WP-050–WP-055 | All gate/scenario evidence; independent model review |
| T-17 · T §17 | Global architecture decisions remain true during delivery | WP-001, WP-011–WP-018, WP-033–WP-049, WP-055 | Architecture decision log and cross-boundary review |
| T-18 · T §18 | Pinned source corpus, attribution and current official provider API verification | WP-008, WP-025–WP-026, WP-043, WP-050, WP-056 | Immutable source/pack inventory; documentation retrieval date and live compatibility record |

## 4. Required service surface and implementation ownership

Schema presence is insufficient. Each service group needs positive, invalid-input, stale/context or cancellation cases where applicable, authorization/boundary tests, and an actual client call through main/preload. The assistant gets a read-only subset, never a generic service forwarder.

| T §10.2 service group | Packages delivering it | Required integration evidence |
|---|---|---|
| Runtime | WP-010–WP-011, WP-041 | Handshake/health/progress/cancel/shutdown, mismatch and child-crash recovery |
| Catalog/model | WP-008, WP-012, WP-025–WP-026, WP-028, WP-031 | List all domains/branches/questions; inspect definitions/options/coverage/sources; validate compatible and incompatible packs |
| World | WP-007, WP-018, WP-020, WP-030 | Create/open/query scope/entity/topology; preview condition/structure changes with no committed mutation |
| Design | WP-013–WP-018, WP-021–WP-022 | Evaluate, preview, apply, traces, conflict/obligation inspection, stale digest and idempotency |
| History | WP-018, WP-023, WP-041 | List, undo/redo, fork/rename, compare and explicit model-migration branch |
| Timeline | WP-033–WP-037 | Create/fork/schedule/advance/pause/cancel/replay/snapshot/results, atomic boundaries |
| Exploration | WP-028–WP-030 | Atlas query, domain/decision/scope matrix aggregate/drill, group distributions with bounded pagination |
| Goals/notes | WP-017, WP-031 | Preview/apply/query narrative notes and typed targets; physics unaffected |
| Content proposals | WP-012, WP-021, WP-026, WP-031, WP-046 | Create/validate/classify/preview; unknown mechanisms remain qualitative |
| Portability | WP-039–WP-041 | Validate/import, prepare/export/report, chunked archive/data, historical read-only mode |
| Assistant context | WP-046, WP-048–WP-049 | Scoped facts/excerpts/compare/preview, turn/usage records and deletion; no apply or arbitrary access |

## 5. Integrated scenario catalog

Fixtures below are synthetic and carry explicit model/evidence labels. Each scenario runs against actual engine services, and desktop scenarios use actual Electron/main/preload/child-process/storage paths. Provider calls use mocks except the explicitly authorized live compatibility run. Per-domain expected arithmetic/procedures are reviewed independently in addition to these scenarios.

| ID | Procedure / stimulus | Required observable result | Owner / gate |
|---|---|---|---|
| **E2E-001** | Create with named editable conditions → open any domain → inspect all alternatives/source → select → preview → cancel → preview/apply → inspect account/trace → close/reopen | Empty goals/policies initially; no mutation before Apply; exactly one durable decision; numbers/identity agree across engine/UI/storage; no AI needed | WP-019/024; M2 |
| **E2E-002** | Leave questions unanswered, add qualitative commitment, encounter incomplete model, edit a target and navigate to an unrelated domain | No forced progression/game over; unknown/partial/unsupported differ from zero; target creates only an observation; no auto redesign or ranking | WP-017/021/024/031; M2/M3 |
| **E2E-003** | Competing work/care/training claims, finite goods, losses, reservation, conditional imports and group-specific access | Independent stock/time/allocation balances match; no double count/reservation/hidden negative clamp; physical availability and actual access differ; finite external limits respected | WP-015/019/032; M2/M3 |
| **E2E-004** | Watershed and political region overlap; one cohort belongs to multiple networks; incompatible local/regional authority policies | Same canonical stock/cohort counted once; weighted/partitioned aggregation; explicit institutional conflict; input ordering cannot choose winner | WP-007/013/027/032; M3 |
| **E2E-005** | Concurrent stale preview, tampered payload/digest, duplicate apply, commit followed by lost IPC reply, undo then edit | Stale/tampered rejected without mutation; operation ID resolves one durable commit; old future preserved on separate branch; history/alternatives survive restart | WP-018/023/041; M2/M5 |
| **E2E-006** | Switch branch/scope during queries/stream, kill child, restart, introduce protocol mismatch, fail a save | Old results/replies retain old context; pending calls fail safely; last confirmed revision retained; edits blocked on mismatch; unsaved preview labeled; no reset | WP-020/041/049/053; M2/M6/M7 |
| **E2E-007** | Run mixed daily/weekly/seasonal/annual mechanisms and authored/stochastic events continuously, then checkpoint/resume/replay | Same canonical closing states/realizations/digests under pinned runtime; all required boundaries executed; cancellation cannot persist partial transition; unrelated stream unchanged | WP-033–WP-037; M4 |
| **E2E-008** | Enter through each domain; follow education service across all twelve, then inspect atlas/matrix/world/source and group distributions | Shared people/assets/accounts; substantive institutional/identity behavior; direction/edge type honest; blank matrix not independence; every view describes same state/coverage | WP-028–WP-032 + DOM-01–DOM-12; M3 |
| **E2E-009** | Schedule a future policy, fork a past state and introduce a resource/asset/channel disruption with finite response | Counterfactual and future change remain distinct; coupled effects/obligations consistent; no automatic rescue or game over; repair/response competes for capacity | WP-034–WP-037 + DOM-12; M4 |
| **E2E-010** | Compare compatible/incompatible quantities/models, enumerate sensitivity variants and request an explicit capacity bound | Only comparable values yield numeric deltas; missing is not zero; range is not midpoint/probability by default; solved variable/fixed inputs clear; target not optimizer | WP-023/038; M4 |
| **E2E-011** | Offline export branches/experiments → import into fresh data directory → produce Markdown/CSV; also import hostile/corrupt archive | History/events/identities preserved; report quantities match traces; optional private content excluded by default; keys/blobs always absent; invalid import has no partial commit | WP-039–WP-040/053; M5/M7 |
| **E2E-012** | Attack renderer/Markdown/source/pack/preload/archive boundaries with malicious data and oversized/invalid messages | No Node/SQL/shell/code execution or arbitrary authenticated fetch; validation and bounded errors; trusted registry only; application remains recoverable | WP-011/012/039/053; M7 |
| **E2E-013** | Test catalog/routing/privacy/schema/tool/modality/reasoning/usage capability matrix, plus auth/credit/rate/partial/cancel/redirect failures | Selected controls honored or explicitly rejected; actual route visible; keys isolated; no uncertain automatic paid retry; actual replaces estimate and unknown stays unknown; offline model intact | WP-042–WP-050/053; M6/M7 |
| **E2E-014** | Inspect/share limited context, attempt prompt/tool injection, navigate while reply streams, propose alternative, explicitly apply, delete transcript | Tools remain read-only/context-bound; private/unrelated material excluded unless included; proposal never self-commits; origin/evidence retained; transcript deletion leaves design history intact | WP-046–WP-049/053; M6/M7 |
| **E2E-015** | Open unavailable historical model, migrate compatible model to new branch, interrupt schema migration and restore backup | Historical results labeled read-only/cached rather than reproduced; explicit migrated branch preserves old one; backup/transaction recovery keeps confirmed state | WP-041/054; M5/M7 |
| **E2E-016** | Keyboard-only learner records expectation, answers/defers interview, locates assumption, compares branch, inspects matrix via list and exports observation | All core actions accessible; status has text; hypothesis/source/calculation/AI distinct; no assigned grading or goal; learner can explain consequence without AI | WP-052/055; M7 |
| **E2E-017** | Install each native artifact on target with no Node/Python; open offline, run common numeric/replay fixture, export/import, restart and remove key | Bundled engine resolution/permissions correct; supported numeric boundary reproduced; core functional tasks pass; OS key protection/session-only fallback honest; state survives restart | WP-054/055; M7 |

Additional domain fixtures must cover each package's branch inventory and selected static/transition models; the education example alone cannot certify all content or validity. Use numerical/procedural fixtures whose expectations are not generated by calling the implementation under test.

## 6. Test layers, invocation and gate policy

| Layer | Planned invocation / execution | Covers | Does not establish alone |
|---|---|---|---|
| Reproducible setup | `npm ci`; `uv sync --frozen --python 3.12` | Declared dependencies/locks, repeatable tools | Working application or models |
| Content/contract structure | `npm run content:validate`; `npm run contracts:check`; `npm run typecheck` | References/schema/generation/type integrity | Scientific validity or numeric correctness |
| Python | `uv run --frozen pytest` | Independent numeric fixtures, units/scopes, solvers, allocation, transitions, history, safe archive/storage, replay | Electron/provider networking or native operation |
| Desktop/provider contracts | `npm test` using Vitest/mocks | Preload/main validation, provider request/SSE/capability/error logic, UI state | Paid API behavior or installed packages |
| Desktop integration | `npm run test:desktop` using Playwright/Electron | Real engine/SQLite cross-boundary user tasks and offline/fault paths | Every native OS and empirical model validity |
| Packaging | `npm run package` on each native target, then installed smoke/replay tests | Bundled runtime, resource paths, signing/install/runtime behavior | Cross-platform support without actual per-target execution |
| Live providers | Separate explicit documented opt-in command defined by WP-050 | Current endpoint/model/provider behavior within authorized scope and spend | All providers/models forever, or privacy guarantees beyond stated controls |
| Performance/accessibility/model review | Explicit harness/manual protocols defined by WP-001/026/051/052 | Measured budgets, keyboard/assistive use, evidence/validity/limits | Correctness of unexecuted scenarios or unreviewed models |

CI runs default structural/engine/mock/desktop checks without keys and fails on real check failures while preserving command exit status. Platform-dependent jobs report which target ran. Live checks are opt-in, use explicit test profiles/credits and bounded request/cost limits, and do not silently enter ordinary test execution. A manually verified external capability still needs a reproducible evidence record.

### 6.1 Model review checklist

For every activated model record population/scope, operational definition, formula/procedure, units/denominator/time basis, source/assumption revisions, uncertainty, independently derived fixtures, invariants/bounds, behavior under missing data, validity range, distributional limits and unsupported extrapolation. Reviewer must distinguish empirical evidence from hypothetical educational assumptions. Qualitative mechanisms may record obligations/conflicts without numerical predictions; they do not receive fabricated effects to satisfy a test count.

### 6.2 Native platform matrix

| Target | Required native evidence | Baseline status |
|---|---|---|
| Windows x64 | Native Python bundle/Forge install, signing policy, no-system-Python smoke, resource paths, key store, recovery and numeric/replay fixtures | Unrun |
| macOS arm64 | Native bundle, signing/notarization, install/lifecycle, key store, resource paths and numeric/replay fixtures | Unrun |
| macOS x64 | Separate native architecture build/install and same functional/numeric checks; arm64 result does not certify it | Unrun |
| Linux x64 | Native bundle/install, executable permissions, secure backend and session-only fallback, headless desktop CI plus actual desktop operation, numeric/replay fixtures | Unrun |

OS minimum versions and installer formats are settled in WP-004 and tested in WP-054. Cross-build success is not native functional evidence. Reproducibility claims name their exact numerical/model runtime and supported platforms; approximate resemblance of displayed bars is insufficient.

## 7. Provider capability acceptance matrix

WP-050 maintains a dated model/provider-specific table with mock test IDs, live case/result, route metadata, limitations and evidence link. All rows below are **unrun** at this baseline. Test only capabilities actually supported by the selected documented model/provider; explicitly unsupported behavior is rejected and documented, not silently removed from requests. Select suitable models to exercise each required application capability path.

| Capability family | Required cases | Packages |
|---|---|---|
| Key/account and endpoint binding | Entry/test/replace/remove; authenticated key limits; OS protection vs session-only; redirect leak prevention; no key in engine/log/export | WP-042/043/053 |
| Catalog/capabilities | Full discovery/variants/search; pricing/context/modality/tools/reasoning metadata; unknown fields; timestamped refresh/cache/offline | WP-043 |
| Routing/privacy | order/only/ignore, fallbacks, supported-parameter enforcement, documented price/privacy/data-use preferences; incompatible control rejected; actual provider/model reported | WP-044/050 |
| Generation/structured response | Stream/nonstream, sampling/output/schema modes, local validation, finish reasons, model changes | WP-044/045/047 |
| Fragmented tools | Parallel/indexed fragments, full validation before execution, continuation/results, bounded rounds, no-tool models, attempted mutation rejected | WP-045/046 |
| Reasoning/history | Visible metadata separated; opaque continuation preserved only compatibly; no interpretation as world truth; explicit new thread when needed | WP-045/047 |
| Modalities/files | Supported text/image/audio/video/file input/output paths, size/context checks, provenance and explicit sharing, safe artifact rendering/retention, unsupported renderer/model rejected | WP-047 |
| Usage/cost/gates | Token categories, estimates vs actual vs unknown, generation metadata, late reconciliation, cancellation uncertainty, Decimal aggregation and new-request gates | WP-048 |
| Failure/cancellation/retry | Auth/credit/rate/model/provider failures, partial/malformed SSE, abort, late updates, deliberate paid retry, safe bounded metadata retry | WP-045/050 |
| Context and ownership | Bounded revision/scope manifest, consent for private notes/attachments/other branches, prompt injection, read-only tools/proposals, transcript deletion independent of history | WP-046/049/053 |
| Compatible-provider adapter | Declared common capability subset, custom endpoint validation, no OpenRouter-only assumptions, explicit unsupported feature errors | WP-042–WP-045/047/050 |

Provider documentation retrieval and live runs are implementation tasks. T §18's historical network denial is not evidence of current connectivity or a permanent prerequisite. Use actual runtime checks then; request needed credentials through supported secure configuration, never chat or tracked files. Missing live evidence limits compatibility claims; deterministic mocks remain required even when live tests pass.

## 8. Milestone acceptance record

For each gate fill in candidate identities, package status, evidence links, reviewer decision and outstanding defects. All gates are **open/not achieved** at this baseline.

| Gate | Required evidence bundle | Blocking omissions |
|---|---|---|
| G0 / M0 | Requirement/package ledger, named A/B owners and peers, actual availability/time zones, DEC-04 coverage, DEC-06 budgets, separate two/three-person forecast inputs, COL-01 | Unstaffed specialist duties, unknown reviewer capacity or no measurable scope |
| G1 / M1 | Frozen independent setup, generated contracts, secure renderer/preload, child handshake/storage/recovery, per-target feasibility report, COL-02/03/05 | Runtime boundary unverified, second developer cannot reproduce setup, candidate checks absent or native targets silently ignored |
| G2 / M2 | E2E-001–006 relevant cases, independent arithmetic, actual offline Electron/SQLite loop and reopened history, COL-04 | UI-only mocks, unexplained numeric/history failure, zero-test run |
| G3 / M3 | All domain static conformance/counterpart results, source branch inventory, E2E-004/008, complete exploration workspaces | Domain only decorative, duplicate state, unclassified branches, implied unsupported effects |
| G4 / M4 | All selected domain transitions, E2E-007/009/010, RNG/checkpoint/fast-forward equivalence and uncertainty limits | Partial transition commit, hidden skipped boundary, unexplained replay drift |
| G5 / M5 | E2E-011/015, full design+experiment privacy-safe round trip, reports/CSV, backup/migration/historical mode | Unsafe or partial import, key/private export leak, silent historical recomputation |
| G6 / M6 | Provider capability table, E2E-013/014, mock and bounded live outcomes, secure keys and spending/context controls | Assistant commit path, silent capability/privacy dropping, required live compatibility unverified |
| G7 / M7 | WP-055 full trace ledger, E2E-001–017, current collaboration evidence, numeric budgets, accessibility/model/security review, all native artifacts, release inventory/docs | Unexplained required failures, unmet core architecture, untested claimed native/provider support |

A gate's recorded evidence must match the actual frozen candidate. A change to a mechanism, schema, pack, runtime, provider adapter or dependency requires an impact assessment and affected checks; it does not automatically invalidate unrelated evidence, and it cannot silently reuse evidence for changed behavior. WP-056 records final acceptance and publication separately.

## 9. Distributed-development acceptance

These checks validate the delivery workflow. All are **unrun** at this documentation-only revision. Validate the two-contributor allocation independently. COL-06 applies when C joins. Other COL evidence is required at the indicated gate and repeated only when an affected boundary/setup/process changes.

| ID / owner / peer | Procedure and evidence | Gate / failure condition |
|---|---|---|
| COL-01 / B / A | Assign all 68 parents and initial children to actual A/B people with different peers; record zones, weekly hours, review windows, next-ready fallback, shared-path ownership, external access gaps and resource-loaded forecast inputs | M0: fail if duties are scheduled to an unstaffed specialty, two implementations require the same person's time, or C is required by the two-person plan |
| COL-02 / B / A | A and B independently bootstrap clean clones at the same SHA with locked dependencies, documented commands and isolated user-data directories; run real child handshake plus engine/desktop checks; capture OS/runtime identities and no tracked drift | M1: fail if either requires another developer's untracked schema, DB, absolute path or global undocumented tool |
| COL-03 / A / B | Implement an approved contract increment on producer and consumer branches; test current pair, supported previous fixtures and explicit incompatible-version rejection; integrate real operations on one candidate | M1 initially; repeat on boundary changes: fail if silent drift, numeric loss or mock-only compatibility replaces actual producer/consumer behavior |
| COL-04 / B / A | Complete one small child with a written end-of-period handoff and review in the next agreed working window while the peer advances independent approved work; run merged offline real-engine slice and capture review wait/blocked cause | M2: fail if progress depends on an undocumented synchronous conversation or self-approval; missed service targets require queue/capacity correction and another observed handoff |
| COL-05 / B / A | Verify required candidate checks and one-nonauthor review; demonstrate two locally green branches whose combination fails a shared contract fixture are blocked before integration. Use merge queue or branch update/recheck; record unavailable protection permissions and enforced/manual status accurately | M1: fail if stale separate-branch green runs authorize a combined failing merge, or protection is claimed without evidence |
| COL-06 / C / A | When C joins, reproduce setup, run shared fixtures and complete a small peer-reviewed child; transfer listed parents after in-flight children merge, update reviewer/fallback queues and forecast; verify A/B can resume if C leaves | Before C takes transferred parent queues: fail if transferred work has two owners or depends on undocumented knowledge; not applicable until C joins |

The gate owner collects each contributor's evidence on the same candidate SHA. Author-local tests are necessary but do not substitute for peer review or independent numerical expectations. Use workflow metrics to adjust queues, dependencies and review capacity. Existing product, platform, provider and model gates remain unchanged.
