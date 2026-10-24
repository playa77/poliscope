# Working on Poliscope

This file applies throughout the repository. Follow the user's current task and
any more specific instructions in the area you change. Keep work scoped to the
request; do not start unrelated implementation packages or rewrite requirements.

## Current platform scope

Target Windows x64 and Linux x64 only. The owner deferred Mac support to a later product version because nobody on the team owns a Mac for testing. Do not plan, implement or require Mac work for this version. See [platform scope](docs/platform_scope.md).

## Start with the actual repository

- Inspect `git status`, the current branch, relevant files, and applicable
  `AGENTS.md` files before editing. Preserve existing edits and untracked files.
- At the start of an implementation package, fetch the current baseline and
  reconcile it with the package branch. Prefer a fast-forward pull when possible.
  Never discard work, overwrite drafts, or reset/clean the checkout to refresh it.
  If a stash or backup is needed, identify it in the handoff and retain it.
- Read `docs/roadmap/execution/active-package.json` and its parent record before
  historical child handoffs. They identify the current full package. Application
  sources, pinned manifests, tests and CI exist; inspect their actual state.
- README development commands describe the intended interface until the scaffold
  exists. Do not claim an install, build, test, or application launch succeeded
  when its prerequisites are absent.

## Read the right sources

- [README](README.md): product overview and intended development commands.
- [Design](docs/design_doc.md): player experience and product requirements.
- [Technical specification](docs/tech_spec.md): architecture and system contracts.
- [Implementation roadmap](docs/implementation_roadmap.md): sequencing, decisions,
  milestones, and completion gates.
- [Delivery plan](docs/roadmap/distributed_delivery.md): package allocation,
  contract handoffs, review, and solo validation.
- [Shared packages](docs/roadmap/work_packages.md),
  [domain packages](docs/roadmap/domain_work_packages.md), and
  [verification matrix](docs/roadmap/verification_matrix.md): concrete scope,
  dependencies, acceptance criteria, and evidence.

Product and technical requirements come from the design and technical
specification; the roadmap organizes delivery. Read the sections relevant to the
task. Surface contradictions explicitly instead of silently changing requirements
or treating planned behavior as implemented behavior.

## Work packages and handoffs

- Use one full work package per task and one branch based on current `main`.
  Complete implementation and relevant checks, commit the complete change set,
  push the branch, and open a regular (non-draft) PR against `main` before handing
  back. Report the PR URL, actual scope, checks and limitations. Do not merge
  without user authorization or label an uncommitted workspace as delivered.
- Finish the full allocated work package before handing back. When the request
  covers a planning parent, complete its necessary children and parent acceptance;
  decomposition is not a reason to stop after one child. If completion is blocked,
  preserve the assignment and evidence and identify the concrete blocker.
- One top-level WP/DOM package per session and delivery PR is the default.
  Children are internal implementation steps/commits, not new user merge
  checkpoints. Only an explicit user instruction may authorize a partial child
  delivery. Never choose a child because it fits a turn, session or context window;
  continue through compaction, or resume the same parent after interruption.
  Do not relabel feature work as maintenance to evade the parent contract.
- Update `docs/roadmap/execution/delivery.json` and the full parent record for
  code deliveries. Feature delivery must complete the active parent's acceptance
  checklist. Corrective maintenance records its actual scope and leaves the
  active feature package intact. This declaration is not proof of behavior.
- For implementation work, identify the executable package and its prerequisites.
  Record scope, owner/controller, base commit, contract versions, deliverables,
  validation route, and acceptance criteria in the project's package records.
  Do not invent assignments or mark prerequisites verified without evidence.
- Routine documentation, repository guidance, and small maintenance requests can
  be completed directly within the requested scope; they do not imply starting a
  new product milestone or creating an issue tracker.
- Default to sequential work by the current agent. The delivery plan supports
  one to three agents; it does not require delegation. If multiple agents are
  allocated, use isolated worktrees/clones and private runtime data, declare
  nonoverlapping write scopes, and coordinate shared contracts and lockfiles.
- Keep an active package's owner, scope, and validation route stable. Changes in
  available agents affect subsequent allocations. Decompose large packages before
  execution, preserving the parent's dependencies and acceptance requirements.
- A reviewed, merged contract child can enable consumer development before its
  parent is accepted. Record the exact upstream commit and limitations. Mocked
  behavior does not satisfy production integration or milestone acceptance.
- Follow the declared review route. Solo work uses the delivery plan's separate
  inspection pass and records `solo-validated; agent review deferred` when
  applicable. A fresh session of the author is not independent review.
- Finish with changed files/behavior, checks and results, remaining limitations,
  and any next action or blocker. Keep durable package evidence in repository or
  PR records so another session can continue without chat history.

## Architecture boundaries

The intended stack is Node.js 24 LTS, Electron/Forge/Vite, React/TypeScript,
Python 3.12 with Pydantic 2 and Decimal, SQLite, and `uv`. Confirm actual paths
and tooling when the scaffold is introduced. Planned responsibility boundaries:

| Area | Responsibility |
| --- | --- |
| `desktop/main/` | Lifecycle, engine process, files, protected keys, provider networking |
| `desktop/preload/` | Named, typed, validated renderer API |
| `desktop/renderer/` | React presentation, queries, and temporary UI state |
| `engine/` | Canonical world, domains, simulation, storage, explanations, contracts |
| `contracts/` | Generated schemas/types and versioned compatibility fixtures |
| `content/` | Versioned catalogs, sources, evidence, mechanisms, and fixtures |

