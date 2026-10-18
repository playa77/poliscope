# WP-009-store — Versioned SQLite transaction foundation

Started 2026-10-18 from current main
`500998751c1fb1ce95ac4f48362a69f450caa871` (PR #12 merged).
Owner Codex `/root`; controller requesting repository user; one sequential agent.
Branch `codex/wp-009-store`; reserved checkout `/workspace/poliscope`.
Validation route SV: separate inspection; solo-validated; agent review deferred.
Prerequisites: WP-002 at `d86aa12` and merged protocol-1 WP-005-wire at
`e0e18287cda3a45d52f22e98518ea6553134f580`; evidence DTOs at the base above.

Allocation follows distributed delivery §4.1's early provider exception. Scope:
Python production user-data-path selection, versioned SQLite initialization,
foreign keys/WAL/FULL durability, explicit rollback-safe transactions, backup API,
immutable bounded data-only records, durable accepted evidence, context/payload
bound operation outcomes, independently disposable caches. Reuse protocol-1
bounded evidence/operation DTOs; no new remote operations. Write scope storage,
engine tests, storage documentation and execution records. No dependencies added.

Acceptance: reopen preserves exact text, identities and evidence; foreign-key and
transaction failures retain old valid state; nested transactions fail explicitly;
backup reopens consistently including uncheckpointed WAL data; future/foreign
schemas fail without migration; only schema 1 creation is supported; future upgrades must add backup-before-migration
validation before being enabled; cache clearing preserves durable records and operation outcomes; operation
IDs bind context/payload and replay prior outcomes; retained records cannot be
updated/deleted. Tests use isolated synthetic databases and independent SQL reads.

This child does not certify full WP-009, G1, world/pack semantics, domain
repositories, player apply/replay, private payload classification, retention quotas,
Electron single-instance enforcement, or historical-reader authorization. Those
remain WP-006/007/008, WP-009-repositories, WP-010/011, WP-018 and later providers.
The storage API is trusted Python infrastructure, not an untrusted SQL interface.

## Separate inspection and evidence

Inspected explicit transaction boundaries, SQLite's automatic rollback behavior,
foreign-key enforcement, immutable-table triggers, bounded text, exact decimal
preservation, operation context/binding mismatch and replay, schema identity,
backup overwrite protection and WAL behavior. Inspection found that SQLITE_FULL
can abort a transaction before the context manager exits; writes now also require
SQLite's active-transaction flag, preventing an accidentally caught failure from
turning later writes into autocommits. An adversarial regression covers this.
Unknown/foreign schemas are preserved; only initial schema creation is implemented,
not a claimed migration from a nonexistent older Poliscope database.

29 synthetic storage tests exercise real SQLite files, independent SQL reads,
reopening, live-WAL backup, process exit (no commit), duplicate/FK/disk-full failure,
write contention, malformed/oversized data, context separation and retained-table
immutability. The broader suite passes: 256 pytest tests plus 24 subtests,
163 Vitest tests and 40 roadmap unittests. Typecheck, generated-contract drift,
content inventory, roadmap/baseline and whitespace pass. Frozen npm/uv setup
succeeded with writable `/tmp` caches and unchanged locks; no new dependencies.
Fresh engine/unit candidate-bound reports are recorded and verified under
`/tmp/poliscope-wp009-store-{engine,unit}`. Native Electron/package checks are
unrun: this package adds no desktop integration. Hosted CI and independent agent
review remain separate evidence. No paid providers or production data were used.

Outcome: **solo-validated; agent review deferred**. Allocated WP-009-store is
complete. This is production infrastructure invoked directly by its tests, not a
claim that application create/apply or trusted historical reads are integrated.
Generic retained JSON requires future repositories to validate world/pack semantics,
privacy boundaries and evidence closure. No storage upgrade, quota manager,
Electron ownership or WP-009 parent/application acceptance is claimed. Next ready
work is WP-010-transport; historical-read needs the storage/evidence providers and
its own exact bounded contract. One sequential agent remains available.
