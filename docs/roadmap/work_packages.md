# Poliscope — Shared Implementation Work Packages

Status baseline: every package is **not started**. Parent plan: [implementation roadmap](../implementation_roadmap.md). Companion registers: [domains](domain_work_packages.md) and [verification](verification_matrix.md).

## Reading and using this register

Revision 0.4 follows the [work-package delivery plan](distributed_delivery.md). Packages define scope, required capabilities, dependencies and acceptance; they do not reserve named agents for the project. Human controllers allocate a development agent and record the package execution plan before it starts. Its owner, agreed division of work and validation route remain fixed through completion. Availability is reassessed for subsequent packages at each completion/start boundary, while other active packages continue unchanged.

`Depends` lists acceptance prerequisites. A validated, merged contract package can authorize dependent development before the aggregate parent scope is complete; record the exact SHA and limitations. Each executable package follows its declared agent-review or solo-validation (SV) route. Human authorization and required scientific/technical evidence remain separate. Specialty abbreviations: TL = architecture/integration; ENG = engine; DESK = desktop; MODEL = content/model evidence; QA = verification/security/release; TPM = delivery coordination; PRODUCT = product intent/usability. These identify capabilities, not permanent people or agents.

Decompose large inventory packages before execution into bounded executable packages with separate IDs, write scopes, prerequisites, deliverables and acceptance criteria. Parent IDs retain aggregate scope and gates. Allocate each executable package at its own start; its internal assignment remains stable. Producer/consumer packages can run sequentially or concurrently using validated contracts. Handoffs preserve source versions, evidence, limitations and the next action so a different agent can own the next package. Paths are proposed responsibility locations confirmed by WP-002. D/T references point to the [design](../design_doc.md) and [technical specification](../tech_spec.md).

Domain packages use the same registry, world, accounts, content, UI, and transition services built here. Cross-domain acceptance is coordinated by WP-032 and WP-055. M3 includes the static portions of domain packages; their transition portions finish with M4. This does not allow a domain to be marked fully verified at M3 if its transition work is unfinished.

## A. Baseline and runtime foundation — M0/M1

### WP-001 — Delivery baseline, requirement ledger, and implementation decisions

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** TPM + TL; review expertise PRODUCT, MODEL, QA. **Size:** M. **Depends:** none. **Sources:** D §§1–16; T §§1–18.

- Create implementation issue templates using the package IDs, source sections, agent owner/controller, agreed division of work and package validation route, changed paths, contract/base SHA, acceptance criteria, evidence links, status, blockers and next working-window handoff. Define the available-agent list, controller contacts, package readiness, assignment/completion records, write-scope reservations, handoffs and access prerequisites. Reassess capacity and ready work at each package boundary; retain active package plans. Allocate duties when the corresponding executable package starts. Record the documentation-only baseline and an architecture decision log; repair or separately track broken companion links without rewriting requirements.
- Define the release content inventory policy: branch-by-branch coverage, minimum substantive behavior per domain, evidence review roles, and clearly labeled synthetic/reference setups. Distinguish implementation deliverables from open model research.
- Resolve DEC-04's initial scope and DEC-06's benchmark definitions: named world-size fixtures, benchmark machine/OS, latency/throughput/memory budgets, and measurement method. Produce a dependency/resource forecast and external prerequisite register; no unsupported completion date.

**Acceptance/evidence:** every D/T top-level section maps to packages and a verification owner; all 68 planning packages have capability requirements, dependencies and acceptance criteria; executable-package records require one agent owner/controller and a stable execution plan; the ready queue supports one to three agents and all six capacity changes at package boundaries; active packages remain unchanged; performance and content acceptance have measurable definitions or named blocking decision issues. Approved planning decisions are recorded, not silently substituted for specification requirements.

### WP-002 — Reproducible repository scaffold and development commands

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** TL + DESK + ENG. **Size:** M. **Depends:** WP-001. **Sources:** T §§2, 15; README Development.

- Validate the minimum shared layout, then allocate separate Python and desktop scaffold packages from the ready queue. Verify frozen setup in each executing agent environment and an additional clean checkout for solo execution; isolate paths, databases and secrets. Establish `desktop/{main,preload,renderer}`, Python engine packages, content/contracts/tests, packaging configuration, and sanitized local-configuration templates. Keep private state under an application/user-data path, never tracked content.
- Pin Node 24 LTS/Python 3.12 and compatible stable Electron/Forge/Vite/React/TypeScript, TanStack Query/Recharts, Pydantic 2, testing and bundling tools. Commit npm/uv locks; justify any additional runtime dependency.
- Implement the README's install/dev/check/test/package command contract. `npm run dev` resolves and starts the managed Python engine through main, without shell interpolation or requiring a separate model server. Document OS-specific development prerequisites.

**Acceptance/evidence:** a clean checkout installs with `npm ci` and `uv sync --frozen --python 3.12` without lock changes; commands run from the repository root and propagate failures. Another developer can follow the instructions without undocumented global tools. Runtime/code remains intentionally minimal until later packages.

### WP-003 — Test harnesses, CI, and evidence capture

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** QA; review expertise ENG + DESK. **Size:** M. **Depends:** WP-002. **Sources:** T §16; D §15.

- Set up pytest, Vitest, and Playwright Electron harnesses, temporary user-data/database directories, synthetic content and a provider mock server/transport. Ordinary checks must not access real keys or spend money.
- Wire content validation, generated-contract drift, cross-version fixtures, type checks, engine tests, desktop/provider tests and real-child desktop smoke checks into CI. Require passing checks on a candidate containing current main, using a merge queue or an updated branch. Require the package's declared nonauthor-agent review or SV checklist/deferred-review record, alongside actual repository approval rules. Keep account-level protection stable across agent-count changes; agents sharing an account cannot supply separate GitHub approval identities. New behavior changes invalidate stale approval/evidence. Add native matrix jobs as supported runners become available in WP-004/WP-054.
- Capture command exit status, test counts, skip/expected-failure reasons, fixture versions, runtime identities, and current-run artifacts. Define where integration/performance/recovery evidence will live.

**Acceptance/evidence:** a deliberately failing fixture fails the appropriate job; zero selected tests cannot be recorded as readiness; reruns do not accept stale output. Desktop tests actually launch Electron. Test data is isolated from personal civilizations and external paid providers.

### WP-004 — Early native packaging and platform feasibility probe

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** QA + DESK. **Size:** M. **Depends:** WP-002, WP-003. **Sources:** T §§2, 13.3, 15.

- Package a minimal Python handshake executable with PyInstaller, place it outside ASAR through Forge resources, and launch by resolved absolute path. Probe paths containing spaces/non-ASCII characters and development versus packaged resolution.
- Execute native probes on Windows x64, macOS arm64/x64, and Linux x64; determine minimum supported OS versions, runner availability, executable permissions, signing/notarization needs, and secure-key backend behavior.
- Record unsupported/missing runners or signing prerequisites with owners and lead time. A Linux cloud run cannot certify the other targets. Retain the probe as a packaging smoke fixture for WP-054.

**Acceptance/evidence:** per-target result distinguishes launch success, failure, and unrun; packaged engine does not require user Python. Remaining platform prerequisites have concrete resolutions and block the relevant release claim. This probe certifies process/bundle feasibility, not application functionality.

### WP-005 — Versioned contracts, schema generation, and compatibility rules

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG + TL. **Size:** M. **Depends:** WP-002, WP-003. **Sources:** T §§4, 6, 9–11, 13.4.