- Python owns simulation arithmetic, allocation, transitions, numerical
  comparisons, cost aggregation, and SQLite writes. Do not duplicate these rules
  in TypeScript or let domains maintain competing copies of shared resources.
- Authoritative quantities use Decimal parsed from decimal strings, with the
  specified 28-significant-digit, round-half-even context. Preserve units, scopes,
  time bases, provenance, and model/runtime identity. Apply the declared account
  quantum/magnitude/residual rules; reject transfers lost to precision and use an
  independent exact balance oracle. Unknown is not zero.
- Generate JSON Schema, TypeScript types, and tool schemas from canonical Python
  contracts. Regenerate artifacts when contracts change and test compatibility.
- Main launches the engine without a shell. IPC is bounded, versioned JSON Lines
  over stdio; engine stdout is protocol only and diagnostics go to stderr.
- Keep `nodeIntegration: false`, `contextIsolation: true`, and `sandbox: true`.
  Renderer code has no direct filesystem, database, provider, or process access.
  Preload must not expose arbitrary IPC or shell execution.
- Preserve pure previews, immutable committed revisions, stale-candidate checks,
  idempotent apply, and transactional state changes. Cancellation and recovery
  must not commit partial transitions or erase user history.
- Retain accepted-result evidence separately from disposable caches. Historical
  reads use the trusted data-only reader; execution compatibility is a separate
  decision from safe schema readability. Mutation retries use context/payload-bound
  operation IDs and replay completed outcomes before checking the current head.
- Schedule explicit policy deltas with binding preconditions; stage and validate
  all transition effects before durable confirmation and publication.
- Keep the application local and usable offline. Do not introduce a web backend
  or separate model server without an explicit architecture change.

## Product, evidence, and privacy

- Preserve player agency: no mandatory civic policies, hidden objective function,
  overall civilization score, automatic redesign, or universal winner ranking.
- Label synthetic fixtures and reference arrangements. Preserve historical
  alternatives, source revisions, attribution, licenses, and model assumptions.
- Distinguish implemented, partial, qualitative, unresolved, and unsupported
  behavior. Structural validity does not establish scientific validity. Missing
  mechanisms stay visible; do not invent numerical social effects.
- Keep AI assistance to explanation, inspection, proposals, and noncommitting
  previews. Only the player's validated action can apply a proposed game change.
  Imported packs and generated text are data, never executable code.
- Keep keys in main's OS-protected storage, with session-only storage when secure
  persistence is unavailable. Never pass keys to Python or return stored keys to
  the renderer. Exclude secrets and private runtime data from Git, logs, fixtures,
  prompts, and exports. Classify private payloads and derived copies separately
  from immutable simulation history. Enforce sharing scope for every provider
  payload and reserve spending atomically before each billable dispatch, including
  tool continuations. Rendered untrusted content must not load remote resources.
- Provide keyboard access, text meanings for status colors, and accessible
  table/list alternatives to charts and matrices. Show revision, scope, time,
  and coverage where needed to interpret results.

## Validation and change hygiene

Once manifests, locks, and scripts exist, use the repository-root command
interface below. Run checks relevant to the change and the package's acceptance
criteria; report missing prerequisites and skipped/unrun checks honestly.

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

- Use the verification matrix's exact gate/subcase manifest; do not choose an
  unspecified subset of a cross-milestone scenario. A documentation disposition
  does not certify application behavior.
- These are setup, development, validation, and packaging commands, not a single
  mandatory sequence for every edit. Documentation-only changes need relevant
  link/content review and `git diff --check`, not nonexistent application tests.
- Reuse a valid environment when locks are unchanged. During development run
  affected tests and shared-invariant regressions; consolidate universal checks
  instead of copying them into every pair suite. Run the full suite once at the
  integrated package boundary when warranted, or let the authoritative full CI
  candidate run provide it. Do not repeat passing full runs after unrelated
  documentation edits or wait for post-merge smoke before starting authorized work.
- CI runs engine and desktop validation on separate runners, with a stable
  fail-closed `checks` result. Main pushes run a bounded engine smoke; manual and
  weekly runs retain full validation. Docs-only PRs use roadmap/content review.
  Keep exact candidate/gate evidence for full runs; never call a smoke a full gate.
- Report completed parent acceptance first. Separate handwritten engine/desktop
  changes, tests/helpers, fixtures, generated artifacts and documentation in line
  counts. Distinguish new tests from cumulative passes; neither measures features.
- Use pytest for engine invariants, Vitest for desktop/provider contracts, and
  Playwright for Electron flows. Derive numerical/procedural expectations
  independently; test meaningful failures as well as successful behavior.
- Ordinary tests use synthetic isolated data and mocked providers. Paid live
  provider checks require explicit opt-in and bounded scope. Report untested
  capabilities and unavailable native platforms as untested.
- Keep dependency locks and generated contracts tracked. Use frozen installs;
  do not regenerate locks merely to get past an unexplained failure. Document
  intentional dependency changes and additional runtime dependencies.
- Native packages must be built and validated on their target OS/architecture;
  a Linux run cannot certify Windows support.
- Keep patches focused and avoid unrelated formatting or speculative abstractions.
  Do not commit credentials, personal saves, transcripts, caches, or build output.
  Check the final diff and working-tree status; preserve unrelated user work.
