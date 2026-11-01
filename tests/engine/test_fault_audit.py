"""WP-053: real SQLite failure modes, not exceptions standing in for SQLite.

All worlds and canaries are synthetic. No system volume is filled or permission
changed: SQLite's page ceiling and query-only switch inject the actual result
codes at the persistence boundary, including SQLite's automatic rollback.
"""
import sqlite3
import pytest
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from test_revisions import (create_request, apply_request, mechanism_registry,
                            count, output)
from test_boundaries import running, confirm_request


def deny(connection, fault):
    if fault == 'full':
        pages = connection.execute('PRAGMA page_count').fetchone()[0]
        assert connection.execute(f'PRAGMA max_page_count={pages}').fetchone()[0] == pages
    else:
        connection.execute('PRAGMA query_only=ON')


def release(connection, fault):
    connection.execute('PRAGMA max_page_count=1073741823' if fault == 'full' else 'PRAGMA query_only=OFF')


@pytest.mark.parametrize('fault,code', [('full', sqlite3.SQLITE_FULL), ('readonly', sqlite3.SQLITE_READONLY)])
def test_design_save_failure_retains_history_then_exact_retry_succeeds(tmp_path, fault, code):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=mechanism_registry())
        original = service.create(create_request(service))
        request = apply_request(service, original.context)
        before = count(service)
        retained = service.evidence(original.context)
        deny(store._connection, fault)
        with pytest.raises(sqlite3.OperationalError) as caught:
            service.apply(request)
        assert caught.value.sqlite_errorcode == code
        assert not store.in_write_transaction and not store._connection.in_transaction
        assert count(service) == before
        assert service.status('apply', request) is None
        assert service.branch(original.context).context == original.context
        assert service.evidence(original.context) == retained
        release(store._connection, fault)
        saved = service.apply(request)
        advanced = service.apply(apply_request(service, saved.context, '7', 'later'))
    with Store(tmp_path) as store:
        cold = Revisions(store, registry=None)
        assert cold.apply(request) == saved  # retry after head advances, no model
        assert cold.branch(original.context).context == advanced.context
        assert output(cold.evidence(original.context)) == '6'
        assert output(cold.evidence(saved.context)) == '15'
        assert output(cold.evidence(advanced.context)) == '21'


@pytest.mark.parametrize('fault,code', [('full', sqlite3.SQLITE_FULL), ('readonly', sqlite3.SQLITE_READONLY)])
def test_timeline_save_failure_never_publishes_candidate(running, fault, code):
    service, _, opened = running
    request = confirm_request(service, opened)
    before = count(service.revisions)
    retained = service.read(opened.context)
    deny(service.store._connection, fault)
    with pytest.raises(sqlite3.OperationalError) as caught:
        service.confirm(request)
    assert caught.value.sqlite_errorcode == code
    assert count(service.revisions) == before
    assert service.status(request) is None
    assert service.read(opened.context) == retained
    assert not service.store.in_write_transaction and not service.store._connection.in_transaction
    release(service.store._connection, fault)
    saved = service.confirm(request)
    assert saved.sequence == 1
    assert service.confirm(request) == saved