- Start with the small WP-005-wire producer/consumer contract and positive/negative fixtures, validated under the package's recorded route and merged before the consumer starts. Grow boundary by boundary; record affected consumers, compatibility window, migration/rejection behavior and adapter retirement. Test supported old/new combinations. Define Pydantic request/result/error envelopes, world and mechanism DTOs, identities, coverage/findings, pagination/progress/cancellation, preview/apply, and assistant-context types. Separate schema/application/catalog/model/numeric-runtime/protocol versions.
- Generate JSON Schema, TypeScript types and tool-input schemas from Python contracts; validate both inbound and outbound messages at main. Specify version negotiation and additive/breaking change policy.
- Commit positive/negative wire fixtures including decimal strings, unknown result versus zero, model unavailable, stale revision, malformed data, and a structurally valid but insufficient design.

**Acceptance/evidence:** `contracts:check` detects drift; TS/Python fixtures round-trip without type or numeric loss; unsupported versions fail with a stable code. Valid incomplete/infeasible evaluations remain successful results with findings, rather than transport errors.

### WP-006 — Quantity, unit, time-base, and canonical numeric contract

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG; review expertise MODEL. **Size:** M. **Depends:** WP-005. **Sources:** T §§7.1, 7.4–7.5; D §§5, 9.

- Implement decimal-string inputs, local 28-significant-digit Decimal contexts with round-half-even, stored precision versus display rounding, and canonical decimal encoding. Reject NaN, Infinity and binary-float authority.
- Build extensible dimensions, conversions, stocks/flows/capacity/count/time/entitlement definitions, per-capita denominators and scope/time conversions. Treat monetary access separately from physical conversion.
- Specify validation errors and immutable numeric runtime identity. Add independent fixtures for yields, loss, day/year factors, zero/invalid denominators, nonrepresentable or incompatible conversions, and precision boundaries.

**Acceptance/evidence:** equivalent valid units produce canonical equivalent quantities; incompatible or unknown units fail; cross-language formatting never changes authoritative values. Independent calculations verify time factors, denominator populations and rounding; global Decimal context mutation cannot leak between evaluations.

### WP-007 — Canonical world, scopes, membership, and state ownership

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG. **Size:** L. **Depends:** WP-005, WP-006. **Sources:** D §§3–5; T §§4–5.

- Implement stable identities for civilization, scopes, locations, cohorts, household/community arrangements, institutions, assets/networks, accounts, external interfaces, decisions and events; establish owned state partitions.
- Represent containment, geography, weighted/partitioned membership, jurisdiction, ownership, obligation, access, connectivity and source relationships independently. Validate containment acyclicity while permitting appropriate jurisdiction/network cycles.
- Provide entity/scope queries and change validation; declare whether population is fixed input, dynamic state, or a solved capacity bound. External interfaces carry finite capacity, terms, timing, and response assumptions.

**Acceptance/evidence:** watershed/political-region overlap and a cross-settlement care network refer to single underlying stocks/cohorts; aggregation does not duplicate them. A goal cannot mutate conditions/state; invalid membership/identity fails structurally. Two domains cannot independently own/spend the same asset capacity.

### WP-008 — Pack, source, evidence, and model identity contracts

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** MODEL + ENG. **Size:** M. **Depends:** WP-005, WP-006. **Sources:** D §12; T §§5–6, 18.

- Define pack manifests, compatibility/dependency resolution, file digests, catalogs, mechanism references, parameter/measurement declarations and source archives. Separate app/schema/catalog/model/numeric identities.
- Define namespaced game IDs and citation-only source decision IDs; preserve compound questions, full alternatives, source commit, section, excerpt digest, license, adopted/superseded status and amendments.
- Implement separate origin, modeling coverage and evidence axes; `SourceRef` and `AssumptionRef` with uncertainty, scope, rationale and validity limits. Bound data-only imports and declarations; do not execute content.

**Acceptance/evidence:** digest/source/license tampering, incompatible packs, duplicate IDs and missing references are detected. Historical adoption never defaults a fresh player's answer or implies numerical coverage. A qualitative or hypothetical definition can load with honest status but cannot masquerade as a validated numerical rule.

### WP-009 — SQLite bootstrap, repositories, and backup foundation

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG. **Size:** M. **Depends:** WP-007, WP-008. **Sources:** T §11.1, §14.

- Build Python-only persistence, application user-data database selection, foreign keys, WAL, explicit transaction boundaries and durable user commits. Electron will enforce one application instance per data directory.
- Establish migrations/version tables and storage for civilizations, scopes/entities, immutable pack/model archives, revision inputs and branches. Reserve extensions for experiment/assistant/measurement data without unversioned schema edits.
- Implement SQLite backup API integration and controlled temporary test databases. Derived evaluation caches must be independently discardable.

**Acceptance/evidence:** invalid foreign keys roll back; failed transaction leaves the old valid state; backup reopens consistently and preserves identities. Two application instances cannot write the same data directory; cached-result deletion does not delete choices or archived evidence.

### WP-010 — Engine stdio transport and process lifecycle

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG + DESK. **Size:** M. **Depends:** WP-005, WP-009. **Sources:** T §§2, 10.1, 14.

- Define WP-010-producer and WP-010-consumer before execution against the same merged WP-005-wire fixtures; allocate each package independently at its start. Integrate the real handshake early while storage work continues; final acceptance still needs WP-009. Implement versioned UTF-8 JSON Lines request/response routing, request correlation, stable errors, operation progress, cancellation, health, handshake and bounded shutdown. Reserve stdout exclusively for protocol; redact diagnostics on stderr.
- Enforce the 1 MiB message limit and paginated/chunked large responses. Handle partial reads, malformed lines, unexpected child exit, write backpressure and mismatched versions without hanging callers.
- Main launches one child by absolute path without shell, supplies only needed environment, waits for handshake before edits, and rejects pending calls on failure. Define reconnect to last confirmed state; commit uncertainty is resolved in WP-018.

**Acceptance/evidence:** fragmented/batched lines, oversize input, crash, protocol mismatch, timeout and cancellation each produce a bounded documented outcome. Shutdown leaves no orphan child. No logs or malformed child output can be mistaken for a result.

### WP-011 — Secure main/preload API and desktop boundaries

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** DESK; review expertise TL/QA. **Size:** M. **Depends:** WP-005, WP-010. **Sources:** T §§2, 10.2, 14.

- Configure `nodeIntegration: false`, `contextIsolation: true`, `sandbox: true`, restrictive CSP, blocked arbitrary navigation/windows, sanitized Markdown/source/AI rendering, and validated system-browser source links.
- Expose named, typed preload methods/events for allowed service groups; validate renderer input and engine output in main. Keep filesystem dialogs and paths, process APIs, databases and provider requests out of renderer authority.
- Enforce one-instance/data-directory behavior and error views for handshake/crash/mismatch. Deny arbitrary operation-string forwarding, SQL, shell, filesystem reads and authenticated URL fetches.

**Acceptance/evidence:** renderer/adversarial content cannot obtain Node APIs or bypass method validation; a forged/malformed message is rejected before side effects. Desktop starts and reconnects with readable last-known state, and model/protocol mismatches disable edits visibly.

## B. Shared engine and offline choice loop — M2

### WP-012 — Mechanism registry and bounded declarative composition

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG + MODEL. **Size:** L. **Depends:** WP-006, WP-007, WP-008. **Sources:** T §§5–6; D §§4–5, 12.

- Implement the module registration contract: stable/versioned mechanisms, typed ports, scopes, owned state, preconditions, claims, policy composition, traces, diagnostics and validation fixtures.
- Support trusted reviewed Python mechanisms and bounded declarative graphs of registered operators. Validate units, graph size/depth and allowed operations; no `eval`, generated code or imported executable plugins.
- Define explicit static/transition support and missing-input propagation. Unsupported proposed mechanisms remain stored qualitative drafts, with no numerical activation until evidence and independent fixtures are reviewed.

**Acceptance/evidence:** two synthetic domains register and exchange typed references without direct cross-module writes. Bad operators/units, execution payloads and undeclared state mutations are rejected. A structurally valid definition without model evidence is not automatically approved scientifically.

