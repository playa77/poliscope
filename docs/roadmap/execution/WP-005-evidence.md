# WP-005-evidence — Evaluation and explanation contracts

Started 2026-10-18 at current main
`1775a361b3cdf0ad2d94fc3c7518dbaa4ddfcc9d` (PR #11 merged).
Owner Codex `/root`; controller requesting user; one sequential agent.
Branch `codex/wp-005-evidence`; reserved checkout `/workspace/poliscope`.
Validation route SV: separate inspection, then solo-validated; agent review deferred.
Prerequisites: WP-005-world merged at the base above, WP-005-wire at
`e0e18287cda3a45d52f22e98518ea6553134f580`, WP-003 at
`3cac56b3a33a28a9dd69f89901f892c6930d7fbb`.

Scope: bounded revision/result-bound evidence reads and evaluation summary DTOs;
coverage and findings; source/assumption lineage; typed trace inputs/outputs;
generated schema, TypeScript/tool inputs and synthetic compatibility fixtures.
Sources: technical specification §§6.3, 7.3, 9, 10.1, 11. Write scope: engine
contracts, generated contracts, shared tests/fixtures and execution records.

Acceptance: exact quantities and separate unknown values survive both runtimes;
all seven coverage states and five finding classes are represented; incomplete
and infeasible designs remain successful results; model unavailable and stale
revision are typed operation errors. Sources pin document/revision/location/digest,
license, historical status and supersession. Assumptions record scope, definition,
origin, uncertainty and rationale. Trace pages pin mechanism/version, typed inputs,
outputs, dependencies and provenance. All pages bind immutable revision, result,
model/runtime identities, scope and effective time. Invalid enums, extra fields,
wrong types, unsupported evidence schemas and oversized arrays/frames fail closed.
Existing fixtures remain compatible; frozen installs, drift, type, engine/unit,
roadmap/baseline and whitespace checks pass, followed by separate inspection.

No evaluation computation, persistence, trace traversal/cursor authorization,
scientific validity, source-license verification, historical reader, privacy
payload, preview/apply or parent/application-gate acceptance is allocated.

## Inspection and validation

Refreshed the clean checkout with a network-enabled Git fetch and branched from
origin/main at the recorded SHA. Frozen npm/uv installs succeeded using writable
`/tmp` caches; locks remain unchanged. Initial default-cache attempts failed on
read-only home paths; the subsequent frozen setup and checks use explicit caches.

Separate inspection checked discriminator variants, strict required/null fields,
source revision/digest/license/history separation from coverage, assumption origin
and uncertainty, trace ports/dependencies, exact decimal strings, error/result
separation, and retention of existing runtime/world fixtures. Known outputs reject
unknown values; unavailable statuses reject numeric zero. Cross-reference closure,
consistent coverage/observation statuses and cursor authorization remain producer
service obligations, explicitly documented rather than inferred from DTO validity.
The 1 MiB outbound checks revalidate forged nested values and combined page size.

Linux x64 checks: 227 pytest tests plus 24 subtests; 163 Vitest tests; root npm test
including 40 roadmap unittests; typecheck; generated-contract drift; content
inventory; roadmap/baseline; whitespace. All pass without skips. No dependency or
lock changes. Fresh candidate-bound engine/unit evidence is recorded and verified
in `/tmp/poliscope-wp005-evidence-verified-{engine,unit}`. Native packaged Electron smoke
and non-Linux checks are unrun; no bootstrap routing behavior changed. Hosted CI
and independent review remain separate evidence.

Outcome: **solo-validated; agent review deferred**. The full allocated evidence
contract child is complete. Simulation, source/numeric verification, persistence,
historical-read/privacy/timeline contracts and WP-005 parent acceptance remain
open. After merge, reassess ready store/transport packages; timeline still needs
WP-033-adoption. No application gate is claimed.
