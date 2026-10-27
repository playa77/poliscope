"""Trusted data-only recovery. No implicit upgrades, resets or backup overwrite."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import time
from .storage.store import (Store, StorageError, database_path, check_schema,
                            _MIGRATION_V2, SCHEMA_VERSION)
from .contracts.recovery import RecoveryReply, RecoveryBranch


@contextmanager
def reader(path):
    path = Path(path)
    if not path.is_absolute() or not path.is_file():
        raise StorageError('unreadable source')
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, isolation_level=None, timeout=1)
    connection.enable_load_extension(False)
    connection.execute('PRAGMA query_only=ON')
    connection.execute('PRAGMA trusted_schema=OFF')
    connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 2 * 1024 * 1024)
    deadline = time.monotonic() + 10
    connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
    try:
        connection.execute('BEGIN')
        check_schema(connection)
        yield connection
    finally:
        connection.close()


@contextmanager
def historical_service(path):
    """Reuse bounded storage reads, never construct a Store writer/registry."""
    from .revisions import Revisions
    with reader(path) as connection:
        store = Store.__new__(Store)
        store.path, store._connection, store._writing = Path(path), connection, False
        service = Revisions.__new__(Revisions)
        service.store, service.registry = store, None
        # Data-only verification markers contain no evaluator or registry.
        service._verified_evidence = {}
        raw = store.read_context('revision-service:v1')
        if raw is None:
            raise StorageError('no revision catalogue')
        service.data_store_id = json.loads(raw)['data_store_id']
        yield service


def backup(source, destination):
    """SQLite snapshot includes WAL, accepted evidence, operations and redactions.

    Separate classified private stores and keys are deliberately not enumerated.
    """
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError('backup destination already exists')
    if any(Path(str(destination) + suffix).exists() for suffix in ('-wal', '-shm', '-journal')):
        raise StorageError('select a new backup path without journal sidecars')
    if not destination.is_absolute():
        raise StorageError('absolute destination required')
    created = False
    try:
        with reader(source) as connection:
            with destination.open('xb'):
                created = True
            target = sqlite3.connect(destination, isolation_level=None)
            try:
                deadline = time.monotonic() + 15
                def progress(*_):
                    if time.monotonic() > deadline:
                        raise StorageError('backup deadline exceeded')
                connection.backup(target, pages=128, progress=progress, sleep=0.01)
                check_schema(target)
            finally:
                target.close()
        with destination.open('rb') as stream:
            os.fsync(stream.fileno())
        if os.name != 'nt':
            descriptor = os.open(destination.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        return destination
    except BaseException:
        if created:
            destination.unlink(missing_ok=True)
        raise


def restore(source, directory):
    """Restore only to an empty/new sandbox, preserving the original and backup."""
    directory = Path(directory)
    if not directory.is_absolute() or (directory.exists() and any(directory.iterdir())):
        raise StorageError('select a new empty restore folder')
    directory.mkdir(parents=True, exist_ok=True)
    return backup(source, database_path(directory))


def migrate_schema(source, backup_file, *, fault=None):
    """v1 -> v2 adds recovery metadata only. Backup precedes transactional DDL.

    Interruption before COMMIT leaves schema 1 readable. Interruption after COMMIT
    leaves schema 2 readable. Original confirmed rows are never rewritten.
    """
    backup(source, backup_file)
    connection = sqlite3.connect(source, isolation_level=None, timeout=1)
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA synchronous=FULL')
        connection.execute('BEGIN IMMEDIATE')
        version = check_schema(connection)
        if version != 1:
            raise StorageError('schema already current; no migration required')
        for statement in _MIGRATION_V2:
            connection.execute(statement)
        connection.execute('INSERT INTO recovery_metadata VALUES (?,?)', ('schema-1-to-2', json.dumps(dict(from_schema=1, to_schema=2, backup_method='sqlite_backup_api', history='preserved', status='committed_with_schema_transaction'))))
        if fault:
            fault(connection)
        connection.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
        check_schema(connection, supported=(SCHEMA_VERSION,))
        connection.execute('COMMIT')
    except BaseException:
        if connection.in_transaction:
            connection.execute('ROLLBACK')
        raise
    finally:
        connection.close()


def inspect(source):
    from .numeric import RUNTIME_ID
    with historical_service(source) as service:
        branches = []
        for state in service.catalogue():
            record = service.read(state.context)
            versions = record.inputs.versions
            branches.append(RecoveryBranch(context=state.context, name=state.name,
                model_id=versions.model_id, numeric_runtime_id=versions.numeric_runtime_id,
                execution='requires_explicit_migration' if versions.model_id == 'workspace:unmodeled' and versions.numeric_runtime_id == RUNTIME_ID else 'unavailable'))
        return RecoveryReply(status='complete', schema_version=check_schema(service.store._connection),
            detail='Retained history, read only; no results reproduced. Select a revision to inspect. Edits and computation are disabled.', branches=branches)


def read_revision(source, context, offset=0):
    from .archives import display_item
    from .contracts.archives import ArchiveRevision, ArchiveEvidence
    with historical_service(source) as service:
        record = service.read(context)
        try:
            evidence = ArchiveEvidence(saved=service.evidence(context))
        except (ValueError, KeyError):
            evidence = None
        item = ArchiveRevision(id=context.revision_id, civilization_id=context.civilization_id,
            branch_id=context.branch_id, parent_id=record.parent_id, inputs=record.inputs,
            alternatives=record.decision.alternatives, selected_id=record.decision.selected_id, evidence=evidence)
        heading, rows, next_offset = display_item(item, offset)
        rows = [r.model_copy(update={'detail': r.detail.replace('with privacy projection identities', 'with original retained identities')}) for r in rows]
        if evidence is None:
            rows = [r.model_copy(update={'detail': 'Historical evidence unavailable or unreadable; no recomputation attempted.'}) if r.label == 'Evidence' else r for r in rows]
        return RecoveryReply(status='complete', detail=heading + '; retained historical data, not freshly reproduced.',
            rows=rows, next_offset=next_offset)
