"""One-shot trusted data-only reader. Never opens a writer or imports a model."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
from pydantic import ValidationError
from .contracts.history import HistoryRequest, HistoryResult, SavedEvidence
from .storage.store import APPLICATION_ID, SCHEMA_VERSION, _SCHEMA

MAX_BYTES = 1024 * 1024


class HistoryFailure(ValueError):
    pass


def read(database: Path, context_id: str, grant: HistoryRequest, request: HistoryRequest):
    # The launch grant is main-owned. No path, SQL or context enumeration in IPC.
    if request.context != grant.context or request.result_id != grant.result_id:
        raise HistoryFailure('ACCESS_DENIED')
    database = Path(database)
    if not database.is_absolute() or not database.is_file():
        raise HistoryFailure('UNREADABLE_HISTORY')
    connection = None
    expected = sqlite3.connect(':memory:')
    try:
        connection = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=1)
        connection.enable_load_extension(False)
        connection.execute('PRAGMA query_only=ON')
        connection.execute('PRAGMA trusted_schema=OFF')
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 2 * MAX_BYTES)
        connection.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 65536)
        # Bound hostile schema/data execution as well as returned byte counts.
        budget = 1000
        def progress():
            nonlocal budget
            budget -= 1
            return int(budget <= 0)
        connection.set_progress_handler(progress, 1000)
        connection.execute('BEGIN')
        if (connection.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID
                or connection.execute('PRAGMA user_version').fetchone()[0] != SCHEMA_VERSION):
            raise HistoryFailure('UNREADABLE_HISTORY')
        for statement in _SCHEMA:
            expected.execute(statement)
        query = "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name LIMIT 100"
        if connection.execute(query).fetchall() != expected.execute(query).fetchall():
            raise HistoryFailure('UNREADABLE_HISTORY')
        if connection.execute('SELECT version FROM storage_versions ORDER BY version LIMIT 2').fetchall() != [(1,)]:
            raise HistoryFailure('UNREADABLE_HISTORY')
        row = connection.execute('SELECT payload FROM evidence WHERE context_id=? AND id=?',
                                 (context_id, request.result_id)).fetchone()
        if row is None:
            raise HistoryFailure('NOT_FOUND')
        if not isinstance(row[0], str) or len(row[0].encode('utf-8')) > MAX_BYTES:
            raise HistoryFailure('INVALID_EVIDENCE')
        saved = SavedEvidence.model_validate_json(row[0])
        summary = saved.summary
        if summary.context != request.context or summary.result_id != request.result_id:
            raise HistoryFailure('INVALID_EVIDENCE')
        if request.collection == 'summary':
            if request.offset != 0:
                raise HistoryFailure('INVALID_REQUEST')
            result = summary
        else:
            items = getattr(saved, request.collection)
            if request.offset > len(items):
                raise HistoryFailure('INVALID_REQUEST')
            end = min(len(items), request.offset + request.limit)
            result = dict(kind='evidence_page', evidence_schema=1, context=summary.context,
                          versions=summary.versions, effective_time=summary.effective_time,
                          result_id=summary.result_id, scope_id=summary.scope_id,
                          page=dict(kind=request.collection, items=items[request.offset:end],
                                    next_cursor=str(end) if end < len(items) else None))
        return HistoryResult(history_protocol=1, mode='stored_historical', result=result)
    except (sqlite3.Error, OSError) as exc:
        raise HistoryFailure('UNREADABLE_HISTORY') from exc
    except (ValidationError, ValueError, RecursionError) as exc:
        if isinstance(exc, HistoryFailure):
            raise
        raise HistoryFailure('INVALID_EVIDENCE') from exc
    finally:
        expected.close()
        if connection is not None:
            connection.close()


def serve(source, sink, database: Path, context_id: str, grant: HistoryRequest):
    try:
        frame = source.readline(MAX_BYTES + 1)
        if len(frame) > MAX_BYTES or not frame.endswith(b'\n') or b'\r' in frame:
            raise HistoryFailure('INVALID_REQUEST')
        request = HistoryRequest.model_validate_json(frame)
        response = read(database, context_id, grant, request).model_dump_json().encode() + b'\n'
        if len(response) > MAX_BYTES:
            raise HistoryFailure('RESPONSE_TOO_LARGE')
    except (ValidationError, ValueError, UnicodeError, RecursionError) as exc:
        code = str(exc) if isinstance(exc, HistoryFailure) else 'INVALID_REQUEST'
        response = json.dumps(dict(history_protocol=1, error=code)).encode() + b'\n'
    sink.write(response)
    sink.flush()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='Trusted historical evidence reader')
    parser.add_argument('--database', required=True, type=Path)
    parser.add_argument('--context-id', required=True)
    parser.add_argument('--grant', required=True)
    args = parser.parse_args(argv)
    try:
        grant = HistoryRequest.model_validate_json(args.grant)
        if not 1 <= len(args.context_id.encode()) <= 512:
            raise ValueError()
    except (ValueError, ValidationError):
        return 2
    try:
        return serve(sys.stdin.buffer, sys.stdout.buffer, args.database, args.context_id, grant)
    except (OSError, sqlite3.Error):
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