### WP-013 — Scoped policy composition and institutional conflict resolution

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG + MODEL. **Size:** M. **Depends:** WP-007, WP-012. **Sources:** D §§3.1, 5.3; T §§4.2, 7.2–7.3.

- Implement mechanism-declared exclusive, composable, floor/ceiling and delegated policy semantics. Resolve applicability against entities, membership sets, jurisdiction and scope classes.
- Represent authority/parameter conflict and unresolved allocation precedence as typed findings, separate from numerical SCCs and documentary edges. A registered resolution rule must identify authority and scope.
- Provide inspectable conflict participants, affected accounts/choices, sources and missing resolution requirements; do not impose local-wins, file-order, alphabetical or ideology-based precedence.

**Acceptance/evidence:** overlapping local/regional policies and competing institutions produce explicit unresolved findings until a chosen rule resolves them. Reordering inputs changes no political outcome. Independent unconflicted results remain available.

### WP-014 — Numerical dependency compiler and declared solver components

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG; review expertise MODEL. **Size:** L. **Depends:** WP-006, WP-012, WP-013, WP-015. **Sources:** T §§7.2–7.3, 15–16.

- Compile active mechanism instances/typed ports; distinguish numerical, institutional and documentary graphs. Use stable topological order for acyclic numerical components and classify strongly connected components.
- Implement explicit finite-allocation solver integration, deterministic Decimal linear elimination, and bounded iterative solver contracts with starting state, update order, criterion, tolerance and iteration limit.
- Handle singular/inconsistent systems, missing solver, nonconvergence and budget exhaustion with explicit scoped status. Supply independent coupled fixtures and convergence/nonconvergence examples.

**Acceptance/evidence:** chain, diamond and cyclic graphs produce independently derived outputs or honest unresolved/solver-failure statuses; no silent single pass replaces an equilibrium. Graph ordering is deterministic; nonnumerical cycles never invoke a numerical solver solely because they cycle.

### WP-015 — Shared accounts, finite allocation, access and budgets

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG + MODEL. **Size:** L. **Depends:** WP-006, WP-007, WP-012, WP-013. **Sources:** D §§5.1–5.4; T §§5, 7.4.

- Implement stock/flow/capacity accounts with supplies, claims, reservations, transformations, actual allocation, unmet demand, losses, imports/exports and subtotal membership. Deduct a reservation once; distinguish export from domestic use.
- Allocate finite resources, labor/time, services and throughput only through declared procedures. Keep physical presence separate from rights/entitlements/access and required funding. Unspecified precedence stays unresolved.
- Validate conservation and model-specific invariants; expose local/group distributions, unmet requests and unreachable surplus. Do not hide negative stocks by clamping or assume all social/monetary quantities share a physical conservation law.

**Acceptance/evidence:** independent fixtures cover shared labor contention, overlapping claims, losses/residual products, stock conservation, finite imports, and food existing without household access. Actual allocations never exceed available capacity; insufficiency remains playable and traceable.

### WP-016 — Pure evaluation orchestration, identity and safe caching

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG. **Size:** L. **Depends:** WP-008, WP-013, WP-014, WP-015. **Sources:** T §§7.3–7.5, 15.

- Implement pure `evaluate(world, design, assumptions, model_identity)` with structure validation, mechanism/policy resolution, graph/solver execution, accounts, distributions, coverage and typed results.
- Keep computation free of database/network/provider/wall-clock calls and hidden randomness. Canonicalize decimals, unordered collections and semantic order; exclude request IDs/timestamps from identity.
- Compute complete input/model/realization/output digests and cache keys. Continue independent components when others lack inputs or fail; never reuse results because visible indicators happen to match.

**Acceptance/evidence:** repeated equal canonical inputs give equal results/digests; changed meaningful input/model produces the appropriate changed identity. Injected I/O/randomness is detected in pure evaluation tests. Structural invalidity errors differ from successful insufficient results and dependent missing/failed coverage.

### WP-017 — Measurements, goal isolation, findings, and trace services

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG + MODEL. **Size:** L. **Depends:** WP-016. **Sources:** D §9; T §9.

- Implement indicator definitions with formula/procedure, units, scope/aggregation/time basis, thresholds/provenance and explicit interpretation. Preserve `known`, `partial`, `missing_input`, `unmodeled`, `conflict`, `solver_failure`, `not_applicable`.
- Build typed physical shortage, policy breach, institutional gap, uncertainty and target observations. Narrative or structured goals default empty and are evaluated after authoritative world computation; no score or ranking.
- Produce pageable trace DAGs with mechanism/version, typed inputs/results/dependencies, scope/time and source/assumption references; supply authored explanation templates separately from AI prose.

**Acceptance/evidence:** every numerical fixture output has a traversable trace; unknown and zero differ; a target edit leaves physical results/allocations unchanged. Missing coverage cannot turn green as whole-system sufficient; warning thresholds and neutral metrics follow named definitions rather than a global margin.

### WP-018 — Immutable revisions, pure preview, transactional apply and recovery

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG. **Size:** L. **Depends:** WP-009, WP-010, WP-016, WP-017. **Sources:** T §§10.3, 11.1, 14; D §§6–7, 13.

- Publish the preview/apply/history contract child for the desktop consumer before completing the production service; separately derived stale/idempotency fixtures validated under the recorded package route are mandatory. Build candidate reconstruction from immutable base + complete typed changes; return candidate identity, affected scopes/differences/findings/traces without committing or advancing branch heads.
- Apply validates base revision, current head, full payload and digest, then persists revision/event/results and head movement in one transaction. Operation IDs provide replayable outcomes for uncertain IPC responses.
- Implement history list, branch rename/fork, undo/redo, preserving old futures after editing an undone head. Archive offered alternatives/rationale and model identity with decisions.

**Acceptance/evidence:** preview leaves committed history/head untouched; stale or tampered apply cannot commit; duplicate operation IDs create one decision; crash after commit/before reply recovers the confirmed result. Undo/edit retains both futures and all original alternatives; no automatic history deletion.

### WP-019 — Independent headless vertical-slice verification

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** QA + ENG + MODEL. **Size:** M. **Depends:** WP-018. **Sources:** D §§2–7, 13, 15; T §§7–11, 16.

- Assemble the roadmap's labeled synthetic world through public engine services: two locations, overlapping scopes, finite stock/labor, an institution/access rule, a quantitative alternative and an unsupported qualitative alternative.
- Exercise create/query/evaluate/preview/apply/trace/undo/fork/compare inputs/reopen, including missing data, insufficiency, conflicts, stale candidate and lost reply. Derive stock/time/allocation expectations independently of the implementation.
- Capture repeatable result digests, current-run counts, preliminary performance measurements and evidence for scope/goal isolation. This fixture is test content, not the default civic setup.

**Acceptance/evidence:** derive expected accounts separately from implementation and validate them through the declared agent-review or SV route. Record the owner/controller, candidate, derivation, inspection and any deferred review; correct defects before acceptance; the integrated service workflow passes without renderer or provider access; independently derived accounts and preserved histories match persisted/reopened data. The suite fails if conservation, stale checking, goal isolation or shared-state identity is deliberately broken. Performance findings inform DEC-06 rather than replace functional acceptance.

### WP-020 — Synchronized shell, creation flow and navigation

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** DESK; review expertise PRODUCT. **Size:** M. **Depends:** WP-011, WP-018. **Sources:** D §§6, 8; T §12.

