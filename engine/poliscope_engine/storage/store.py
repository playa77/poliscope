"""Versioned, data-only storage with explicit transactions and immutable records.

The caller supplies Electron's absolute userData directory. No current-directory
or home-directory fallback can accidentally open a different civilization store.
This module owns no numerical engine imports or application mutation handlers.
"""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from typing import Iterator

APPLICATION_ID = 0x504F4C49
SCHEMA_VERSION = 2
MAX_TEXT_BYTES = 1024 * 1024


class StorageError(ValueError):
    """A bounded storage request violates the storage contract."""


def database_path(user_data: Path) -> Path:
    user_data = Path(user_data)
    if not user_data.is_absolute():
        raise StorageError('user-data directory must be absolute')
    return user_data / 'poliscope.sqlite3'


def _key(value: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value.encode('utf-8')) <= 512:
        raise StorageError('identifier must contain 1–512 UTF-8 bytes')
    return value


def _reject_constant(value: str) -> None:
    raise ValueError(f'non-JSON constant: {value}')


def _json(value: str) -> str:
    if not isinstance(value, str) or len(value.encode('utf-8')) > MAX_TEXT_BYTES:
        raise StorageError('JSON exceeds the 1 MiB storage bound')
    try:
        # Preserve the original text, including exact decimal strings. Reject
        # non-JSON constants accepted by Python's default decoder.
        json.loads(value, parse_constant=_reject_constant)
    except (ValueError, RecursionError) as exc:
        raise StorageError('invalid data-only JSON') from exc
    return value


_SCHEMA = (
    'CREATE TABLE storage_versions (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)',
    "INSERT INTO storage_versions VALUES (1, strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
    '''CREATE TABLE contexts (
        id TEXT PRIMARY KEY NOT NULL,
        metadata TEXT NOT NULL CHECK(json_valid(metadata))
    ) STRICT''',
    '''CREATE TABLE records (
        context_id TEXT NOT NULL REFERENCES contexts(id),
        kind TEXT NOT NULL, id TEXT NOT NULL,
        payload TEXT NOT NULL CHECK(json_valid(payload)),
        PRIMARY KEY(context_id, kind, id)
    ) STRICT''',
    '''CREATE TABLE evidence (
        context_id TEXT NOT NULL REFERENCES contexts(id),
        id TEXT NOT NULL, payload TEXT NOT NULL CHECK(json_valid(payload)),
        PRIMARY KEY(context_id, id)
    ) STRICT''',
    '''CREATE TABLE operations (
        context_id TEXT NOT NULL REFERENCES contexts(id),
        id TEXT NOT NULL, binding TEXT NOT NULL CHECK(json_valid(binding)),
        outcome TEXT NOT NULL CHECK(json_valid(outcome)),
        PRIMARY KEY(context_id, id)
    ) STRICT''',
    '''CREATE TABLE caches (
        context_id TEXT NOT NULL REFERENCES contexts(id),
        id TEXT NOT NULL, payload TEXT NOT NULL CHECK(json_valid(payload)),
        PRIMARY KEY(context_id, id)
    ) STRICT''',
) + tuple(
    f'''CREATE TRIGGER immutable_{table}_{action.lower()} BEFORE {action} ON {table}
        BEGIN SELECT RAISE(ABORT, 'immutable retained record'); END'''
    for table in ('contexts', 'records', 'evidence', 'operations', 'storage_versions')
    for action in ('UPDATE', 'DELETE')
)


_SCHEMA_V1 = _SCHEMA
_MIGRATION_V2 = (
    'CREATE TABLE recovery_metadata (id TEXT PRIMARY KEY NOT NULL, payload TEXT NOT NULL CHECK(json_valid(payload))) STRICT',
    "INSERT INTO storage_versions VALUES (2, strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
)
_SCHEMA = _SCHEMA_V1 + _MIGRATION_V2


