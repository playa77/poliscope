# Poliscope — Verification, Traceability and Release Evidence

Revision 0.5 · Agent allocation at work-package boundaries. Assignment and workflow authority: [distributed delivery plan](distributed_delivery.md).

This is the verification plan for the [implementation roadmap](../implementation_roadmap.md), [shared work packages](work_packages.md) and [domain packages](domain_work_packages.md). **No checks listed here have run against an application yet.** The repository is documentation-only at this planning baseline. Evidence links, counts and outcomes must be added during implementation; a planned check is not a passing check.

D references the [global game design](../design_doc.md); T references the [technical specification](../tech_spec.md), both revision 0.3 dated 2026-10-16. Source sections remain authoritative for behavior; proposed fixtures below make that behavior falsifiable. WP-001 expands each section into stable leaf requirement IDs with owner, first gate and positive/negative oracle; section-level coverage alone cannot establish complete requirement coverage.

## 1. Evidence requirements and outcome vocabulary

Human controllers maintain the package/availability ledger; agents maintain evidence for their assigned packages. Each executable package records its owner/controller, division of work and validation route before start and retains them through completion. Agent review, SV, deferred review and required human approval are distinct evidence types. Key the verification ledger by requirement/scenario, candidate identity, platform and package. For each run record the exact subcase IDs from §5.1 and any RT regression obligations from §5.2, then:

- Source requirement, package/issue, agent owner/controller, package validation route and assigned reviewer or review-package reference; command and actual selected target; run date, relevant OS/architecture and tool/runtime versions.
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
| T-16 · T §16 | Architecture-wide numerical, domain, replay, coverage, security, UI and portable validation | WP-003, WP-019, WP-024, WP-032, WP-050–WP-055 | All gate/scenario evidence; model evidence review with declared validation mode |
| T-17 · T §17 | Global architecture decisions remain true during delivery | WP-001, WP-011–WP-018, WP-033–WP-049, WP-055 | Architecture decision log and cross-boundary review |
| T-18 · T §18 | Pinned source corpus, attribution and current official provider API verification | WP-008, WP-025–WP-026, WP-043, WP-050, WP-056 | Immutable source/pack inventory; documentation retrieval date and live compatibility record |

## 4. Required service surface and implementation ownership

Schema presence is insufficient. Each service group needs positive, invalid-input, stale/context or cancellation cases where applicable, authorization/boundary tests, and an actual client call through main/preload. The assistant gets a read-only subset, never a generic service forwarder.

| T §10.2 service group | Packages delivering it | Required integration evidence |
|---|---|---|
| Runtime | WP-010–WP-011, WP-041 | Handshake/health/authorized operation-status/progress/cancel/shutdown, completed replay before head validation, trusted read-only historical interface and child-crash recovery |
| Catalog/model | WP-008, WP-012, WP-025–WP-026, WP-028, WP-031 | List all domains/branches/questions; inspect definitions/options/coverage/sources; validate compatible and incompatible packs |
| World | WP-007/009/018 production creation/query child before WP-019; WP-020/030 consumers | Create/open/query scope/entity/topology headlessly before UI acceptance; preview condition/structure changes with no committed mutation |
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
| **E2E-015** | Open unavailable historical model, migrate compatible model to new branch, interrupt schema migration and restore backup | Historical results labeled retained/read-only, or unavailable when omitted, rather than reproduced; explicit migrated branch preserves old one; backup/transaction recovery keeps confirmed state | WP-041/054; M5/M7 |
| **E2E-016** | Keyboard-only learner records expectation, answers/defers interview, locates assumption, compares branch, inspects matrix via list and exports observation | All core actions accessible; status has text; hypothesis/source/calculation/AI distinct; no assigned grading or goal; learner can explain consequence without AI | WP-052/055; M7 |
| **E2E-017** | Install each native artifact on target with no Node/Python; open offline, run common numeric/replay fixture, export/import, restart and remove key | Bundled engine resolution/permissions correct; supported numeric boundary reproduced; core functional tasks pass; OS key protection/session-only fallback honest; state survives restart | WP-054/055; M7 |