- Start the shell/creation consumer against the merged context/preview contract while the WP-018 production service is pending; fixtures stay confined to development/tests and cannot satisfy WP-024. Build navigation rail, central workspace, optional inspector and the selected civilization/branch/revision-or-checkpoint/scope/model context. Use TanStack Query with complete context-keyed queries and local React state for transient filters/cards.
- Add create/open, named editable starting conditions, explicit reference-setup selection, and optional purpose entry. Ordinary creation starts with empty goals and unanswered civic choices.
- Implement accessible scope selection and state labels; invalidate/cancel appropriate queries on branch or scope changes and keep older results visibly attached to their original state.

**Acceptance/evidence:** changing branches/scopes cannot display stale results as current; no view maintains its own authoritative civilization. A new sandbox has no injected policies/goals; navigation permits entry through every registered domain regardless of unanswered dependencies.

### WP-021 — Interviews, alternatives, parameter editing and preview/apply UI

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** DESK + PRODUCT. **Size:** L. **Depends:** WP-017, WP-018, WP-020. **Sources:** D §§6–7; T §§6.2, 10.3, 12.

- Render one substantive prose problem at a time, usually three/four readable option cards, original wording/source, benefits/costs/mechanism, scope, origin/evidence/coverage, clarification and deferral. Support real quantitative questions with typed controls.
- Connect card/parameter/condition edits to noncommitting preview with affected accounts/scopes, dependencies, findings and alternatives. Only a distinct player Apply action commits; handle stale candidate, unsaved state and retryable read failures visibly.
- Support templates, player variants and qualitative proposals through the shared content/preview pipeline. Unknown mechanisms show gaps; no fabricated numeric effect or forced answer sequence.

**Acceptance/evidence:** keyboard-only select → inspect → preview → cancel changes no history; Apply records rationale/full alternatives and one revision. Stale apply refreshes safely; unsupported proposals remain inspectable without executing prose/code; deferring does not block unrelated inquiry.

### WP-022 — Overview, diagnostic indicators, distributions and trace inspectors

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** DESK + MODEL. **Size:** L. **Depends:** WP-017, WP-020, WP-021. **Sources:** D §§5, 8–9; T §§9, 12.

- Build a configurable small indicator set and neutral observations using Recharts plus accessible HTML tables. Show units, scope/time, interpretation, coverage, status text and named diagnostic thresholds.
- Implement green/orange/red/gray semantics with distinct text for unknown/conflict/inapplicable/etc.; separate player targets/selected policy commitments from engine diagnostics. Do not imply global sufficiency from partial results.
- Provide shared account/definition/input/calculation/source/assumption inspectors with pageable trace navigation, group/local distributions and exclusions. Separate Python traces, model rationale and optional AI explanations.

**Acceptance/evidence:** every displayed authoritative quantity opens its corresponding definition/trace; a local unreachable shortage remains visible beside aggregate surplus. All result statuses render distinctly without color dependence; no target edit changes arithmetic or introduces a score.

### WP-023 — History, undo/fork and compatible design comparisons

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG + DESK. **Size:** M. **Depends:** WP-018, WP-020, WP-022. **Sources:** D §§6.3–6.4, 13; T §§11–12.

- Expose revision lineage, offered alternatives/rationale, rename/fork/restore, undo/redo and retained old futures. Clearly identify branch heads versus inspected historical revisions.
- Implement Python comparison services that align quantities by dimensions, scope, aggregation, time basis and model semantics; show changed choices/assumptions alongside differences.
- Preserve missing/incompatible outcomes as labeled noncomparisons, never zeros or winners. Establish comparison DTOs reusable by timeline and assistant tools.

**Acceptance/evidence:** edit after undo retains both descendants; restart preserves lineage and context. Compatible comparisons match independent deltas; incompatible scope/unit/model fixtures explain why subtraction is unavailable. No branch gets an implicit rank.

### WP-024 — Integrated offline design milestone

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** QA + PRODUCT; review expertise TL + MODEL. **Size:** M. **Depends:** WP-019, WP-021, WP-022, WP-023. **Sources:** D §§2, 6–10, 13–15; T §16.

- Automate and manually inspect the complete Electron workflow using temporary user data: create, choose conditions, enter a domain, compare options, preview, apply, inspect consequences/source, fork, compare and reopen.
- Run with provider networking unavailable and no key; check missing/partial/shortage/conflict states and engine restart. Verify all core paths by keyboard and text/status equivalents.
- Produce M2 evidence with engine/desktop counts, independent expected numbers, saved identities and known exclusions. Confirm that mocked UI data has not replaced the actual child engine/database.

**Acceptance/evidence:** M2 exit in the roadmap is demonstrated end to end offline; the UI, actual engine and reopened SQLite agree. Outstanding failures are diagnosed and assigned; a working demo cannot waive numerical/history defects.

## C. Content and all-domain design integration — M3

### WP-025 — Society corpus inventory and provenance-preserving importer

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** MODEL; review expertise PRODUCT + ENG. **Size:** L. **Depends:** WP-008. **Sources:** D §§4, 12; T §§6, 18.

- Inspect the actual `playa77/society` corpus at the specification's reference commit `9ff539997dbd1bd3fa99deabcf6bc5907602df60`; inventory all twelve domains and actual three-level branches, ledger decisions, integration documents, source essay and licenses. Record revision availability and redistribution permission; never infer unseen branch content.
- Implement a deterministic import/transformation process into game catalog/source records with namespaced IDs, compound question handling, original alternatives, adopted/superseded lineage and excerpt digests. Classify document-maintenance decisions as provenance.
- Review amendments and disputed arithmetic independently. Separate imported design content, evidence claims, model candidates and optional reference civilization choices; importing the source cannot select policies in a fresh sandbox.

**Acceptance/evidence:** every source domain/branch and imported decision is accounted for in an inventory report; rerun on identical inputs produces identical outputs; later supersession wins only through explicit links. If source access/license is unavailable, synthetic framework work proceeds while source-derived release content remains blocked and labeled.

### WP-026 — Content build, validation, reviewed model activation and setups

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** MODEL + ENG. **Size:** L. **Depends:** WP-012, WP-017, WP-025. **Sources:** D §§7, 12, 14; T §§5–6, 16.

- Implement `content:validate` for manifest/reference/hash/license/coverage/units integrity and `contracts:check` integration. Package immutable catalog/model/evidence artifacts and approved source archives.
- Maintain a mechanism review record: operational definition, formula/procedure, denominator/time/scope, empirical versus hypothetical basis, uncertainty, independent expected fixtures, invariants, validity limits and unsupported extrapolation. A validator passing is not scientific approval.
- Author shared interview/template conventions, a neutral editable conditions setup, optional explicitly selected historical/reference setups, and inquiry prompts. Build branch-level coverage reports; missing source/model detail is explicit work rather than invented content.

**Acceptance/evidence:** invalid references, bad digests, absent attribution and unsupported numerical activation fail validation; every activated rule links to reviewed evidence/fixtures. A new blank sandbox selects neither reference policies nor goals. Rebuilt packs retain stable identities when unchanged.

### WP-027 — Domain conformance harness and interface ownership registry

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG + QA + MODEL. **Size:** M. **Depends:** WP-019, WP-026. **Sources:** D §§4–5, 15; T §§5, 16.

- Publish WP-027-contract from the module and pack interface children before waiting for the complete importer/content build. Domain authors may start against it; WP-027 acceptance still requires WP-019/026 and real conformance. Publish shared domain fixtures, ownership registry and interface catalog for account/resource/asset/population/institution references, typed ports, claims, coverage and trace expectations.
- Build parameterized conformance tests for registration, supported scopes, invalid inputs, shared finite capacity, state ownership, provenance, conflict handling and pure evaluation. Add transition hook fixtures to be extended by WP-034.
- Define paired-domain integration contracts and a branch coverage template; designate integration owners. Stubs must preserve authoritative IDs and expose unavailable behavior, not fabricate capacities or effects.

