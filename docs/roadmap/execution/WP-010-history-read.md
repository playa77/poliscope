# WP-010-history-read — Trusted saved-evidence reader

Started 2026-10-18 from merged PR #14, main
`0b828b53d2c6a4642ffa8a31259065f98922d215`. Owner Codex `/root`; controller
requesting repository user; one sequential agent; checkout `/workspace/poliscope`;
branch `codex/wp-010-history-read`. Route SV: separate inspection, agent review
deferred. Dependencies: WP-005-evidence at `500998751c1fb1ce95ac4f48362a69f450caa871`
and WP-009-store at `3785021ae0c8032e80413d16c23aff81a18a034c`.

Scope: canonical historical-interface-1 DTOs/generated schema and TypeScript,
Python read-only schema-1 SQLite reader, packaged reader entry, main-owned
one-shot launch and result validation, synthetic process/SQLite/consumer tests.
Write reservation: those modules, tests, generator and package documentation.
No new dependencies. Full WP-010 lifecycle and shell integration remain separate.

Launch authorization: trusted main supplies an absolute database path, opaque
storage context ID and exact revision context/result ID grant. IPC cannot select
a path, context, arbitrary SQL, mutation, computation or other saved result.
The reader checks the grant before opening SQLite. A future public IPC caller must
first pass sender/document and player selection authorization in the shell.
No renderer API or automatic fallback is introduced in this child.

Acceptance: cold start without numerical runtime/model or renderer cache reads
schema-validated retained evidence; read-only SQLite includes committed WAL data;
independent history protocol and stored-result labeling preserve original model,
runtime/revision identities and decimal strings. Bounded collection pagination
returns validated DTOs only. Missing/foreign/future/altered schemas, corrupt saved
payloads, cross-context/result access, malformed/oversized input and process
failure fail safely without migration or source mutation. Main permits at most
one child per controller and bounds output and wall time. Native packaged reader
must be exercised on the available host; other OS and full application gates
remain unverified. Schema-1 support is not archive extraction/older-schema recovery
(WP-041), durable operation replay or numerical reproducibility.

## Separate inspection and validation

Inspected the data-only import path, exact schema comparison before data queries,
read-only/query-only setup, disabled extensions/trusted schema, SQL work/length
bounds, grant checks before opening, stored context/result binding, typed pages,
output bound, safe errors and main's kill/launch limits. Inspection identified a
consumer numeric spelling gap: JSON decimal tokens could round into valid integer
DTO values before schema checking. The consumer now rejects noninteger spellings
and unsafe integer tokens before parsing; a regression exercises fractional tick
spelling. Empty continuation pages are also rejected to prevent cursor loops.

Validation: 283 pytest tests (plus 24 subtests), 188 TypeScript tests and 40 roadmap
unittests pass. Typecheck, generated artifacts, content inventory, roadmap and
baseline checks pass; frozen npm/uv locks are unchanged. Tests cold-start the
reader as a real Python process and invoke it through main against synthetic
SQLite; live committed WAL evidence, exact decimal text, original model/revision
identities, pagination, denied grants, absent results/stores, malformed/oversized
frames, invalid payloads, unknown/foreign/altered schemas, hostile views, missing
executables, invalid output and concurrent launch refusal are covered. Initial
TS fixture setup blocked on stdin; the fixture now passes bounded synthetic data
as an argument with a setup timeout. Checks requiring uv use a writable /tmp
cache; a default-cache permission failure was corrected without changing locks.

PyInstaller builds the native Linux executable. Its `--history-read` entry reads
a real schema-1 store with live WAL, preserves the main database bytes and returns
the original summary with explicit stored-history labeling. The same executable's
normal protocol-1 handshake still works. No numerical model or renderer cache is
required. Full Electron packaging/launch and Windows/macOS behavior are unrun for
this package; this does not certify fallback UI, application gates or native release
support. No providers, personal data or paid services were used.

Outcome: **solo-validated; agent review deferred**. Full allocated minimal reader
child is complete; future producers must retain the documented envelope, not raw
private payloads or arbitrary JSON. No archive extraction, older-schema migration,
operation replay, automatic fallback or public preload RPC is claimed. Next ready
scope for reassessment is WP-011-shell. Candidate-bound engine/unit evidence is
recorded and verified under `/tmp/poliscope-history-final-v2-{engine,unit}`; those
local reports are not hosted CI or independent review.