Additional domain fixtures must cover each package's branch inventory and selected static/transition models; the education example alone cannot certify all content or validity. Use numerical/procedural fixtures whose expectations are not generated by calling the implementation under test.

### 5.1 Exact subcases and first-required gates

The scenario table above describes aggregate workflows. The following manifest is normative for selecting application cases; "relevant cases" is not a selection rule. A bare ID below means its complete scenario; a suffixed ID means only the explicitly described subcase. First-required cases remain required in subsequent affected regression runs. All cases are **unrun** at this documentation baseline. Setup, structural/contract checks, per-domain acceptance and COL workflow evidence remain additional requirements at their stated gates.

| Case ID | Exact case scope | First required gate / production prerequisite |
|---|---|---|
| E2E-001 | Complete create → preview/cancel/apply → trace → reopen offline workflow | G2; WP-018 production creation/query and WP-020/021/022 consumers |
| E2E-002.a | Unanswered/qualitative/incomplete design, no forced progression and navigation to another domain | G2; WP-017/018/021 |
| E2E-002.b | Engine target edit/observation leaves physical results and allocation unchanged; no target UI required | G2; WP-017/018 |
| E2E-002.c | Persisted target/note editing UI, private classification and cross-view observation | G3; WP-031 |
| E2E-003.a | Synthetic finite stock/labor contention, loss, reservation, finite import and group access; actual output follows allocated input; precision edge rejection/residuals | G2; WP-006/014/015/019 |
| E2E-003.b | Corresponding production domain mechanisms/counterparts and distributions across the declared all-domain inventory | G3; WP-032 and static DOM packages |
| E2E-004.a | Synthetic canonical overlap, single accounting and unresolved policy conflicts invariant under input order | G2; WP-007/013/019 |
| E2E-004.b | Domain harness/counterpart and world/matrix projections for that overlap | G3; WP-027/030/032 |
| E2E-005 | Complete stale/tampered/duplicate/lost-reply/undo workflow, including identical completed retry after head advancement, operation-status lookup and changed-payload/cross-context key reuse | G2; WP-018/023 |
| E2E-006.a | Switch scope/branch during ordinary queries, crash/restart, cold protocol mismatch through trusted historical reader, failed save and correctly labeled last-confirmed/unsaved state; no provider streaming | G2; minimal reader in WP-010/011 and WP-018/020 |
| E2E-006.b | Switch branch during provider streaming and reject late/cancelled updates without relabeling a reply | G6; WP-045/049 |
| E2E-006.c | Expanded forced-close/disk/permission/protocol/network fault matrix across all production paths | G7; WP-053 |
| E2E-007 | Complete mixed-rate/authored/stochastic run, instance/event/draw identity, paired/new-realization forks and checkpoint/replay; inject invariant failure and crashes before/after durable boundary commit | G4; WP-033–WP-036 |
| E2E-008 | Complete all-domain entry/education/atlas/matrix/world/evidence workflow | G3; WP-028–WP-032 and static DOM packages |
| E2E-009 | Complete future-adoption/counterfactual/disruption workflow; disjoint/conflicting same-base deltas and same-boundary ordering preserve unrelated policies, stocks/assets and pending cases | G4; WP-033–WP-037 and selected domain transitions |
| E2E-010.a | Compatible/incompatible design comparison with independent deltas, no ranking or missing-as-zero | G2; WP-023 |
| E2E-010.b | Sensitivity, explicit capacity bound, repeated/shared uncertain variables and common-cause dependence; qualified unsupported methods | G4; WP-035/038 |
| E2E-011 | Complete ordinary/reduced archive, fresh-directory round trip and Markdown/CSV; invalid/hostile import is transactional; omission covers historical/derived private copies | G5; WP-039/040 (WP-053 later expands attacks) |
| E2E-012.a | Main/preload sender/frame and schema enforcement, untrusted rendering, passive resource network sink and bounded IPC errors | G1; WP-010/011 |
| E2E-012.b | Trusted registry/bounded expression and invalid-unit/operator/state-write attacks | G2; WP-012/014/015 |
| E2E-012.c | Archive/portable-content path, type, hash, decompression, executable-content and transactional rejection cases | G5; WP-039/041 |
| E2E-012.d | Full combined attachment/prompt/provider/import/renderer attack and recovery matrix | G7; WP-047/053 |
| E2E-013 | Complete provider capability/failure/usage scenario, concurrent reservations and per-continuation dispatch gates; explicit bounded live cases remain separately authorized | G6; WP-042–WP-050 |
| E2E-014 | Complete sharing/tool/proposal/deletion workflow; inspect every outbound payload including history, errors, tool results, artifacts and continuations; test revocation/out-of-envelope retrieval | G6; WP-046–WP-049 |
| E2E-015.a | Applied-revision values/trace closure survive complete acceleration-cache eviction and missing numeric runtime; minimal trusted read-only inspection | G2; WP-009/010/017/018 |
| E2E-015.b | Confirmed timeline evidence and operation outcomes survive checkpoint/cache eviction and restart | G4; WP-034/036 |
| E2E-015.c | Structurally safe absent-mechanism archives open read-only, unreadable schemas preserve originals with a diagnostic, reduced/legacy evidence is labeled, explicit model migration and interrupted backup/restore preserve old evidence/deduplication | G5; WP-039/041 |
| E2E-016.a | Keyboard-only core offline creation/interview/preview/account/trace/fork/comparison tasks, status text and focus recovery | G2; WP-020–WP-024 |
| E2E-016.b | Complete learner inquiry/report task and accessibility audit across every delivered workspace | G7; WP-052/055 |
| E2E-017 | Complete native install/offline/replay/round-trip/key-removal workflow on both current targets (Windows x64 and Linux x64) | G7; WP-054/055 |