**Acceptance/evidence:** a conforming synthetic module passes and deliberate double-write/double-spend/invalid-unit modules fail. Every DOM package can start against stable shared fixtures; counterpart acceptance dependencies and unresolved ownership are visible. Domain-specific engines/databases are rejected by review.

### WP-028 — Decision atlas and full question/alternative search

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** DESK + ENG. **Size:** M. **Depends:** WP-020, WP-021, WP-026, WP-027. **Sources:** D §§8, 10; T §§10.2, 12.

- Implement paginated/filterable atlas queries across all domains/branches, scope, source, selection/unanswered status, modeling/evidence coverage and open issues. Include complete option sets, original wording, supersession and proposed commitments.
- Link results to interview/preview, history, source and model gap. Distinguish a historical adopted source option from the player's current choice.
- Preserve filters/context without creating authoritative state in renderer; support keyboard traversal and accessible result counts/loading/empty states.

**Acceptance/evidence:** queries retrieve selected and unanswered alternatives with correct filters and pagination; source-maintenance records do not become civic questions. Opening an item preserves revision/scope and presents all archived alternatives even after a catalog update.

### WP-029 — Sparse domain/decision/scope matrices and relationship drill-down

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG + DESK. **Size:** L. **Depends:** WP-017, WP-023, WP-027, WP-028. **Sources:** D §10; T §§7.2, 12, 15.

- Aggregate sparse typed relationships in Python by domain, branch, decision, scope or selected alternatives; support requires/supplies/competes/conflicts/influences/supersedes with explicit row-to-column direction.
- Keep relationship count, numerical magnitude, coverage and activation separate. Differentiate documentary/historical supersession from active causal/solver dependencies; explain that blank means no recorded relationship.
- Build virtualized drill-down and accessible lists leading to choices, mechanism/rule, affected account, source and current condition. Do not enumerate the full Cartesian product of possible civilizations.

**Acceptance/evidence:** asymmetric and mixed-type cells display correct direction/type; filtering does not fabricate independence or causality. Drill-down reaches the same account/trace as the interview; all list actions are keyboard-equivalent and large sparse fixtures stay bounded.

### WP-030 — World, institutions, topology and distribution exploration

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** DESK + ENG + MODEL. **Size:** M. **Depends:** WP-007, WP-022, WP-027, WP-029. **Sources:** D §§3, 5, 8; T §§4, 12.

- Present locations, cohorts/groups, households/communities, assets/networks, jurisdictions and actor obligations with scope-specific access/capacity and links to decisions/accounts.
- Show geography, membership and authority as separate projections of the canonical entity/edge store. Provide list/table inspection for overlaps and networks; no required terrain simulation or individual agents.
- Keep layout randomness separate/seeded and excluded from simulation identity. Expose local variation and unreachable surpluses alongside civilization aggregates.

**Acceptance/evidence:** editing a shared asset/obligation appears consistently in domain, matrix and world views; overlapping jurisdiction is representable without cloning entities. Diagram layout changes cannot alter simulation inputs/results; tables reveal the same relationships.

### WP-031 — Evidence/models workspace, assumptions, goals and notes

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** DESK + ENG + MODEL. **Size:** M. **Depends:** WP-017, WP-021, WP-023, WP-026. **Sources:** D §§9, 12–14; T §§6, 9, 10.2.

- Build source/excerpt, mechanism/formula, evidence/coverage and assumption inspectors; show origin, revisions, licenses, amendments, uncertainty and unsupported extrapolation independently.
- Support parameter/assumption preview through normal revision flow and model-gap/proposal records. Inspect archived historical definitions without silently switching to current models.
- Implement narrative inquiry, expectation/observation notes and typed targets through scoped preview/apply/query methods. Store private-note classification for export/context consent; goals remain empty by default.

**Acceptance/evidence:** a player can follow a result to its input/assumption/source, edit a supported assumption and compare branches. Goal edits leave physics unchanged; historical evidence is still readable after source/model updates; qualitative records cannot silently activate arithmetic.

### WP-032 — Twelve-domain static integration and coverage gate

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** TL + QA + MODEL + PRODUCT. **Size:** L. **Depends:** WP-024, WP-028, WP-029, WP-030, WP-031; static deliverables of DOM-01–DOM-12. **Sources:** D §§4–5, 15; T §§5, 16.

- Assemble the education relationship path from D §5.7 as a synthetic all-domain integration fixture: shared people/time/assets, provision, access, authority, rights, care, health needs, information, environment, identity accommodation and continuity requirements.
- Also exercise an entry choice originating in each domain, including institutional/cultural procedures, ensuring that no domain only decorates another domain's resource arithmetic. Record numerical, procedural, qualitative and missing effects separately.
- Audit every source branch, question coverage inventory and module interface. Review observed couplings and limits; verify cross-view context, canonical IDs and provenance with the actual engine/database.

**Acceptance/evidence:** all twelve static modules pass the conformance harness and counterpart checks; the shared education fixture exposes independent shortages, rights/access issues and unresolved gaps without double-counting or assigning a score. Every source branch is represented/classified; absent implementation is labeled, never implied complete by catalog presence. M3 evidence leaves domain transition work explicitly open for M4.

## D. Time, experiments and uncertainty — M4

### WP-033 — Calendar, multirate scheduling and effective changes

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG + MODEL. **Size:** M. **Depends:** WP-006, WP-012, WP-018. **Sources:** D §§6.2–6.3; T §8.

- Define integer simulation-day boundaries, calendar convention and rate conversions; declare mechanism update intervals and deterministic same-boundary event precedence.
- Schedule approved revisions and player-authored/external events with effective time, preconditions, origin and affected scope. Separate counterfactual design edits, retrospective forks and future policy adoption.
- Advance through every required daily/weekly/seasonal/annual boundary; permit exact aggregate transitions only with defined applicability/equivalence fixtures.

**Acceptance/evidence:** year-view fast-forward still records an intermediate daily shortage; same-boundary events replay identically. A future policy does not alter past states; unsupported adoption delay/transition stays a coverage gap rather than an instant effect.

### WP-034 — Atomic transition reduction and shared dynamic invariants

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG + MODEL. **Size:** L. **Depends:** WP-015, WP-016, WP-027, WP-033. **Sources:** D §§5–6; T §§5, 8.

- Implement boundary processing: due events, active mechanism resolution, proposed transitions/demands, finite-capacity/conflict resolution, combined in-memory commit, invariant checks and traces/closing state.
- Extend the domain harness for construction/maintenance, education/skills, service queues, population/health where selected, ecological change, institutional procedures and response capacities. State ownership and shared accounting apply across all proposed transitions.
- Add cancellable chunks, progress and runtime quotas. Cancellation, solver failure or invalid proposal cannot persist half a boundary; independent supported outputs remain inspectable.

**Acceptance/evidence:** simultaneous domains cannot spend the same labor/stock twice; before/after conservation and model-specific invariants pass independently derived fixtures. Cancellation resumes from a confirmed boundary; missing transition behavior is explicit. Domain transition portions are tested against their accepted counterparts.

### WP-035 — Reproducible stochastic events and random-stream identity

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG; review expertise MODEL + QA. **Size:** M. **Depends:** WP-016, WP-033, WP-034. **Sources:** T §7.5, §8; D §§6.2, 13.

- Specify/version deterministic RNG contract and isolated streams keyed by experiment seed, mechanism, scope and event index; pass streams explicitly to stochastic mechanisms.
- Store distributions, sampling definitions, runtime identity and realized draws/events. Keep source ranges as ranges until a declared probability distribution is selected; exclude AI generation and diagram layout randomness.
- Provide deterministic/no-hazard, authored-event and stochastic test paths with known realization fixtures and native cross-platform verification hooks.

**Acceptance/evidence:** replay reproduces realizations/results; enabling an unrelated module cannot shift another module's random sequence. A source interval is never sampled without a declared model, and a changed RNG/runtime identity cannot be advertised as exact historical reproduction.

