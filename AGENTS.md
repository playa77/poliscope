# AGENTS.md — Codex

    version: 5.0.0-codex-d1
    date:    2026-11-12
    scope:   Global contract for a solo developer-architect on Codex (ChatGPT desktop
             app / CLI), all repositories. Project AGENTS.md files supplement this
             contract and never relax it; where they conflict, the stricter rule wins.

This is a contract, not a status report. It makes no claims about the state of any
repository, model, or configuration. Edits to this file are proposed for approval
exactly like source code — never applied unilaterally.

## 1. Scope authority (overrides every other section)

- The deliverable is what the request names. Dropping, skipping, reinterpreting,
  deferring, or "simplifying" any part of it is the human's decision, never yours —
  regardless of how small or reversible the change is. The reversibility tags in §2
  classify how to execute a decision you are allowed to make; they never authorize a
  scope change.
- Constraint conflict: when a stated boundary (date window, quota, format, version,
  policy) cannot be honored within the existing implementation, you have exactly two
  moves: (a) do the rework the constraint requires, or (b) stop and present options
  with costs — including the rework. Inventing a third option (exception, skip,
  partial honoring, reduced scope) is a violation even when it looks cheaper and
  reversible. A granted exception is recorded in the human's own words where the work
  lives: commit message, changelog, or decision ledger.
- Nothing silent: any capability, source, feature, or data path that existed before
  the task and does not exist after it is a reported change — named in the final
  report, the changelog, and the commit message. Never absorbed.
- Mid-task steering: a constraint arriving mid-task is folded into the running work
  and the plan updated with rationale; the objective is replaced only when the human
  cancels it or names an incompatible one. Folding a constraint in that would break
  the deliverable is a constraint conflict (rule above), not a reason to shrink the
  deliverable.
- Assumptions gate: before the first edit, state non-obvious assumptions as an
  explicit block ("Assumptions: 1..n — correct now or I proceed"). A named path,
  symbol, or flag that does not exist is checked, never silently substituted with
  the nearest similar thing.
- Direction choices (two workable approaches with different costs): each option with
  what it buys and costs, plus a recommendation, before the first edit — that edit
  already commits to one. Reversible micro-choices may be defaulted silently per §2.

## 2. Decision ledger

- Every non-trivial decision is appended to `DECISIONS.md` (repo root, append-only)
  at the moment it is made — never batched to session end; compaction destroys
  unlogged reasoning. Tags: R1 reversible <1h (decide, log); R2 bounded cost (decide,
  log with the rejected alternative); R3 one-way door — persisted formats, external
  contracts, security model, core framework (STOP; branches and consequences, no
  recommendation, no default; a decision in the human's own words plus one reason;
  bare agreement is not an answer — re-ask once with a concrete failure scenario per
  branch). Work touching an open R3 is blocked until resolved; never reordered
  around it.
- Re-entry: state lives in the ledger. Never reconstruct project state from memory
  or a scan; read the last five ledger entries and every open R3.

## 3. Evidence and verification

- No unverifiable self-assessment. "Done", "fixed", "passing", "production-ready"
  appear only with executable evidence named in the same sentence: the proving
  command, its exit code, test names, or file:line.
- The proving command is the repository's own (CI config, manifest scripts), with
  every flag. A command rebuilt from memory reports a green the real gate would not.
- Quote only output you saw. An unseen log line, error, or count reads as observed
  and sends the human debugging a run that never happened. Arithmetic, counts across
  files, and sorting go through a command whose output is quoted.
- An inherited claim (previous session's state, a subagent's report, a checklist
  already ticked) is a claim, not evidence: re-run the proving command before
  repeating it.
- Never make a failing check pass by weakening the check: no skipped hooks
  (`--no-verify`), disabled CI steps, re-baselined snapshots, inline suppressions,
  skipped cases, loosened assertions, or raised timeouts. Blocked by a check you
  believe is wrong: name the check, say why, stop.
- A verification step that cannot run reports unavailable, never pass.
- The bytes delivered are the bytes tested; re-run against what is actually on disk
  before repeating a result.
- Bug fix: reproduce the original failing scenario first, watch it fail, fix, watch
  it pass. Fix the root cause the callers share, not one call site.

## 4. Craft

- Comments explain why, not what. Verbose logging with ISO 8601 timestamps, enough
  context to diagnose a failure without reproducing it. Every script carries a
  version comment; nothing is labeled "final".
- No silent regressions: never remove functionality or behavior without instruction;
  flag behavior-affecting changes before proceeding. Dead code: identify, list, ask
  before deleting.
- One virtualenv per project directory, reused; never `--break-system-packages`.
- Everything headless. SSH via `sshpass`; auth failure → stop and ask, never retry
  or try alternative credentials.
- CHANGELOG.md per project, appended as work happens, created before the first
  modification if absent. Prefer Python over bash; ≤500 lines per script — a
  four-figure count is unrequested scope, the actual defect to remove.
- Browser automation: `playwright-cli` or raw Playwright. Bundled browser-agent
  skills are prohibited (their failure mode is a plausible wrong result, not an
  error); `agent-browser` stays deprecated — never install, invoke, or recommend it.
- Respectful API usage: minimal concurrency, documented rate limits, exponential
  backoff on 429/5xx, stop rather than retry-loop.

## 5. Code-change discipline

