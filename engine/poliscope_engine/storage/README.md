# SQLite foundation (storage schema 1)

`Store(absolute_user_data_path)` selects `poliscope.sqlite3` beneath the directory
supplied by main. Python alone writes SQLite. A Store is thread-affine; use its
context manager or close it. It enables foreign keys, WAL and synchronous FULL,
with a one-second bounded busy timeout. Main must acquire Electron's single
instance lock for this data directory before launching a writer; SQLite's writer
lock serializes transactions but does not enforce application ownership.

Use `with store.transaction():` for every write. It acquires BEGIN IMMEDIATE,
commits only on successful exit, and rolls back on exceptions, including SQLite
quota/I/O failures. Nested transactions and closing or backing up during a write
are rejected. A caught statement failure must be propagated if the caller wants
the entire unit rolled back. Transactions can atomically insert immutable context,
records, accepted evidence and operation outcomes. Direct SQL is not a public
application API; only trusted repositories may use these primitives.

Contexts carry caller-defined civilization/branch identities. Records are immutable
versioned input/archive building blocks. Evidence stores retained data-only JSON
separately from replaceable caches; clearing caches deletes only cache rows.
Updates/deletes to retained tables are rejected by database triggers. Callers own
reference closure, units, model/runtime identities, semantic validation and private
payload boundaries. This primitive does not accept a claim of complete scientific
or historical evidence merely because JSON is valid. It stores no private payload
classification and must not receive private notes/transcripts as immutable records.
Future repositories bind canonical contracts and store noncontent private references.

Each JSON payload is at most 1 MiB in UTF-8; identifiers are 1–512 bytes. Exact
input text and decimal strings round-trip unchanged; non-JSON constants fail.
Readers fetch one identified record at a time; there is no unbounded listing API.
Protocol-1 evidence pages and operation-status DTOs already merged in WP-005 are
available to consumers, which must validate the DTOs and paginate before dispatch.
Storage does not expose SQL or a new IPC endpoint. Generic JSON is an infrastructure
boundary, not world/pack validation or authorization.

Operation keys are scoped by context. `operation_outcome` compares a caller's
canonical binding (operation, original context/revision and full payload) byte for
byte; different bindings fail. A completed outcome is immutable. The apply service
must look it up before checking the current head and retain the outcome atomically
with its effects. `complete_operation` is idempotent for identical bindings and
outcomes; this alone does not implement player apply or operation authorization.

`backup(new_absolute_path)` uses SQLite's backup API from a committed boundary;
it includes committed WAL pages without copying database files by hand. Exclusive
creation prevents overwriting an active database or existing backup. Preserve the
returned backup independently; it contains retained data and has its own disposal
policy. Backups and WAL can retain older data; no secure-erasure guarantee applies.

Application ID, user_version, schema structure and version history are checked.
Only empty-database creation and storage schema 1 reopening are supported now.
Unknown/foreign/altered schemas fail with preservation guidance; no implicit repair
or upgrade runs. There is currently no older Poliscope schema to migrate. Before
adding any upgrade, add an explicit migration, backup-before-migration and injected
failure/recovery tests. Backup and migration metadata extensions require a versioned
schema change. Full archive/historical reader support belongs to WP-010/041.

Tests use temporary synthetic databases, independent SQL assertions, process exit,
real SQLite disk-full/write-lock errors, and live-WAL backup checks. They do not
certify Electron ownership, full world repositories, historical reader access,
privacy-safe exports, native targets or any application gate.

Schema-1 retained evidence now has a supported read-only consumer in
`poliscope_engine.history`. Its launch grant and bounded envelope are documented
in `contracts/README.md`; raw generic evidence is rejected unless it validates
that envelope. The reader never constructs Store, creates a database or migrates
one. This does not supply production world/evaluation repositories or private
payload classification.

WP-018's `revisions` repository now supplies production immutable world/history,
preview/apply, append-only branch state and transactional accepted-result closure
on these unchanged schema-1 primitives. `read_context` and bounded indexed
`record_page` expose retained metadata/record reads to trusted repositories.
No schema migration or raw renderer SQL access is added. See
`../revisions/README.md` for limits, authorization, operation replay and chunking.
