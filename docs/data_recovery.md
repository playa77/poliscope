# Backup, portability and recovery

Keep real civilizations, keys and transcripts outside the repository. Application
profiles live under Electron's OS user-data directory; civilization stores are in
the folder you select. A per-user installation directory is separate from both.
Never delete a selected store to fix a startup or compatibility error.

Before upgrading, use the recovery workspace's **Back up selected database**.
This produces a checked SQLite backup of confirmed history, accepted evidence and
operation replay identities. It excludes separate private-note/rationale payloads
and keys. It is not a complete profile backup. Keep a securely stored copy of any
private material you separately need; do not export keys into a backup receipt.
Do not copy an open SQLite database file alone: its WAL may contain confirmed data.

Use **Export portable history** for a shareable data-only archive. The default
projection removes private notes/rationale and private identifiers throughout
old snapshots, alternatives and derived evidence. Explicit opt-ins include active
private notes/rationale from all revisions. Transcripts, attachments and credentials
remain excluded. Evidence-reduced export omits listed measurement reports/traces;
those values become unavailable rather than recomputed by a newer model.

**Import portable history** opens stored historical inspection, leaving saved
worlds unchanged. Files are validated for schema, paths, types, hashes, limits and
references before a SQLite transaction; imported text and packs never execute.
Inspect the retained revision/model/runtime identities and omission/redaction
labels. Use an explicit compatible model-migration branch to resume execution;
readability is separate from numerical execution compatibility. A newer app or a
matching filename alone cannot establish compatibility.

If the engine cannot start, use read-only historical inspection in the recovery
workspace. Stored accepted results/traces survive disposable cache eviction and
are labeled retained, not freshly reproduced. An absent runtime must not invent
numbers. Unreadable schema or corrupted input produces a diagnostic and preserves
the original. **Restore selected backup into new folder** never downgrades or
replaces the original store. Open that new folder and verify its confirmed head.

On a crash, save failure, cancelled transition or uncertain IPC reply, reopen and
inspect the last confirmed revision. Completed mutation retries resolve their
operation ID before checking a new head, so retrying an identical operation does
not create a second commit. Changed payload/context is rejected. Do not manually
edit SQLite or replay a proposal with a new ID to conceal an uncertain outcome.
An export may exist after an uncertain reply: inspect it and select a fresh output
path rather than overwriting it. Report the visible diagnostic if recovery fails.

For rollback, close the app, launch the retained old installation and open a
compatible pre-upgrade backup restored into a **new** folder. An old application
cannot automatically reverse a database migration. Keep the newer installation,
original store and receipts until recovery is verified. Installers neither migrate
nor erase user data; uninstalling an app is separate from deleting a civilization.

Deleting private payloads/transcripts removes active copies and derivatives under
the app's deletion rules. Immutable public simulation history remains. Older
backups, exports, WAL/filesystem recovery and already shared copies may retain
material; dispose of those separately. Secure physical erasure is not promised.
