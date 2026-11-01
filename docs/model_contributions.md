# Contributing contracts, content and models

Start with [development setup](development.md), [AGENTS.md](../AGENTS.md),
[design](design_doc.md) and [technical specification](tech_spec.md). Use one full
allocated package, current main and the declared review route. Preserve source
versions and existing work. A new implementation invalidates evidence for affected
behavior; a test name or documentation disposition cannot certify production use.

Python contracts in `engine/poliscope_engine/contracts/` are canonical. Change
those models first, run `uv run --frozen python scripts/generate_contracts.py`,
and inspect the generated JSON Schema/TypeScript/tool artifacts and compatibility
fixtures. Run `npm run contracts:check`, TypeScript and affected boundary tests.
Do not hand-edit a second competing schema in the renderer or add arbitrary IPC.
Main owns files, provider requests and keys; Python owns arithmetic and SQLite;
preload exposes named validated calls; the renderer owns presentation.

For each mechanism declare stable ID/version, scope, inputs/outputs, units/time
basis, evidence, assumptions, authority, dependencies, supported transitions,
unknowns and independent expected outcomes. Use canonical entities/resources and
shared reducers, not domain-local copies of stocks or people. Distinguish empirical,
hypothetical, qualitative and unsupported effects; structural validity is not
scientific validity. Preserve alternatives, attribution, license and supersession.
A source design, target or generated number cannot silently activate model physics.

Decimal quantities arrive as decimal strings under `decimal28-half-even-exact-v1`.
Use the shared 28-significant-digit half-even runtime and account quantum/magnitude/
residual rules. Independent Fraction/integer oracles must detect lost transfers.
Preserve pure preview, explicit player Apply, stale checks, idempotency and atomic
publication. Scheduled policy deltas bind preconditions and explicit adoption;
unknown/unsupported prerequisites withhold effects rather than choosing precedence.

Update the relevant domain coverage/model records and generated content using
`npm run content:build`; review its diff and run `npm run content:validate`.
The pinned society importer is separate and never selects player policy:
`uv run --frozen python scripts/import_society.py /path/to/society /path/to/new-output`.
Read [the pinned source review](roadmap/execution/society/review.md) first.

Use synthetic fixtures and independently derived numerical/procedural expectations.
Run affected pytest/Vitest/packaged workflows and the exact required gate selection;
retain candidate, runtime and report digests, failures and precise reruns. No paid
provider check is authorized by contribution or release preparation. For frozen
inputs, `scripts/freeze_release.py --check` must reject drift until a reviewed new
candidate inventory is prepared; never overwrite an old receipt to disguise drift.
