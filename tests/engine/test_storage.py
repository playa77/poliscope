"""Synthetic storage fixtures; expectations use independent SQL and reopen reads."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from poliscope_engine.storage import StorageError, Store, database_path
from poliscope_engine.storage.store import APPLICATION_ID


@pytest.fixture
def store(tmp_path):
    with Store(tmp_path / 'user-data') as value:
        yield value


def seed(store):
    with store.transaction():
        store.add_context('civilization:1/branch:1', '{"civilization":"1","branch":"1"}')


CTX = 'civilization:1/branch:1'
EXACT = '{"value":"0.000000000000000000000000001","coverage":"known","source":"synthetic:1"}'
BINDING = '{"operation":"apply","revision":"rev:1","payload":{"choice":"synthetic"}}'
OUTCOME = '{"revision":"rev:2","result_id":"result:2"}'


def test_user_data_selection(tmp_path):
    assert database_path(tmp_path) == tmp_path / 'poliscope.sqlite3'
    with pytest.raises(StorageError):
        Store(Path('relative'))


def test_durable_settings_and_atomic_evidence_reopen(store):
    seed(store)
    assert store._connection.execute('PRAGMA foreign_keys').fetchone() == (1,)
    assert store._connection.execute('PRAGMA journal_mode').fetchone() == ('wal',)
    assert store._connection.execute('PRAGMA synchronous').fetchone() == (2,)
    with store.transaction():
        store.add_record(CTX, 'revision-input', 'rev:2', EXACT)
        store.retain_evidence(CTX, 'result:2', EXACT)
        store.complete_operation(CTX, 'op:1', BINDING, OUTCOME)
        store.cache(CTX, 'query:1', '{"disposable":true}')
    with store.transaction():
        store.clear_caches()
    with sqlite3.connect(store.path) as independent:
        assert independent.execute('SELECT count(*) FROM caches').fetchone() == (0,)
        assert independent.execute('SELECT payload FROM evidence').fetchone() == (EXACT,)
        assert independent.execute('SELECT binding,outcome FROM operations').fetchone() == (BINDING, OUTCOME)
    with Store(store.path.parent) as reopened:
        assert reopened.read_record(CTX, 'revision-input', 'rev:2') == EXACT
        assert reopened.read_evidence(CTX, 'result:2') == EXACT
        assert reopened.operation_outcome(CTX, 'op:1', BINDING) == OUTCOME
        assert reopened.read_evidence('other-context', 'result:2') is None


@pytest.mark.parametrize('failure', ['exception', 'foreign-key', 'duplicate', 'disk-full'])
def test_failed_transaction_keeps_old_state(store, failure):
    seed(store)
    if failure == 'disk-full':
        # A real SQLite allocation failure, not a mocked commit outcome.
        pages = store._connection.execute('PRAGMA page_count').fetchone()[0]
        store._connection.execute(f'PRAGMA max_page_count={pages}')
    with pytest.raises((RuntimeError, sqlite3.Error)):
        with store.transaction():
            store.add_record(CTX, 'revision', 'new', '{}')
            store.retain_evidence(CTX, 'new', '{}')
            store.complete_operation(CTX, 'new', BINDING, OUTCOME)
            if failure == 'exception':
                raise RuntimeError('synthetic interruption')
            if failure == 'foreign-key':
                store.add_record('absent', 'revision', 'new', '{}')
            if failure == 'duplicate':
                store.add_record(CTX, 'revision', 'new', '{}')
            if failure == 'disk-full':
                store.add_record(CTX, 'revision', 'big', json.dumps('x' * 900_000))
    assert store.read_record(CTX, 'revision', 'new') is None
    assert store.read_evidence(CTX, 'new') is None
    assert store.operation_outcome(CTX, 'new', BINDING) is None
    assert store._connection.execute('SELECT count(*) FROM contexts').fetchone() == (1,)


def test_writes_explicit_nested_transaction_and_close_rejected(store):
    with pytest.raises(StorageError, match='explicit'):
        store.add_context('x', '{}')
    with store.transaction():
        with pytest.raises(StorageError, match='nested'):
            with store.transaction():
                pass
        with pytest.raises(StorageError, match='close'):
            store.close()
        store.add_context('x', '{}')
    # Transaction remains usable after a handled nested failure.
    with store.transaction():
        store.add_context('y', '{}')


def test_operation_binding_and_replay(store):
    seed(store)
    assert store.operation_outcome(CTX, 'op:1', BINDING) is None
    with store.transaction():
        store.complete_operation(CTX, 'op:1', BINDING, OUTCOME)
        store.complete_operation(CTX, 'op:1', BINDING, OUTCOME)
    assert store.operation_outcome(CTX, 'op:1', BINDING) == OUTCOME
    with pytest.raises(StorageError, match='different request'):
        store.operation_outcome(CTX, 'op:1', '{"revision":"new-head"}')
    with pytest.raises(StorageError, match='immutable'):
        with store.transaction():
            store.complete_operation(CTX, 'op:1', BINDING, '{}')
    with store.transaction():
        store.add_context('other', '{}')
        store.complete_operation('other', 'op:1', '{}', '{}')
    assert store.operation_outcome(CTX, 'op:1', BINDING) == OUTCOME


@pytest.mark.parametrize('table', ['contexts', 'records', 'evidence', 'operations', 'storage_versions'])
@pytest.mark.parametrize('action', ['UPDATE', 'DELETE'])
def test_retained_tables_are_immutable(store, table, action):
    seed(store)
    with store.transaction():
        store.add_record(CTX, 'archive', 'model:1', '{}')
        store.retain_evidence(CTX, 'result:1', '{}')
        store.complete_operation(CTX, 'op:1', BINDING, OUTCOME)
    column = 'version' if table == 'storage_versions' else 'id'
    sql = f'UPDATE {table} SET {column}={column}' if action == 'UPDATE' else f'DELETE FROM {table}'
    with pytest.raises(sqlite3.IntegrityError, match='immutable'):
        with store.transaction():
            store._connection.execute(sql)


def test_backup_includes_live_wal_and_never_overwrites(store, tmp_path):
    seed(store)
    with store.transaction():
        store.add_record(CTX, 'revision', 'rev:2', EXACT)
        store.retain_evidence(CTX, 'result:2', EXACT)
        store.complete_operation(CTX, 'op:1', BINDING, OUTCOME)
    assert Path(str(store.path) + '-wal').stat().st_size > 0
    destination = tmp_path / 'backup.sqlite3'
    assert store.backup(destination) == destination
    with sqlite3.connect(destination) as backup:
        assert backup.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert backup.execute('PRAGMA application_id').fetchone() == (APPLICATION_ID,)
        assert backup.execute('PRAGMA user_version').fetchone() == (2,)
        assert backup.execute('SELECT payload FROM evidence').fetchone() == (EXACT,)
        assert backup.execute('SELECT outcome FROM operations').fetchone() == (OUTCOME,)
    before = destination.read_bytes()
    with pytest.raises(FileExistsError):
        store.backup(destination)
    assert destination.read_bytes() == before
    with pytest.raises(FileExistsError):
        store.backup(store.path)
    with store.transaction():
        with pytest.raises(StorageError, match='boundary'):
            store.backup(tmp_path / 'pending.sqlite3')
    assert not (tmp_path / 'pending.sqlite3').exists()


@pytest.mark.parametrize('variant', ['foreign', 'future', 'truncated'])
def test_unsupported_databases_preserved(tmp_path, variant):
    path = database_path(tmp_path)
    if variant == 'truncated':
        with Store(tmp_path):
            pass
        with sqlite3.connect(path) as conn:
            conn.execute('DROP TRIGGER immutable_evidence_delete')
    else:
        with sqlite3.connect(path) as conn:
            conn.execute('CREATE TABLE external (id INTEGER)')
            if variant == 'future':
                conn.execute(f'PRAGMA application_id={APPLICATION_ID}')
                conn.execute('PRAGMA user_version=999')
    before = path.read_bytes()
    with pytest.raises(StorageError):
        Store(tmp_path)
    assert path.read_bytes() == before


@pytest.mark.parametrize('payload', ['NaN', '{"v":Infinity}', '{', '"' + 'x' * 1048576 + '"'])
def test_invalid_or_oversized_json_rejected(store, payload):
    seed(store)
    with pytest.raises(StorageError):
        with store.transaction():
            store.retain_evidence(CTX, 'bad', payload)
    assert store.read_evidence(CTX, 'bad') is None


def test_sqlite_writer_lock_does_not_interleave(store):
    seed(store)
    with Store(store.path.parent) as second:
        second._connection.execute('PRAGMA busy_timeout=10')
        with store.transaction():
            store.add_record(CTX, 'revision', 'first', '{}')
            with pytest.raises(sqlite3.OperationalError, match='locked'):
                with second.transaction():
                    second.add_record(CTX, 'revision', 'second', '{}')
        with second.transaction():
            second.add_record(CTX, 'revision', 'second', '{}')
    assert store.read_record(CTX, 'revision', 'first') == '{}'
    assert store.read_record(CTX, 'revision', 'second') == '{}'


def test_process_exit_discards_uncommitted_changes(store):
    seed(store)
    script = '''
import os, sys
from pathlib import Path
from poliscope_engine.storage import Store
store = Store(Path(sys.argv[1]))
with store.transaction():
    store.add_record('civilization:1/branch:1', 'revision', 'interrupted', '{}')
    os._exit(17)
'''
    result = subprocess.run([sys.executable, '-c', script, str(store.path.parent)], timeout=10)
    assert result.returncode == 17
    with Store(store.path.parent) as reopened:
        assert reopened.read_record(CTX, 'revision', 'interrupted') is None
        assert reopened._connection.execute('PRAGMA integrity_check').fetchone() == ('ok',)


def test_automatic_sqlite_rollback_cannot_turn_later_writes_into_autocommits(store):
    seed(store)
    pages = store._connection.execute('PRAGMA page_count').fetchone()[0]
    store._connection.execute(f'PRAGMA max_page_count={pages}')
    with pytest.raises(sqlite3.OperationalError):
        with store.transaction():
            with pytest.raises(sqlite3.OperationalError, match='full'):
                store.add_record(CTX, 'revision', 'big', json.dumps('x' * 900_000))
            # SQLITE_FULL may roll back the entire transaction itself. A handled
            # error must not allow the next write to run in SQLite autocommit.
            with pytest.raises(StorageError, match='explicit transaction'):
                store.add_context('accidental-autocommit', '{}')
    assert store._connection.execute('SELECT count(*) FROM contexts').fetchone() == (1,)