### WP-036 — Experiment persistence, checkpoints, pause/replay and timeline forks

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG. **Size:** L. **Depends:** WP-018, WP-034, WP-035. **Sources:** D §§6, 13; T §§8, 11.1.

- Store immutable opening state/model/assumptions, approved schedules, random identity/realizations, ordered events and checkpoints. Persist confirmed boundary results with restart-safe operation semantics.
- Implement create/fork/advance/pause/cancel/replay/query service operations and checkpoint intervals; combine checkpoints with intervening events without losing explanation history.
- Fork at a past simulation state without rewriting the old run; retain distinction from design counterfactuals. Validate replay identities and report unavailable historical runtime rather than silently using a newer engine.

**Acceptance/evidence:** continuous run, checkpoint-resume and recorded-event replay yield equivalent canonical state/results under the same runtime. Crash/cancel/reopen loses no confirmed transition; retrospective edits preserve the original experiment; no wall-clock dependency enters simulation state.

### WP-037 — Timeline, event scheduling, experiment comparison and presentation

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** DESK + ENG + PRODUCT. **Size:** M. **Depends:** WP-023, WP-030, WP-036. **Sources:** D §§6, 8, 13; T §§8, 12.

- Add timeline workspace with effective policy schedule, event origin, opening/current checkpoint, progress/pause/cancel, event consequences/traces, and past-state fork controls.
- Render time series and distributions with accessible tables, distinguishing a displayed time range from executed boundaries. Label unsupported dynamic models and selected stochastic assumptions.
- Extend engine comparability to experiment opening conditions, policies, schedules, realizations, scopes and time/model semantics. Show changed choices/assumptions and local/group differences without ranking.

**Acceptance/evidence:** scheduling a future policy and forking a past state have visibly different histories and results. Cancel cannot display an uncommitted boundary as saved. Comparison explains incompatible clocks/models and never substitutes zero for missing outcomes.

### WP-038 — Uncertainty, sensitivity and optional capacity-bound solving

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG + MODEL; review expertise PRODUCT. **Size:** L. **Depends:** WP-014, WP-017, WP-023, WP-036. **Sources:** T §§7.2, 7.5, 9; D §§3.2, 6, 12.

- Implement explicit point/range/distribution parameter semantics, enumerated sensitivity variants, and supported uncertainty propagation/diagnostic overlap. Record methods and coverage rather than implying all uncertainty is probabilistic.
- Surface comparative assumptions and uncertain thresholds in inspectors/reports. Reject range-to-midpoint and range-to-distribution conversions without an explicit player/model choice.
- Add the optional registered capacity-bound calculation with a named solved variable, fixed inputs, monotone constraints, feasibility boundaries, stopping criterion and independent fixtures. Population cannot simultaneously be fixed, evolved and solved.

**Acceptance/evidence:** independent bounded examples produce expected feasible/infeasible limits and range-aware findings; unsupported propagation is labeled. Changing a player target cannot invoke an optimizer or alter the bound's declared physical constraints; stochastic sampling requires a defined distribution and stream.

## E. Portability, reports and recovery — M5

### WP-039 — Versioned portable archives and transactional safe import/export

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG + DESK; review expertise QA/security. **Size:** L. **Depends:** WP-008, WP-018, WP-026, WP-036. **Sources:** D §§13–14; T §11.2, §14.

- Define separate archive format/validation and dialogs/privacy UI packages before execution, with approved fixtures before either consumer implementation; experiment histories may be fixtures until WP-036 is real. Define archive manifest/version with inputs, original choices/alternatives, branch lineage, experiments/events/realizations, assumptions, model/catalog/runtime identities, sources and optional cached results. Include data only; exclude all keys/encrypted-key blobs.
- Validate schemas, compatible references/mechanisms, digests, paths, entry types, duplicates and decompression/file-size/count budgets before one import transaction. Reject traversal, symlinks, executable content and arbitrary formulas.
- Use main-owned file dialogs and explicit include/exclude choices for transcripts, private notes and attachment material, excluded by default. Prepare/export large data in bounded chunks; do not squeeze archives into one IPC message.

**Acceptance/evidence:** offline export/import into a new user-data directory preserves designs, forks, experiments and source identities; corrupted/hostile archives leave no partial civilization. Privacy fixtures prove prohibited key material is always absent and optional private content appears only when selected.

### WP-040 — Markdown inquiry reports and typed CSV exports

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG + DESK + PRODUCT. **Size:** M. **Depends:** WP-022, WP-031, WP-037, WP-039. **Sources:** D §§6.4, 14; T §11.2.

- Generate explanatory Markdown with inquiry/expectation/observation, choices and alternatives, outcomes/findings, traces, sources, assumptions, model versions and unresolved coverage; keep generated explanation explicitly labeled if included.
- Export scoped measurements/distributions/time series as CSV with units, time basis, denominator, coverage and identities. Handle escaping and spreadsheet formula-injection concerns for untrusted text without changing authoritative quantities.
- Reuse export privacy controls; provide offline progress/failure handling and never insert keys, unrelated private notes or transcripts implicitly.

**Acceptance/evidence:** report/CSV quantities match Python results and comparability semantics; missing/unmodeled values are labeled rather than zero. A recipient can distinguish hypothesis, calculation, historical source and optional AI explanation; text/CSV escaping round-trips safely.

### WP-041 — Schema/model migrations, historical mode and recovery workflows

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG + DESK + QA. **Size:** L. **Depends:** WP-009, WP-018, WP-036, WP-039. **Sources:** D §13; T §§11, 14.

- Complete migration backups using SQLite's backup API, schema compatibility checks, interrupted-migration handling and restore guidance. Model changes create explicit new migration/comparison branches, never rewrite historical results.
- Support historical read-only inspection when engine/model/protocol compatibility prevents recomputation; distinguish cached historical evidence from freshly reproduced output and disable unsafe edits visibly.
- Exercise engine restart, uncertain operation recovery, disk-full/save failures, corrupt archive versus corrupt database diagnostics, bounded shutdown and user-selected restore without automatic civilization reset.

**Acceptance/evidence:** backup/restore and failed migration preserve all confirmed history; model migration leaves the original branch/results readable. Save failure leaves preview visibly unsaved; an unavailable runtime yields honest historical inspection, never silent recomputation or data deletion.

## F. Optional assistance and full provider integration — M6

### WP-042 — Provider profiles, secure keys and main-owned networking

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** DESK; review expertise QA/security. **Size:** L. **Depends:** WP-011. **Sources:** D §11; T §§13.1, 13.3, 14.

- Store endpoint/model/routing/capability preferences separately from key references; implement temporary key entry/test/replace/remove. Transfer once to main and clear input; never return stored keys to renderer or pass them to Python.
- Use Electron safeStorage with OS protection; when unavailable or Linux reports `basic_text`, fall back to session-only memory with an explicit status, never plaintext persistence. Deleting a key removes stored material and cancels its requests.
- Perform provider HTTPS through Electron networking/system proxy behavior. Bind credentials to configured endpoint/profile, reject non-loopback plaintext endpoints, prevent authenticated cross-host redirect forwarding, and redact headers/keys from diagnostics.

**Acceptance/evidence:** protected and unavailable-backend fixtures behave correctly; profile switch/redirect cannot leak a key to another host or engine child. Removal cancels in-flight work; storage/log/archive/renderer APIs contain neither raw keys nor key blobs outside the approved store.

### WP-043 — Provider adapter contracts and live capability/catalog metadata

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** DESK. **Size:** M. **Depends:** WP-042. **Sources:** D §11; T §§13.1–13.2, 18.