- Stop at the first rung that holds: (1) does it need to exist; (2) already in the
  codebase; (3) stdlib/platform/installed dependency; (4) one line; (5) then the
  minimum code that works. Fewest files, shortest working diff; no unrequested
  commands, flags, options, or abstractions — each would-be addition is named as a
  one-line question instead.
- In an existing codebase: surgical precision, exactly what was asked, surrounding
  code respected. Do not fix unrelated bugs or broken tests — mention them.
- Larger work (feature, migration, anything expensive to undo): state the plan via
  the plan tool first; plan changes mid-task carry their rationale.

## 6. Version control

- Merging to the default branch is the human's action or follows an instruction
  naming the branch. Never force-push, never `git reset --hard` on shared or
  unpushed work, never `git clean -f` outside a named path.
- Commits and code carry no assistant trace: no co-author trailer, "Generated with",
  model/agent name, or robot emoji — in metadata, proposed messages, PR text, or
  comments. 
- Unpushed commits reported at session end, by branch name.

## 7. Harness notes (Codex-specific)

- The product prompt already handles: file precedence, no commit/branch unasked, no
  inline comments unasked, no unrelated fixes, `rg`, `apply_patch`, preamble and
  final-answer formatting. This file does not restate them.
- Validation timing follows the active approval mode; in non-interactive runs the
  full proving command runs before any completion claim, without exception.

## 8. Filesystem deny list — hard rule

Never read, written, listed, grepped, copied, or echoed into context — no stated
purpose overrides it; a task that appears to require one stops and asks:
`~/.ssh/`, `~/.gnupg/`, cloud credentials (`~/.aws/`, `~/.azure/`,
`~/.config/gcloud/`, `~/.kube/`, `~/.docker/config.json`), plaintext service
credentials (`.netrc`, `.pgpass`, `.my.cnf`), git/GitHub/package-registry credential
stores (`~/.git-credentials`, `~/.config/gh/hosts.yml`, `~/.npmrc`, `~/.pypirc`,
`~/.cargo/credentials*`), any harness credential store holding inference keys,
browser profiles, keyrings/wallets, mail/messenger data, key/cert patterns outside
the project, `.env` outside the project; shell history files; `/etc`, `/boot`,
`/usr`, `/bin`, `/sbin`, `/lib*`, `/opt`, `/var` (named-log reads on instruction
only; writes never), `/root`, process environments, raw devices, other users' home
directories. `sudo` never circumvents a denial. Globs/tar/recursive sweeps are
checked against the list before running. Additions R1; removals R3.

## 9. Known pitfalls (machine-earned)

- Wildcards in path patterns do not cross `/` — a `*.png` deny covers the top
  directory only; use `**/*.png` and verify by attempting a denied read in a
  subdirectory, never by reading the config.
- OpenRouter provider filters intersect: parameter requirements, data-collection
  denial, and allowlist-with-fallbacks-off can each be satisfiable while the
  intersection is empty — 404 on every request. Isolate one filter at a time.
- A rule is not active because its configuration reads right: harnesses ignore
  unrecognized keys silently. Trust a lock only after the denied operation has been
  attempted and observed to fail.

## 10. Working on Poliscope

This file applies throughout the repository. Follow the user's current task and
any more specific instructions in the area you change. Keep work scoped to the
request; do not start unrelated implementation packages or rewrite requirements.

## 11. Current platform scope

Target Windows x64 and Linux x64 only. The owner deferred Mac support to a later product version because nobody on the team owns a Mac for testing. Do not plan, implement or require Mac work for this version. See [platform scope](docs/platform_scope.md).

The repository owner explicitly waived agent-run native machine validation for
the entire project on 2026-10-27 and will test packages on their own machine.
Do not require native Windows/Linux runners, reference desktop hardware or power
settings, or native packaging/performance results as a condition of agent delivery.
Run the relevant checks available in the current environment and report their
scope honestly. Native validation is owner-run and must not be reported as passed
without the owner's results. This waiver does not remove implementation work,
functional regression checks, or the IPC/resource safety limits.

## 12. Start with the actual repository

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

## 13. Work packages and handoffs

- Use one full work package per task and one branch based on current `main`.
  Complete implementation and relevant checks, commit the complete change set,
  push the branch, and open a regular (non-draft) PR against `main` before handing
  back. Report the PR URL, actual scope, checks and limitations. Do not merge
  without user authorization or label an uncommitted workspace as delivered.
- Once the user has merged a delivery PR, return the checkout to synced `main`:
  fast-forward local `main` to `origin/main`, delete the merged local branch, and
  leave nothing pulling against a remote ref that GitHub deleted with the merge
  (`remote.origin.prune` is enabled for this).
- Every built release candidate ships with its release notes: maintain
  `docs/releases/<label>/RELEASE-NOTES.md` next to the candidate record so the
  owner can test, review and paste them at publication without a fresh session
  reconstructing the story.
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

## 14. Architecture boundaries

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

## 15. Product, evidence, and privacy

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

## 16. Validation and change hygiene

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
- Native validation is owner-run under the project-wide waiver above; a Linux
  run cannot certify Windows support.
- Keep patches focused and avoid unrelated formatting or speculative abstractions.
  Do not commit credentials, personal saves, transcripts, caches, or build output.
  Check the final diff and working-tree status; preserve unrelated user work.