def check_schema(connection, *, supported=(1, 2)):
    """Trusted schemas only; usable without opening a writer or loading models."""
    version = connection.execute('PRAGMA user_version').fetchone()[0]
    if connection.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID or version not in supported:
        raise StorageError('unsupported schema; preserve original and use a compatible reader')
    expected = sqlite3.connect(':memory:')
    try:
        for statement in (_SCHEMA_V1 if version == 1 else _SCHEMA):
            expected.execute(statement)
        query = "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
        if connection.execute(query).fetchall() != expected.execute(query).fetchall():
            raise StorageError('storage schema differs; preserve original')
        if connection.execute('SELECT version FROM storage_versions ORDER BY version').fetchall() != [(v,) for v in range(1, version + 1)]:
            raise StorageError('invalid storage version history')
        if connection.execute('PRAGMA quick_check').fetchall() != [('ok',)] or connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise StorageError('corrupt database; preserve original and select a verified backup')
        return version
    finally:
        expected.close()


class Store:
    """One thread-affine connection. Only transaction() may delimit writes.

    SQLite serializes concurrent transactions. Electron must additionally enforce
    its single-instance lock before opening this store; SQLite locks alone do not
    implement application ownership. Public primitives require an active write
    transaction so callers can atomically retain records, evidence and outcomes.
    """

    @property
    def in_write_transaction(self) -> bool:
        """Whether this connection can currently see its own uncommitted writes."""
        return self._writing

    def revision_catalogue_rows(self):
        """Bounded immutable branch journal discovery; no caches/private payloads."""
        cursor = self._connection.execute(
            "SELECT r.context_id, r.kind, r.id, r.payload FROM records AS r "
            "WHERE r.kind GLOB 'branch:*' AND r.id = "
            "(SELECT MAX(latest.id) FROM records AS latest "
            "WHERE latest.context_id=r.context_id AND latest.kind=r.kind) "
            "ORDER BY r.context_id, r.kind")
        rows, size = [], 0
        for row in cursor:
            size += len(row[3].encode('utf-8'))
            if len(rows) >= 1000 or size > MAX_TEXT_BYTES:
                raise StorageError('branch catalogue exceeds discovery limit')
            rows.append(row)
        return rows

    def __init__(self, user_data: Path):
        self.path = database_path(user_data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, isolation_level=None, timeout=1.0)
        self._writing = False
        try:
            self._connection.execute('PRAGMA foreign_keys=ON')
            # Check identity before changing an existing file's journal mode.
            self._check_identity()
            if self._connection.execute('PRAGMA journal_mode=WAL').fetchone()[0] != 'wal':
                raise StorageError('WAL unavailable')
            self._connection.execute('PRAGMA synchronous=FULL')
            with self.transaction():
                # Recheck under the write lock in case another opener initialized.
                self._check_identity()
                version = self._connection.execute('PRAGMA user_version').fetchone()[0]
                if version == 0:
                    for statement in _SCHEMA:
                        self._connection.execute(statement)
                    self._connection.execute(f'PRAGMA application_id={APPLICATION_ID}')
                    self._connection.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
            self._check_schema()
        except BaseException:
            self._connection.close()
            raise

    def _check_identity(self) -> None:
        app_id = self._connection.execute('PRAGMA application_id').fetchone()[0]
        version = self._connection.execute('PRAGMA user_version').fetchone()[0]
        tables = self._connection.execute(
            "SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
        if version == 0 and app_id == 0 and not tables:
            return
        if app_id != APPLICATION_ID or version != SCHEMA_VERSION:
            raise StorageError('unsupported or foreign database; preserve original and use a compatible reader')

    def _check_schema(self) -> None:
        check_schema(self._connection, supported=(SCHEMA_VERSION,))

    @contextmanager
    def transaction(self) -> Iterator[None]:
        if self._writing:
            raise StorageError('nested transactions are unsupported')
        self._connection.execute('BEGIN IMMEDIATE')
        self._writing = True
        try:
            yield
            self._connection.execute('COMMIT')
        except BaseException:
            if self._connection.in_transaction:
                self._connection.execute('ROLLBACK')
            raise
        finally:
            self._writing = False

    def _require_transaction(self) -> None:
        if not self._writing or not self._connection.in_transaction:
            raise StorageError('write requires an explicit transaction')

    def add_context(self, context_id: str, metadata: str) -> None:
        self._require_transaction()
        self._connection.execute('INSERT INTO contexts VALUES (?,?)', (_key(context_id), _json(metadata)))

    def read_context(self, context_id: str) -> str | None:
        row = self._connection.execute('SELECT metadata FROM contexts WHERE id=?',
                                       (_key(context_id),)).fetchone()
        return row[0] if row else None

    def record_page(self, context_id: str, kind: str, *, after: str | None = None,
                    limit: int = 100, descending: bool = False) -> list[tuple[str, str]]:
        """Bounded immutable-record index; journal keys use zero-padded sequence IDs."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise StorageError('invalid page limit')
        if type(descending) is not bool:
            raise StorageError('invalid page order')
        params = [_key(context_id), _key(kind)]
        predicate = ''
        if after is not None:
            predicate = ' AND id ' + ('<' if descending else '>') + ' ?'
            params.append(_key(after))
        params.append(limit)
        order = 'DESC' if descending else 'ASC'
        return self._connection.execute(
            'SELECT id,payload FROM records WHERE context_id=? AND kind=?' + predicate +
            ' ORDER BY id ' + order + ' LIMIT ?', params).fetchall()

    def add_record(self, context_id: str, kind: str, record_id: str, payload: str) -> None:
        self._require_transaction()
        self._connection.execute('INSERT INTO records VALUES (?,?,?,?)',
                                 (_key(context_id), _key(kind), _key(record_id), _json(payload)))

    def read_record(self, context_id: str, kind: str, record_id: str) -> str | None:
        row = self._connection.execute('SELECT payload FROM records WHERE context_id=? AND kind=? AND id=?',
                                       (_key(context_id), _key(kind), _key(record_id))).fetchone()
        return row[0] if row else None

    def retain_evidence(self, context_id: str, evidence_id: str, payload: str) -> None:
        self._require_transaction()
        self._connection.execute('INSERT INTO evidence VALUES (?,?,?)',
                                 (_key(context_id), _key(evidence_id), _json(payload)))

    def read_evidence(self, context_id: str, evidence_id: str) -> str | None:
        row = self._connection.execute('SELECT payload FROM evidence WHERE context_id=? AND id=?',
                                       (_key(context_id), _key(evidence_id))).fetchone()
        return row[0] if row else None

    def operation_outcome(self, context_id: str, operation_id: str, binding: str) -> str | None:
        """Call before head checks. Binding is the caller's canonical request JSON.

        It includes operation, civilization/branch, original revision and payload;
        a reused ID with a different binding fails, rather than replaying a result.
        """
        binding = _json(binding)
        row = self._connection.execute('SELECT binding,outcome FROM operations WHERE context_id=? AND id=?',
                                       (_key(context_id), _key(operation_id))).fetchone()
        if row and row[0] != binding:
            raise StorageError('operation ID is bound to a different request')
        return row[1] if row else None

    def complete_operation(self, context_id: str, operation_id: str, binding: str, outcome: str) -> None:
        self._require_transaction()
        _json(outcome)
        previous = self.operation_outcome(context_id, operation_id, binding)
        if previous is not None:
            if previous != outcome:
                raise StorageError('completed operation outcome is immutable')
            return
        self._connection.execute('INSERT INTO operations VALUES (?,?,?,?)',
                                 (_key(context_id), _key(operation_id), binding, outcome))

    def cache(self, context_id: str, cache_id: str, payload: str) -> None:
        self._require_transaction()
        self._connection.execute('INSERT INTO caches VALUES (?,?,?) ON CONFLICT(context_id,id) DO UPDATE SET payload=excluded.payload',
                                 (_key(context_id), _key(cache_id), _json(payload)))

    def clear_caches(self) -> None:
        self._require_transaction()
        self._connection.execute('DELETE FROM caches')

    def backup(self, destination: Path) -> Path:
        """Create a new backup, never overwrite a prior backup or active store."""
        if self._writing:
            raise StorageError('backup requires a committed transaction boundary')
        destination = Path(destination)
        if not destination.is_absolute():
            raise StorageError('backup path must be absolute')
        # Exclusive creation also rejects aliases/symlinks to an existing DB.
        with destination.open('xb'):
            pass
        target = None
        try:
            target = sqlite3.connect(destination)
            self._connection.backup(target)
            target.close()
            return destination
        except BaseException:
            if target is not None:
                target.close()
            destination.unlink(missing_ok=True)
            raise

    def close(self) -> None:
        if self._writing:
            raise StorageError('cannot close inside transaction')
        self._connection.close()

    def __enter__(self) -> 'Store':
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
