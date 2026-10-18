"""Cold historical reads of synthetic retained evidence, with no numerical service."""
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import pytest
from poliscope_engine.contracts.history import HistoryRequest
from poliscope_engine.history import read, serve, HistoryFailure
from poliscope_engine.storage.store import Store


def fixture(name):
    return json.loads(next(c['frame'] for c in json.loads(Path('contracts/fixtures.json').read_text())
                           if c['name'] == 'evidence:' + name))['result']


def saved():
    summary = fixture('incomplete')
    payload = dict(history_schema=1, summary=summary)
    for collection in ('outputs', 'findings', 'sources', 'assumptions', 'traces'):
        payload[collection] = fixture(collection)['page']['items']
    return payload


@pytest.fixture
def archive(tmp_path):
    payload = saved()
    request = HistoryRequest(history_protocol=1, context=payload['summary']['context'],
                             result_id=payload['summary']['result_id'], collection='summary', offset=0, limit=1)
    with Store(tmp_path) as store:
        with store.transaction():
            store.add_context('authorized', '{}')
            store.retain_evidence('authorized', request.result_id, json.dumps(payload))
        yield store.path, request, store


def test_cold_subprocess_reads_live_wal_without_engine_or_cache(archive):
    path, request, _ = archive
    before = path.read_bytes()
    process = subprocess.run([sys.executable, '-I', '-m', 'poliscope_engine.history',
                              '--database', str(path), '--context-id', 'authorized',
                              '--grant', request.model_dump_json()], input=request.model_dump_json() + '\n',
                             text=True, capture_output=True, timeout=5, check=True)
    response = json.loads(process.stdout)
    assert response['mode'] == 'stored_historical'
    assert response['result'] == saved()['summary']
    assert process.stderr == ''
    assert path.read_bytes() == before


def test_pages_and_exact_precision(archive):
    path, grant, _ = archive
    for collection in ('outputs', 'findings', 'sources', 'assumptions', 'traces'):
        actual = []
        offset = 0
        while True:
            request = grant.model_copy(update=dict(collection=collection, offset=offset))
            response = read(path, 'authorized', grant, request)
            page = response.result.page
            actual.extend(item.model_dump() for item in page.items)
            if page.next_cursor is None:
                break
            offset = int(page.next_cursor)
        assert actual == saved()[collection]
    assert saved()['outputs'][0]['observation']['value']['value'] == '125.0000000000000000000000001'


@pytest.mark.parametrize('field,value', [('result_id', 'other'), ('context', fixture('incomplete')['context'] | {'branch_id': 'other'})])
def test_grants_deny_cross_result_and_context_before_open(archive, field, value):
    _, grant, _ = archive
    request = HistoryRequest.model_validate(grant.model_dump() | {field: value})
    with pytest.raises(HistoryFailure, match='ACCESS_DENIED'):
        read(Path('/nonexistent'), 'authorized', grant, request)


@pytest.mark.parametrize('alteration', ['version', 'foreign', 'schema', 'view'])
def test_rejects_unknown_or_altered_database_without_repair(archive, alteration):
    path, grant, store = archive
    store.close()
    with sqlite3.connect(path) as db:
        if alteration == 'version': db.execute('PRAGMA user_version=999')
        if alteration == 'foreign': db.execute('PRAGMA application_id=0')
        if alteration == 'schema': db.execute('DROP TRIGGER immutable_evidence_update')
        if alteration == 'view':
            db.execute('DROP TABLE evidence')
            db.execute("CREATE VIEW evidence AS SELECT 'authorized' AS context_id, 'x' AS id, load_extension('bad') AS payload")
    before = path.read_bytes()
    with pytest.raises(HistoryFailure, match='UNREADABLE_HISTORY'):
        read(path, 'authorized', grant, grant)
    assert before == path.read_bytes()
    # Fixture closes are idempotent for SQLite connections.


@pytest.mark.parametrize('payload', ['{}', '{"history_schema":999}', 'null', '"NaN"'])
def test_invalid_retained_data_is_not_forwarded(tmp_path, payload):
    request = HistoryRequest(history_protocol=1, context=fixture('incomplete')['context'], result_id='bad', collection='summary', offset=0, limit=1)
    with Store(tmp_path) as store:
        with store.transaction():
            store.add_context('authorized', '{}')
            store.retain_evidence('authorized', 'bad', payload)
        with pytest.raises(HistoryFailure, match='INVALID_EVIDENCE'):
            read(store.path, 'authorized', request, request)


@pytest.mark.parametrize('frame', [b'{}\n', b'\xff\n', b'x' * 1048577, b'{}', b'{"operation":"world.apply"}\n'])
def test_bad_frames_have_bounded_safe_errors(archive, frame):
    path, grant, _ = archive
    output = io.BytesIO()
    serve(io.BytesIO(frame), output, path, 'authorized', grant)
    assert json.loads(output.getvalue()) == dict(history_protocol=1, error='INVALID_REQUEST')


def test_absent_store_never_created(tmp_path):
    grant = HistoryRequest(history_protocol=1, context=fixture('incomplete')['context'], result_id='missing', collection='summary', offset=0, limit=1)
    with pytest.raises(HistoryFailure, match='UNREADABLE_HISTORY'):
        read(tmp_path / 'missing.sqlite3', 'authorized', grant, grant)
    assert not list(tmp_path.iterdir())


def test_wrong_stored_binding_missing_result_and_offset(archive):
    path, grant, _ = archive
    with pytest.raises(HistoryFailure, match='NOT_FOUND'):
        read(path, 'different-storage-context', grant, grant)
    with pytest.raises(HistoryFailure, match='INVALID_EVIDENCE'):
        changed = grant.model_copy(update={'context': grant.context.model_copy(update={'revision_id': 'wrong'})})
        read(path, 'authorized', changed, changed)
    with pytest.raises(HistoryFailure, match='INVALID_REQUEST'):
        read(path, 'authorized', grant, grant.model_copy(update={'offset': 1}))