| Gate | New mandatory application selections (plus retained affected earlier cases) |
|---|---|
| G0 / M0 | No application case can pass here; verify requirement/gate manifests, allocation templates and decision records |
| G1 / M1 | E2E-012.a; frozen setup/contracts, actual child/storage/handshake and minimal historical-reader smoke evidence |
| G2 / M2 | E2E-001, E2E-002.a, E2E-002.b, E2E-003.a, E2E-004.a, E2E-005, E2E-006.a, E2E-010.a, E2E-012.b, E2E-015.a, E2E-016.a |
| G3 / M3 | E2E-002.c, E2E-003.b, E2E-004.b, E2E-008; all static domain/counterpart and branch inventory checks |
| G4 / M4 | E2E-007, E2E-009, E2E-010.b, E2E-015.b; all selected domain transition checks |
| G5 / M5 | E2E-011, E2E-012.c, E2E-015.c |
| G6 / M6 | E2E-006.b, E2E-013, E2E-014; provider capability matrix and explicit live evidence |
| G7 / M7 | E2E-006.c, E2E-012.d, E2E-016.b, E2E-017; complete retained case inventory at the frozen candidate plus performance/model/accessibility/security evidence |

WP-003 must fail a gate selection that silently omits a mandatory subcase, selects zero tests, substitutes a mock for a required real service, or relies on an undeclared later package. Gate completion is not blocked by explicitly future-only subcases. COL review-route conditions must be recorded: the SV inspection/deferral record applies when SV was selected, while a later nonauthor follow-up is separate evidence, not retroactive approval. Impact assessment governs reuse of unchanged earlier evidence; changed behavior needs affected reruns with candidate identities.

### 5.2 Red-team regression obligations

The [2026-10-16 review](../reviews/2026-10-16-red-team.md) records the baseline finding and documentation disposition. Every row below remains **unrun** until the owning production case executes. Documentation resolution is not implementation acceptance.