- Build a dedicated OpenRouter adapter and a separate OpenAI-compatible adapter with declared capabilities. Consult current official provider documentation; record retrieval date, API/schema assumptions and fixtures rather than copying stale compatibility guesses.
- Implement OpenRouter model discovery/variants/search, model/provider capabilities, context limits/pricing, authenticated key-status/limits, refresh and timestamped cache. Preserve unknown metadata; model IDs are open strings, not a hardcoded enum.
- Represent text/image/audio/video, tools, schema output, reasoning and routing support with source/timestamp and explicit unknown states. Offline cached metadata is labeled; discovery does not imply execution suitability.

**Acceptance/evidence:** mock current/unknown/stale/removed models and metadata evolve without data loss; unsupported controls/modalities cannot be silently enabled. Key-status errors are safe and actionable. Endpoint/schema evidence and later live outcomes are tracked separately from mock coverage.

### WP-044 — Typed request builder, routing, generation controls and structured output

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** DESK; review expertise TL/QA. **Size:** L. **Depends:** WP-043. **Sources:** T §13.2, §13.5.

- Encode documented order/only/ignore, fallbacks, parameter enforcement, price/routing and supported privacy/data-retention controls. Preserve selected controls or reject explicitly; never loosen incompatible privacy preferences silently.
- Support streamed/nonstreamed generation, sampling/output controls, response formats/schema modes, reasoning controls and explicit model fallback. Validate profile/model capabilities and context limits before sending.
- Validate structured output locally; expose selected versus actual model/provider route, finish reason and unsupported-parameter errors. OpenRouter-only controls must not leak into generic compatible-provider requests.

**Acceptance/evidence:** request snapshots match current documented schemas; unsupported selected controls fail before send or show a specific provider rejection. Structured-invalid responses do not become valid proposals; fallback occurs only when configured and actual identity is reported when available.

### WP-045 — Generation, fragmented SSE, cancellation and deliberate retry

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** DESK + QA. **Size:** L. **Depends:** WP-044. **Sources:** T §§13.2, 13.5; D §11.

- Implement nonstream responses and incremental SSE across arbitrary byte/chunk boundaries, deltas, usage-only events, tool fragment indices, visible reasoning metadata, errors, end markers and finish reasons. Handle UTF-8 split boundaries and partial streams.
- Connect cancellation/abort, request identity and partial/cancelled/failed/completed states. Reject late updates to another request; keep original revision/branch context when navigation changes.
- Distinguish auth/credit/rate/model/provider/network failures with safe diagnostic action. Bounded metadata retry is allowed; generation after uncertain acceptance, output or tools requires a deliberate player retry rather than automatic paid regeneration.

**Acceptance/evidence:** fragmented/parallel tool stream fixtures assemble correctly, malformed/incomplete streams remain explicit, and cancelled output never becomes a completed answer. Branch switching cannot relabel a reply; timeout/uncertain acceptance cannot trigger duplicate paid requests automatically.

### WP-046 — Grounded context, read-only tools and proposal authority boundary

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG + DESK; review expertise QA/security. **Size:** L. **Depends:** WP-017, WP-018, WP-023, WP-031, WP-044, WP-045. **Sources:** D §§7, 11–12; T §13.4.

- Python assembles bounded manifests of relevant facts/choices/accounts/traces/sources/assumptions, pinned to civilization, revision/checkpoint, scope and task. Show the exact sharing manifest; exclude private notes, unrelated branches and attachments unless explicitly included.
- Implement schema-validated context-bound read/inspect/compare/retrieve/validate/noncommitting-preview tools. Complete fragmented calls before execution; bound rounds/call counts/context and validate every argument/reference.
- Store authored/player/AI proposal origin and coverage; route compatible mechanism/parameter proposals into the ordinary preview UI. Tool definitions must expose no apply, model edit, timeline mutation, arbitrary file/URL access, code execution or key retrieval.

**Acceptance/evidence:** prompt injection, forged revision IDs and tool arguments cannot cross the allowlist or change committed state. Read-only tools use the turn's immutable context; AI proposal becomes one player-approved ordinary apply, with its source/coverage retained. No-tool models can explain supplied context with visible limits.

### WP-047 — Modalities, attachments, reasoning and conversation compatibility

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** DESK + ENG. **Size:** L. **Depends:** WP-039, WP-043, WP-045, WP-046. **Sources:** T §§13.1–13.2, 13.4–13.5; D §11.

- Implement typed content and safe rendering/handling for provider-supported text/image/audio/video/file modalities; record attachment provenance, MIME/type, size, consent scope, retention and context/size accounting. Unsupported combinations are rejected before sharing, not discarded.
- Distinguish local parsing/excerpt extraction from provider-side file processing; remote processing requires explicit sharing. Keep returned nontext artifacts separate from simulation authority and subject to untrusted-content handling.
- Preserve provider-required opaque continuation details without inventing or interpreting them; separate visible reasoning metadata. Revalidate history compatibility on model/provider changes and start a new thread when safe translation is unavailable.

**Acceptance/evidence:** capability matrix covers each modality and supported output path; incompatible file/model/history combinations produce explicit explanations. Neither a model switch nor attachment reuse silently broadens shared context. Opaque private reasoning is not forwarded to an incompatible provider or treated as computed fact.

### WP-048 — Usage reconciliation, Decimal costs and spending controls

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG + DESK. **Size:** M. **Depends:** WP-006, WP-009, WP-043, WP-045. **Sources:** T §§13.2, 13.5; D §11.

- Store per-request catalog estimates, reported token categories (input/output/cache/reasoning where supplied), reported actual cost, generation metadata and unresolved/cancelled usage states. Retrieve generation metadata through the provider adapter where supported.
- Aggregate money in Python Decimal; later actual replaces that request's estimate instead of adding a second charge. Unknown cost remains unknown; distinguish currency/unit and estimate provenance.
- Add pre-request per-turn/session gates and visible usage controls; explain provider-side hard account limits versus local estimates and in-flight overruns. Key/profile deletion and cancellation preserve honest unresolved charge observations.

**Acceptance/evidence:** independent fixtures reconcile estimates→actual, usage-only events, missing totals, cancellation and late metadata without double charge or false zero. Budget gate blocks new requests as configured; no claim promises abort eliminates upstream cost.

### WP-049 — Assistant workspace, provider settings and transcript lifecycle

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** DESK + PRODUCT. **Size:** L. **Depends:** WP-037, WP-042, WP-046, WP-047, WP-048. **Sources:** D §§8, 11, 14; T §13.

- Build model discovery/search/selection, route/privacy/generation controls, key-status/settings and visible capability constraints. Display selected and actual identity, timestamped catalog state, safe errors and usage.
- Implement contextual interview clarification, question adaptation, dependency/source explanation, comparisons and structured alternative proposals through immutable turn context. Show context before send, stop/partial status, tool evidence and proposal preview controls.
- Store optional local transcripts/turn metadata; delete independently of civilization history. Respect report/archive inclusion controls and attachment retention. Preserve authored/offline workflows when AI is disabled, fails or has no key.

**Acceptance/evidence:** users can inspect context, choose route/model, stop a reply, inspect cost and apply an ordinary proposal without granting assistant mutation authority. Deleting transcripts preserves choices/history; changing branch leaves old replies correctly labeled. Offline authored interviews and reports remain functional.

### WP-050 — Provider compatibility matrix and bounded live validation

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** QA + DESK; review expertise TL/PRODUCT. **Size:** L. **Depends:** WP-043, WP-044, WP-045, WP-046, WP-047, WP-048, WP-049. **Sources:** T §§13, 16, 18.

- Complete deterministic mock suites for catalog/routing/privacy controls, schema modes, fragmented parallel tools, supported modalities/reasoning, continuation, metadata/costs, auth/credit/rate/provider errors, redirects/redaction and cancellation.
- Run separately authorized bounded live checks against current official OpenRouter contracts: authenticated metadata, representative stream/nonstream generation, tools, schema output, reasoning, supported modalities, routing controls, usage and cancellation. Record provider/model/version/date, cost ceiling and exact outcomes; never commit keys.
- Build a public compatibility/limitations table for each capability path and the generic compatible adapter. A catalog flag or mocked success alone cannot certify live support; distinguish supported, unsupported, failed, untested and access-blocked.

