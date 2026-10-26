"""Independent fixed-microUSD and concurrency checks for production reservations."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
import pytest
from poliscope_engine.spending import Spending
from poliscope_engine.contracts.spending import SpendBinding, SpendReserve, SpendTransition


def binding(dispatch='a', **kwargs):
    return SpendBinding(dispatch_id=dispatch, turn_id='turn', session_id='session', profile_id='profile', payload_sha256='a'*64, binding_sha256='b'*64, currency='USD', estimate_version='explicit-bounded-exposure-v1', **kwargs)


def reserve(b, exposure='0.04', **kwargs):
    return SpendReserve(action='reserve', binding=b, exposure=exposure, turn_limit='0.10', session_limit='0.10', profile_limit='0.10', **kwargs)


def test_atomic_scopes_replay_conflicts_amend_and_no_send(tmp_path):
    ledger=Spending(tmp_path/'ledger.db')
    try:
        a=reserve(binding())
        assert ledger.request(a).status=='reserved'
        assert ledger.request(a).exposure=='0.04'
        assert ledger.request(a.model_copy(update={'exposure':'0.05'})).status=='conflict'
        assert ledger.request(a.model_copy(update={'binding':a.binding.model_copy(update={'payload_sha256':'c'*64})})).status=='conflict'
        assert ledger.request(a.model_copy(update={'action':'amend','exposure':'0.06'})).status=='reserved'
        assert ledger.request(reserve(binding('b'),'0.05')).status=='denied'
        assert ledger.request(SpendTransition(action='no-send',binding=a.binding)).status=='no-send'
        assert ledger.request(reserve(binding('b'),'0.10')).status=='reserved'
        assert ledger.request(a).status=='conflict' # amended, then released; cannot resurrect
    finally: ledger.close()


@pytest.mark.parametrize('scope',['turn_id','session_id','profile_id'])
def test_each_scope_independently_limits_and_limits_cannot_expand(tmp_path,scope):
    ledger=Spending(tmp_path/'ledger.db')
    try:
        assert ledger.request(reserve(binding('a'),'0.06')).status=='reserved'
        b=binding('b').model_copy(update={k:'other' for k in ['turn_id','session_id','profile_id'] if k!=scope})
        assert ledger.request(reserve(b,'0.05')).status=='denied'
        assert ledger.request(reserve(binding('c'),'0.05').model_copy(update={'turn_limit':'1','session_limit':'1','profile_limit':'1'})).status=='denied'
    finally: ledger.close()


@pytest.mark.parametrize('state',['uncertain','complete'])
def test_restart_retains_exposure_and_refuses_release_or_amend(tmp_path,state):
    path=tmp_path/'ledger.db';ledger=Spending(path);b=binding()
    assert ledger.request(reserve(b,'0.06')).status=='reserved'
    assert ledger.request(SpendTransition(action='uncertain',binding=b)).status=='uncertain'
    if state=='complete': assert ledger.request(SpendTransition(action='complete',binding=b)).status=='complete'
    ledger.close();ledger=Spending(path)
    try:
        assert ledger.request(SpendTransition(action='status',binding=b)).status==state
        assert ledger.request(SpendTransition(action='no-send',binding=b)).status=='conflict'
        assert ledger.request(reserve(b,'0.07').model_copy(update={'action':'amend'})).status=='conflict'
        assert ledger.request(reserve(binding('b'),'0.05')).status=='denied'
    finally: ledger.close()


def test_concurrent_independent_connections_cannot_overspend(tmp_path):
    path=tmp_path/'ledger.db';Spending(path).close()
    def run(index):
        ledger=Spending(path)
        try:return ledger.request(reserve(binding(str(index)),'0.04')).status
        finally:ledger.close()
    with ThreadPoolExecutor(max_workers=6) as pool: results=list(pool.map(run,range(12)))
    assert results.count('reserved')==2
    assert results.count('denied')==10


def test_exact_smallest_unit_and_zero_unknown_blocked(tmp_path):
    ledger=Spending(tmp_path/'ledger.db')
    try:
        assert ledger.request(reserve(binding(),'0')).status=='denied'
        assert ledger.request(reserve(binding(),'0.000001')).exposure=='0.000001'
        assert ledger.request(SpendTransition(action='status',binding=binding('missing'))).status=='missing'
    finally:ledger.close()