| Finding | Required oracle / negative case | Case selection and owner |
|---|---|---|
| RT-01 | Evict all disposable caches; accepted values and explanatory closure survive without old runtime and round-trip normally; reduced evidence is explicit | E2E-015.a/b/c, E2E-011; WP-009/017/018/036/039/041 |
| RT-02 | Cold protocol mismatch and safe absent-mechanism archive use trusted reader; unsafe/unreadable structures still reject without mutation | E2E-006.a, E2E-015.c; WP-010/011/039/041 |
| RT-03 | Same-base disjoint/conflicting policy deltas and simultaneous adoptions preserve unrelated configuration and evolved state | E2E-009; WP-033/034/036 |
| RT-04 | Invariant failure/cancel/crash at staging/validation/commit/publication exposes only valid confirmed boundaries | E2E-007, E2E-006.c; WP-034/036/053 |
| RT-05 | Identical completed retry after head advancement returns original outcome; changed-payload key reuse conflicts; status and cross-context access are bounded | E2E-005, E2E-007; WP-005/010/018/036/041 |
| RT-06 | Two services each requesting 100 from energy supply 100 report only allocation-supported output; coupled feedback is solved or explicitly unresolved | E2E-003.a, E2E-007; WP-014/015/016/034 |
| RT-07 | Historical notes/turns/rationale/excerpts/indexes carry private canaries; omission and deletion cover active owned copies; projection integrity and backup limits are honest | E2E-002.c, E2E-011, E2E-014; WP-031/039/046/047/049/053 |
| RT-08 | Injected read-only tools cannot disclose excluded payloads or existence metadata in any subsequent provider request; revocation blocks dispatch | E2E-014; WP-046/047/049/053 |
| RT-09 | Controlled sink receives no request from rendering image/media/CSS/SVG/embed/artifact content; unauthorized sender frames fail | E2E-012.a/d, E2E-014; WP-011/047/053 |
| RT-10 | Allowance 1 with concurrent estimates 0.6 grants at most one dispatch; continuation, cancellation, duplicate grant and late actuals obey reservations | E2E-013; WP-045/046/048/050 |
| RT-11 | `1E29` stock and repeated withdrawals of 1 reject unsupported resolution before mutation or follow an exact declared quantum/residual policy; higher-precision oracle detects rounded-equality false passes | E2E-003.a, E2E-007; WP-006/015/034 |
| RT-12 | Same-definition instances in one scope do not collide; unrelated insertion, named draw purposes, fork policy and checkpoint replay preserve the declared realization | E2E-007; WP-005/035 |
| RT-13 | Same variable `x + (1-x)` has exact supported result 1; shared drought creates declared joint shortages; unsupported propagation is qualified | E2E-010.b, E2E-007; WP-008/035/038 and affected domains |
| RT-14 | Every mandatory subcase has explicit first gate/production prerequisite; missing/zero selection fails; M3 UI and M6 stream cases cannot become hidden M2 prerequisites | §5.1 manifest check at G0, selection enforcement at G1–G7; WP-001/003/019/024/055 |

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

The required native matrix consists of Windows x64 and Linux x64 only.

| Target | Required native evidence | Baseline status |
|---|---|---|
| Windows x64 | Native Python bundle/Forge install, signing policy, no-system-Python smoke, resource paths, key store, recovery and numeric/replay fixtures | Unrun |
| Linux x64 | Native bundle/install, executable permissions, secure backend and session-only fallback, headless desktop CI plus actual desktop operation, numeric/replay fixtures | Unrun |

OS minimum versions and installer formats are settled in WP-004 and tested in WP-054. Cross-build success is not native functional evidence. Reproducibility claims name their exact numerical/model runtime and supported platforms; approximate resemblance of displayed bars is insufficient.

## 7. Provider capability acceptance matrix

WP-050 maintains a dated model/provider-specific table with mock test IDs, live case/result, route metadata, limitations and evidence link. Current deterministic paths and explicit live blockers are recorded in the [dated compatibility table](../provider_compatibility.md) and its executable fixture matrix. All live capability rows remain **access-blocked / untested** as of 2026-10-26; no OpenRouter compatibility or G6/M6 acceptance is inferred. Test only capabilities actually supported by the selected documented model/provider; explicitly unsupported behavior is rejected and documented, not silently removed from requests. Select suitable models to exercise each required application capability path.