**Acceptance/evidence:** all required application-side capability paths pass mock/integration checks; live evidence supports the stated compatibility claims. Missing credentials/credits or a denied capability is recorded as a concrete external prerequisite, not quietly marked passed. A full OpenRouter claim is blocked by required unverified live behavior; offline capability remains separately demonstrable.

## G. Hardening, release evidence and distribution — M7

### WP-051 — Scale fixtures, dependency caching and responsiveness budgets

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** ENG + DESK + QA. **Size:** L. **Depends:** WP-032, WP-037, WP-038, WP-049. **Sources:** T §15; D §§8, 10.

- Execute the DEC-06 small/classroom and larger exploratory fixtures for evaluation/advance, large sparse matrices, atlas/world queries, long traces/histories, archives and assistant context. Record hardware, versions, latency distributions, peak memory and cancel responsiveness.
- Optimize measured bottlenecks through pagination, dependency-aware complete-identity caching, virtualized lists, chunking and checkpoint policy. Independent computation may parallelize only with deterministic merge and isolated state/random streams; writes/reduction remain serialized.
- Test solver/time/memory quotas and stale query cancellation. Over-budget work must return explicit status, not truncated unlabeled results; clearing caches must preserve correctness.

**Acceptance/evidence:** agreed numeric budgets are met with current-run measurements or release is blocked by a named performance issue. Warm/cold cache outputs agree; renderer remains usable while work is cancellable; optimizations preserve canonical digests and no data ownership boundary is bypassed.

### WP-052 — Accessibility, prose clarity and educational usability

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** QA + PRODUCT + DESK. **Size:** L. **Depends:** WP-024, WP-028, WP-029, WP-030, WP-031, WP-037, WP-040, WP-049. **Sources:** D §§7–11, 14–15; T §§12, 16.

- Audit keyboard/focus order/restoration, dialogs, screen-reader names/status announcements, semantic tables, contrast/zoom and noncolor meaning across every core task. Matrices, charts and network views require equivalent lists/tables.
- Run inquiry tasks with student/designer/educator perspectives: predict a consequence, choose/preview, locate a shortage, find its assumption/source, distinguish hypothesis/calculation, fork an alternative and report learning.
- Review interview language, origin/coverage labels, no forced progression, neutral diagnostics and no hidden ranking. Check that aggregate displays cannot conceal local exclusion or confuse a target with engine judgment.

**Acceptance/evidence:** every core action is keyboard-completable, graph-only information has accessible equivalents, and blocking accessibility defects are resolved. Usability evidence shows a reader can identify which state a result describes and explain its assumption/coverage without requiring AI.

### WP-053 — Threat review, privacy audit and fault-injection recovery

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** QA/security + TL. **Size:** L. **Depends:** WP-011, WP-039, WP-041, WP-042, WP-046, WP-049. **Sources:** T §§10–11, 13.3–13.5, 14, 16.

- Review renderer/preload/main/engine/provider/import trust boundaries, CSP/navigation, Markdown sanitization, bounded declarative content, endpoint credential binding and assistant allowlists. Test malicious sources/archives/attachments/prompts and forged IPC.
- Fault-inject disk full, permission loss, child crash, protocol mismatch, interrupted commit/migration/import/export, network disconnect, partial stream and forced close. Assert bounded shutdown, consistent transaction recovery and no automatic reset.
- Scan sanitized diagnostics, prompts, engine environment fixtures, reports, archives, crash handling and logs for raw/encrypted key leaks, private data over-sharing and unintended telemetry. Use synthetic canaries, never real keys as test fixtures.

**Acceptance/evidence:** no arbitrary renderer/content execution or assistant commit path; keys cannot cross prohibited boundaries. Recovery preserves last confirmed revisions/transitions, shows uncertain/unsaved states accurately and leaves provider failure isolated from civilization/history. Findings have severity, owner, fix and retest evidence.

### WP-054 — Native build, signing, installers and bundled-engine validation

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** QA + DESK + ENG. **Size:** L. **Depends:** WP-004, WP-041, WP-049, WP-053. **Sources:** T §§2, 7.5, 13.3, 15–16.

- Produce native PyInstaller/Forge packages for Windows x64, macOS arm64/x64 and Linux x64; bundle engine outside ASAR and verify native dependencies, app/engine identity, resource paths, permissions and upgrade/user-data behavior.
- Configure signing/notarization through external local/CI secrets; verify platform-specific secure-key behavior, session-only fallback, proxy networking, cancellation and recovery. Do not put signing material or secrets into artifacts/source.
- Install/run on target machines without Python/Node, execute the common numerical/replay fixtures and representative offline desktop/import/export tasks. Record signing/install outcomes and reproducibility boundary per target.

**Acceptance/evidence:** all four native target combinations run the bundled engine and pass declared invariants/replay and desktop smoke checks. Missing runner/signing/notarization is explicit and blocks the affected distribution claim. Artifact checksums and version/digest mapping are retained; packaged behavior is not inferred from development mode.

### WP-055 — Whole-product end-to-end validation and model evidence audit

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** QA + MODEL + PRODUCT; review expertise TL. **Size:** L. **Depends:** WP-032, WP-037, WP-038, WP-040, WP-041, WP-050, WP-051, WP-052, WP-053, WP-054; full DOM-01–DOM-12. **Sources:** D §15; T §16.

- Execute the verification matrix's complete integrated scenarios on the release candidate identities, with actual Python/SQLite/Electron and native smoke coverage; include all-domain static and transition effects, uncertainty, historical mode and offline/network failures.
- Audit branch/mechanism inventory, empirical/hypothetical evidence, unsupported effects, all result traces, source attributions and behavioral validity limits. Verify no source choice, target or generated number silently becomes physics/default policy.
- Assemble gate evidence with passed/failed/skipped/expected-failure/unrun counts, defect classification, model limitations, native matrix and provider compatibility outcomes. Recheck only affected suites after changes, preserving the evidence identity.

**Acceptance/evidence:** every requirement row has a current evidence link and owner; all required gates pass with no unexplained failures/unrun required checks. Coverage gaps are honestly named and match DEC-04; no trivial unit/format check substitutes for the intended functional workflow. Confirmed application defects remain separate from missing model mechanisms or external test prerequisites.

### WP-056 — Release candidate freeze, documentation and handoff

**Allocation:** record agent owner/controller, division of work and validation route at executable-package start; retain through completion. **Specialties:** TPM + QA + TL + PRODUCT. **Size:** M. **Depends:** WP-055. **Sources:** D §§14–16; T §§11, 15–18.

- Freeze exact app/schema/catalog/model/numeric/protocol versions, dependency locks, source revisions, pack digests, artifact checksums and compatibility tables. Produce release notes covering supported mechanisms/coverage, provider/platform validation, data migration and known limitations.
- Complete developer setup, architecture/contract contribution, content/model review, user inquiry/reporting, BYOK/privacy/spending, backup/import/export/recovery and native installation guides. Validate README commands against the actual release tree.
- Record functional/model/security/product acceptance with agent-review or SV status, deferred review risk and any required external signoff, a recovery/rollback plan and support triage policy. Keep release authorization and artifact publication explicit; preparation does not itself publish a release.

**Acceptance/evidence:** a new contributor can install/run/test from documented commands, and a native end user needs neither Python nor an AI account for core tasks. Release inventory and evidence identify the same frozen candidate; publication status is reported accurately. Complete-product delivery requires all roadmap gates, not only a downloadable package.
