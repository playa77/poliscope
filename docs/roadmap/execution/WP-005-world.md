# WP-005-world — Bounded world inspection contract

Started 2026-10-18 on current main
`e0e18287cda3a45d52f22e98518ea6553134f580` (PR #10 merged).
Owner Codex `/root`; controller requesting user; one sequential agent.
Validation route SV with a separate inspection pass and deferred agent review.
Branch `codex/wp-005-world`; reserved checkout `/workspace/poliscope`.
Prerequisite WP-005-wire merged in PR #10 at the base above. WP-003 merged
in PR #9 at `3cac56b3a33a28a9dd69f89901f892c6930d7fbb`.

Scope: canonical, bounded world inspection request/result DTOs for immutable
revision context, independent model/catalog/numeric identities, effective time,
scopes/entities/typed relationships, partitioned values and mechanism bindings.
Generate their schema/types/tool inputs through the existing wire generator.
Write scope engine contracts, generated contracts, main boundary validation,
shared fixtures/tests and package execution records. No persistence, topology
solver, unit registry, simulation, preview/apply or evaluation service is allocated.

Acceptance: Python/TypeScript round-trip shared world fixtures without changing
decimal strings or identities; unknown quantities remain distinct from zero;
bounded revision-bound pagination; reject malformed quantities, unknown enum
values, extra fields, malformed reference IDs, unsupported schemas and wrong types.
All six state partitions and all specified relationship kinds are represented.
Existing runtime fixtures remain compatible. Contract generation/drift, unit,
engine, type and roadmap checks pass. Structural validity does not prove topology,
unit compatibility, scientific validity, or a complete/infeasible evaluation.
WP-005-evidence owns findings/evaluation contracts; WP-006/007 own numeric and
world semantics. WP-005 parent acceptance remains open.

## Checkpoint

Current main was retrieved through the GitHub connector with all blob/tree/commit
hashes verified, then fast-forwarded; a subsequent network-enabled Git fetch
confirmed the baseline. Frozen npm/uv installs succeeded after sandbox network
access was granted, with unchanged locks.

## Separate inspection and validation

Inspected canonical/generated DTOs, discriminator handling, required nullable
fields, independent version identities and effective-time fields, complete
partition/relationship vocabularies, scoped provenance and explicit aggregation.
Checked that the extension preserves the existing runtime fixture behavior and
requires regenerated consumers before world dispatch. Decimal strings are not
converted to floats. The main validator now enforces generated string patterns;
full-match checking also rejects JavaScript's end-anchor acceptance of a trailing
newline. Both runtimes reject malformed decimal spellings and preserve exponents.

Fixtures exercise five request collections and five typed result collections,
all specified enum variants, continuation and empty terminal pages, unknown versus
zero, high-precision/exponent decimal strings, malformed schemas/types/references,
extra fields and oversized lists. Dedicated outbound tests catch caller-forged
quantities and a structurally valid 100-item page exceeding the combined 1 MiB
limit. Context preservation is tested; cursor authorization/binding is explicitly
the future service's responsibility, not claimed by structural tests.

Validation on Linux x64 with the pinned frozen environment: 186 pytest tests
and 24 subtests, 124 Vitest tests, typecheck, contract regeneration/drift,
content inventory, roadmap/baseline and whitespace checks pass. The root npm test
also passes its 40 roadmap unittest cases (already included in pytest's count).
No skips; no dependency/lock changes. Candidate-bound engine/unit evidence is
captured under `/tmp/poliscope-wp005-world-{engine,unit}` and verified after the
final source changes. Native Electron smoke is unrun locally; this package changes
contracts and the unintegrated boundary validator, not bootstrap dispatch.
Hosted CI and non-Linux native platforms remain separate evidence.

Outcome: **solo-validated; agent review deferred**. Full allocated world-contract
scope is complete. World persistence/services, graph/numeric semantics, evaluation
findings, preview/apply, cursor authorization and other WP-005 children remain open;
no application milestone or WP-005 parent acceptance is claimed. After merge,
reassess WP-005-evidence and ready store/transport work with one agent.