| Capability family | Required cases | Packages |
|---|---|---|
| Key/account and endpoint binding | Entry/test/replace/remove; authenticated key limits; OS protection vs session-only; redirect leak prevention; no key in engine/log/export | WP-042/043/053 |
| Catalog/capabilities | Full discovery/variants/search; pricing/context/modality/tools/reasoning metadata; unknown fields; timestamped refresh/cache/offline | WP-043 |
| Routing/privacy | order/only/ignore, fallbacks, supported-parameter enforcement, documented price/privacy/data-use preferences; incompatible control rejected; actual provider/model reported | WP-044/050 |
| Generation/structured response | Stream/nonstream, sampling/output/schema modes, local validation, finish reasons, model changes | WP-044/045/047 |
| Fragmented tools | Parallel/indexed fragments, full validation before execution, continuation/results, bounded rounds, no-tool models, attempted mutation and unauthorized result disclosure rejected | WP-045/046 |
| Reasoning/history | Visible metadata separated; opaque continuation preserved only compatibly; no interpretation as world truth; explicit new thread when needed | WP-045/047 |
| Modalities/files | Supported text/image/audio/video/file input/output paths, size/context checks, provenance and explicit sharing, safe artifact rendering/retention, unsupported renderer/model rejected | WP-047 |
| Usage/cost/gates | Token categories, estimates/actual/unknown, durable atomic dispatch reservations, concurrent/continuation gates, late reconciliation and cancellation uncertainty, Decimal aggregation | WP-045/048 |
| Failure/cancellation/retry | Auth/credit/rate/model/provider failures, partial/malformed SSE, abort, late updates, deliberate paid retry, safe bounded metadata retry | WP-045/050 |
| Context and ownership | Bounded revision/scope manifest, consent for private notes/attachments/other branches, prompt injection, read-only tools/proposals, transcript deletion independent of history | WP-046/049/053 |
| Compatible-provider adapter | Declared common capability subset, custom endpoint validation, no OpenRouter-only assumptions, explicit unsupported feature errors | WP-042–WP-045/047/050 |

Provider documentation retrieval and live runs are implementation tasks. T §18's historical network denial is not evidence of current connectivity or a permanent prerequisite. Use actual runtime checks then; request needed credentials through supported secure configuration, never chat or tracked files. Missing live evidence limits compatibility claims; deterministic mocks remain required even when live tests pass.

## 8. Milestone acceptance record

For each gate fill in candidate identities, package status, evidence links, validation decision/mode, deferred reviews and outstanding defects. All gates are **open/not achieved** at this baseline.

| Gate | Required evidence bundle | Blocking omissions |
|---|---|---|
| G0 / M0 | Requirement/package ledger, capability definitions and package allocation/completion rules, controller/agent records, DEC-04 coverage, DEC-06 budgets, ready-queue and package-boundary forecast inputs, COL-01/07 | Unstaffed specialist duties, unknown reviewer capacity or no measurable scope |
| G1 / M1 | Frozen independent setup, generated contracts, secure renderer/preload, child handshake/storage/recovery, per-target feasibility report, COL-02/03/05 and applicable COL-08 | Runtime boundary unverified, executing agent or clean checkout cannot reproduce setup, candidate checks absent or native targets silently ignored |
| G2 / M2 | Exact G2 selections in §5.1, independent arithmetic, actual offline Electron/SQLite loop, retained evidence/reopened history, COL-04 and the declared COL-08 SV/deferral route when selected | UI-only mocks, unexplained numeric/history failure, zero-test run |
| G3 / M3 | All domain static conformance/counterpart results, source branch inventory, E2E-004/008, complete exploration workspaces | Domain only decorative, duplicate state, unclassified branches, implied unsupported effects |
| G4 / M4 | All selected domain transitions, E2E-007/009/010, RNG/checkpoint/fast-forward equivalence and uncertainty limits | Partial transition commit, hidden skipped boundary, unexplained replay drift |
| G5 / M5 | E2E-011/015, full design+experiment privacy-safe round trip, reports/CSV, backup/migration/historical mode | Unsafe or partial import, key/private export leak, silent historical recomputation |
| G6 / M6 | Provider capability table, E2E-013/014, mock and bounded live outcomes, secure keys and spending/context controls | Assistant commit path, silent capability/privacy dropping, required live compatibility unverified |
| G7 / M7 | WP-055 full trace ledger, E2E-001–017, package-boundary workflow evidence and recorded validation routes, numeric budgets, accessibility/model/security review, all native artifacts, release inventory/docs | Unexplained required failures, unmet core architecture, untested claimed native/provider support |

