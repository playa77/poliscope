# Portable historical archives v1

`archives.export_archive`, `validate_archive` and `import_archive` are trusted host
APIs. Main grants a local sandbox and a dialog-selected file. No renderer input
can select paths, SQL, code, ZIP members or process arguments. `archive_host` has a
separate packaged entry and uses no numerical registry for historical inspection.

The fixture `tests/fixtures/archives/format-v1.json` was fixed before either
consumer. Canonical Python contracts generate `contracts/archive.schema.json`
and TypeScript. Format/data schema 1 is a ZIP containing `manifest.json` and
numbered UTF-8 JSON data entries. Arbitrary entry names are never extracted.
Readable typed input, evidence, mechanism declarations and expression graphs are
data; imported definitions are never registered or evaluated. Unknown executable
model identities are separate from supported readable schemas.

The manifest records every entry's SHA-256/byte size, selected privacy scope,
redactions, explicit evidence omissions and the canonical projection digest.
The central directory is preflighted for actual header count, a 4 MiB byte
budget, forged counts and executable prefixes before the eager ZIP parser runs.
ZIP64 and multidisk archives are unsupported in v1. Bounds: 256 MiB compressed file and aggregate expansion, 64 MiB per data entry,
1 MiB manifest, 10,000 data entries. These are safeguards, not product model limits;
exports exceeding them fail without replacing the destination. Snapshot collection
and per-experiment history also have byte budgets. ZIP file counts, compression
methods, entry types, paths, flags, duplicate names/JSON keys, strict typed schemas,
internal references, cycles, chronology, evidence closure/state binding and hashes
are checked before the import write transaction. CRC verification is also supplied
by Python's ZIP reader. No native database/schema/SQL is accepted from a file.

Ordinary exports include every local revision and original alternative, current
branches/redo/fork lineage, complete experiment schedules and confirmed boundary
inputs, conditions, event/adoption outcomes, realized draws, complete transition allocation requests/results, claim ownership, steps and
balance witnesses, checkpoint selections, and complete accepted evaluation/report/
trace closures. Sources retain public attribution/licensing descriptors. Pending
unconfirmed work, caches and operation retry journals are excluded. This portable
format is not a backup; WP-041 owns explicit editable migration and backup/restore.

Private notes and rationale are noncontent references in immutable inputs; their
active separately owned payloads are read only on explicit category opt-in, for
all retained versions. Deletion tombstones remain authoritative. There is currently
no transcript or attachment owner; those categories are excluded in the UI.
No key store, key file, encrypted blob, attachment directory, private index,
derivative or backup is enumerated/read. Public player inputs and goal questions
remain ordinary game content. All nested alternatives and evidence snapshots use
the same private-reference redaction. A physically used assumption retains its
parameter ID with a redacted descriptor; private note/rationale identifiers and
original revision/retained-branch/boundary hashes are omitted. Public metadata ever classified
private in the same revision history remains excluded throughout that export.

Projection-local revision and branch IDs replace original hashes which may depend on private
references. Evidence snapshots and identities are rebuilt from redacted data and
checked by the existing data-only reader; saved quantities, choices, timing,
realization keys/outcomes, public model/source identities and trace dependencies
remain retained. No simulation or measurement is rerun. The UI labels these as
stored historical results with projection identities, never exact freshly
reproduced original results. An evidence-reduced export explicitly lists every
omitted revision/boundary result; it cannot later claim full evidence.

Import writes an immutable historical collection under `portable-archives:v1` in
one SQLite transaction. Identical projection imports are idempotent; distinct
projections coexist; an identity collision with a different manifest fails.
It never overwrites local civilizations, branches or accepted results. The
collection is the imported civilization/history inspection surface, separate from
editable native revision catalogues. Every import is historical; compatible
models still require explicit migration to become editable. Missing numerical or
stochastic runtime does not prevent cold inspection. Unsupported data schemas
fail with original file and local history preserved. Re-export of an imported
collection preserves its evidence and can further exclude private categories or
reduce evidence. Omitted evidence cannot be restored by selecting complete.

Large files are read/written in the engine through bounded entries/chunks.
Renderer IPC carries only options, summaries and bounded text pages, never archive
bytes. The viewer uses text nodes and accessible tables; markup and remote URLs
are never interpreted or loaded. Main serializes operations and rejects export
while drafts or uncertain native mutations exist. Dialog cancellation creates no
file. New export files publish a fully fsynced same-directory temporary through an
exclusive hard link; existing destinations are preserved. A crash before publication
may leave an unselected temporary file, never a partial selected archive; imports commit all data or none and can be safely retried.