A gate's recorded evidence must match the actual frozen candidate. A change to a mechanism, schema, pack, runtime, provider adapter or dependency requires an impact assessment and affected checks; it does not automatically invalidate unrelated evidence, and it cannot silently reuse evidence for changed behavior. WP-056 records final acceptance and publication separately.

## 9. Package allocation and execution acceptance

All operational workflow checks are **unrun** at this documentation-only baseline. Plans cover one to three development agents under human control. Availability changes govern new allocations at package boundaries; ownership and the agreed execution plan remain stable within each active package. Scenarios distinguish document checks, dry runs, agent technical review and actual human approval.

The responsible agent for a verification package is selected at that package's start. Human controllers retain allocation and required authorization decisions. Every gate aggregates the contributing packages' exact candidates, validation routes, mandatory subcase IDs and outcomes; no global agent-count setting changes accepted evidence or active package requirements.

| ID | Procedure / evidence | Gate / failure condition |
|---|---|---|
| COL-01 | Check all 68 planning packages for capabilities, dependencies and acceptance. Verify ready/start/completion records, pre-execution decomposition and agent/controller allocation. WP-001 establishes the process; repeat it for later package starts | M0 and each executable-package start: fail if future packages require fixed project agent identities, a ready package lacks a start contract or an active package changes owner/division of work |
| COL-02 | At each new agent's first package, pull the current baseline, reproduce setup/checks and inspect package/contract records. Use isolated environments and a clean checkout for solo execution. Capture actual runtime/source identities | M1 and later new-agent starts: fail if execution needs another session's untracked files, local DB, undocumented tools or private decisions |
| COL-03 | Allocate contract, producer and consumer packages with fixed start records. Implement sequentially with one agent or concurrently with compatible write scopes. Verify supported version combinations, explicit rejection and production integration | M1 and boundary changes: fail on semantic drift, numeric loss, overlap or acceptance based only on mock compatibility |
| COL-04 | Complete a package, publish checkpoint/candidate/decisions/evidence and next-ready inputs, then let a different agent start the next package from those records. With concurrent execution, keep an unrelated package running throughout; with one agent, change agent identity between consecutive packages | M2 and handoff checks: fail if the next package requires private session memory or the unrelated active package changes owner/plan |
| COL-05 | Validate the candidate against current main with required checks, the package's fixed agent-review/SV route and actual account-level approval requirements. Exercise shared-account agent review without representing it as separate GitHub-account approval | M1 and CI changes: fail on stale evidence, human/agent approval conflation, branch-rule bypass or review rules changed solely because agent count changed |
| COL-06 | Exercise 1→2, 1→3, 2→1, 2→3, 3→1 and 3→2 at package completion/start boundaries. Departing agents complete their final package; joining agents take compatible unstarted packages. Include same-count replacement and packages completing independently | M0 procedure coverage; later boundary exercises: fail if another active package is reassigned, a common milestone/team barrier is required, write scopes overlap or completed evidence is discarded |
| COL-07 | Snapshot active package owner/controller, collaborators, division of work, scope and validation route. Change availability for upcoming allocations, complete a different package and start new ready work. Assert the first package's snapshot is unchanged. For an unexpected interruption, preserve the blocked package and explicit recovery record | Each allocation-path validation: fail on automatic takeover, count-driven validation downgrade, global reassignment of active packages or an interrupted execution silently changing owner |
| COL-08 | Validate an executable package using the SV route selected at start: separate derivation, inspection, required checks and deferred agent-review record. After completion allocate a distinct nonauthor review package; record reviewer identity and findings separately from human authorization | First applicable solo acceptance and follow-up review: fail if a session restart is labeled independent review, agent review is labeled human signoff, required evidence is waived or extra capacity retroactively changes the completed package's route |

Evidence remains attached to the original package and candidate. Human controllers use boundary records to update availability, ready work and forecasts. Active package plans, product/model requirements and actual repository permissions remain stable while new packages can be assigned to a different one-to-three-agent lineup.
