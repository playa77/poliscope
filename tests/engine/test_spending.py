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

from poliscope_engine.contracts.spending import SpendObserve, SpendConfigure, UsageObservation, CatalogEstimate


def observe(ledger, b, **fields):
    return ledger.request(SpendObserve(action='observe', binding=b, observation=UsageObservation(source='response', **fields)))


def sent(ledger, b, amount='0.06'):
    assert ledger.request(reserve(b, amount)).status == 'reserved'
    assert ledger.request(SpendTransition(action='uncertain', binding=b)).status == 'uncertain'


def test_actual_replaces_estimate_exactly_and_survives_restart(tmp_path):
    path = tmp_path/'ledger.db'; ledger = Spending(path); b = binding()
    catalog = CatalogEstimate(input_bound=100, output_bound=20, prompt_rate='0.00001', completion_rate='0.00002', source='catalog-fixture', observed_at='2026-10-26T00:00:00Z')
    assert ledger.request(reserve(b, '0.06').model_copy(update={'catalog':catalog})).catalog_estimate == '0.0014'
    ledger.request(SpendTransition(action='uncertain', binding=b))
    before = observe(ledger, b, input_tokens=7, reasoning_tokens=3)
    assert before.actual_cost is None and before.profile_total == '0.06'
    assert before.unresolved_requests == 1
    actual = observe(ledger, b, actual_cost='0.000000123456789123')
    assert actual.profile_total == '0.000000123456789123'
    assert actual.catalog_estimate == '0.0014'
    assert actual.usage.input_tokens == 7 and actual.usage.reasoning_tokens == 3
    assert actual.unresolved_requests == 0
    assert observe(ledger, b, actual_cost='0.000000123456789123').profile_total == actual.profile_total
    ledger.close(); ledger = Spending(path)
    try:
        result = ledger.request(SpendTransition(action='status', binding=b))
        assert result.actual_cost == '0.000000123456789123'
        assert ledger.request(reserve(binding('second'), '0.09')).status == 'reserved'
    finally: ledger.close()


def test_unknown_cancelled_and_late_metadata_cannot_false_zero_or_double_charge(tmp_path):
    ledger = Spending(tmp_path/'ledger.db'); b = binding()
    try:
        sent(ledger, b)
        assert observe(ledger, b, output_tokens=5).profile_total == '0.06'
        assert ledger.request(SpendTransition(action='no-send',binding=b)).status == 'conflict'
        late = SpendObserve(action='observe',binding=b,observation=UsageObservation(source='generation-metadata',generation_id='gen-late',actual_cost='0.02'))
        assert ledger.request(late).profile_total == '0.02'
        assert ledger.request(late).profile_total == '0.02'
        assert observe(ledger, b, total_tokens=9).profile_total == '0.02'
        assert observe(ledger, b, actual_cost='0').status == 'conflict'
        assert ledger.request(SpendTransition(action='complete',binding=b)).profile_total == '0.02'
        assert ledger.request(reserve(binding('next'),'0.08')).profile_total == '0.1'
    finally: ledger.close()


def test_actual_overrun_is_recorded_and_blocks_new_dispatch(tmp_path):
    ledger = Spending(tmp_path/'ledger.db'); b = binding()
    try:
        sent(ledger, b)
        result = observe(ledger, b, actual_cost='0.12')
        assert result.profile_total == '0.12'
        assert ledger.request(reserve(binding('next'),'0.000001')).status == 'denied'
        configure = SpendConfigure(action='configure',binding=b,turn_limit='0.20',session_limit='0.20',profile_limit='0.20')
        assert ledger.request(configure).profile_total == '0.12'
        q = reserve(binding('next'),'0.08').model_copy(update={'turn_limit':'0.20','session_limit':'0.20','profile_limit':'0.20'})
        assert ledger.request(q).status == 'reserved'
        ledger.request(configure.model_copy(update={'profile_limit':'0.01'}))
        assert ledger.request(SpendTransition(action='status',binding=b)).profile_total == '0.2'
        assert ledger.request(q.model_copy(update={'binding':binding('third'),'profile_limit':'0.01'})).status == 'denied'
    finally: ledger.close()


def test_reported_zero_is_distinct_from_missing_actual(tmp_path):
    ledger = Spending(tmp_path/'ledger.db'); b = binding()
    try:
        sent(ledger, b)
        assert observe(ledger, b).actual_cost is None
        result = observe(ledger, b, actual_cost='0')
        assert result.actual_cost == '0' and result.profile_total == '0'
        assert ledger.request(reserve(binding('next'),'0.1')).status == 'reserved'
    finally: ledger.close()


def test_observation_requires_exact_sent_binding_and_retains_conflicting_facts(tmp_path):
    ledger = Spending(tmp_path/'ledger.db'); b = binding()
    try:
        assert observe(ledger,b,actual_cost='0').status == 'missing'
        ledger.request(reserve(b))
        assert observe(ledger,b,actual_cost='0').status == 'conflict'
        ledger.request(SpendTransition(action='uncertain',binding=b))
        assert observe(ledger,b,generation_id='one',input_tokens=5).status == 'uncertain'
        assert observe(ledger,b,generation_id='two',actual_cost='0').status == 'conflict'
        assert observe(ledger,b,input_tokens=6).status == 'conflict'
        assert observe(ledger,b.model_copy(update={'payload_sha256':'c'*64}),actual_cost='0').status == 'conflict'
        assert ledger.request(SpendTransition(action='status',binding=b)).actual_cost is None
    finally: ledger.close()


def test_two_simultaneous_point_six_estimates_under_one_allowance(tmp_path):
    path=tmp_path/'ledger.db';Spending(path).close()
    def run(index):
        ledger=Spending(path)
        try:return ledger.request(reserve(binding(str(index)), '0.6').model_copy(update={'turn_limit':'1','session_limit':'1','profile_limit':'1'})).status
        finally:ledger.close()
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(run,range(2)))
    assert sorted(results)==['denied','reserved']


def test_catalog_is_immutable_and_cannot_exceed_reserved_policy(tmp_path):
    ledger=Spending(tmp_path/'ledger.db'); b=binding()
    c=CatalogEstimate(input_bound=100,output_bound=50,prompt_rate='0.001',completion_rate='0.002',source='fixture',observed_at='now')
    q=reserve(b).model_copy(update={'catalog':c})
    try:
        assert ledger.request(q).status=='denied'
        assert ledger.request(SpendTransition(action='status',binding=b)).status=='missing'
        q=q.model_copy(update={'catalog':c.model_copy(update={'prompt_rate':'0.000001','completion_rate':'0.000002'})})
        assert ledger.request(q).catalog_estimate=='0.0002'
        assert ledger.request(q).status=='reserved'
        assert ledger.request(q.model_copy(update={'catalog':None})).status=='conflict'
        assert ledger.request(q.model_copy(update={'catalog':c})).status=='conflict'
    finally:ledger.close()


def test_conflicting_higher_actual_is_counted_and_both_observations_retained(tmp_path):
    ledger=Spending(tmp_path/'ledger.db');b=binding()
    try:
        sent(ledger,b)
        observe(ledger,b,generation_id='one',actual_cost='0.01')
        higher=observe(ledger,b,generation_id='one',actual_cost='0.12')
        assert higher.status=='conflict' and higher.reconciliation_conflict
        assert higher.profile_total=='0.12'
        assert ledger.db.execute('SELECT COUNT(*) FROM observation_events').fetchone()[0]==2
        assert ledger.request(reserve(binding('next'),'0.000001')).status=='denied'
        assert observe(ledger,b,actual_cost='0.001').profile_total=='0.12'
    finally:ledger.close()


def test_denied_dispatch_can_explicitly_reconfigure_without_erasing_previous_charges(tmp_path):
    ledger=Spending(tmp_path/'ledger.db');b=binding()
    try:
        sent(ledger,b,'0.1')
        second=binding('second')
        assert ledger.request(reserve(second)).status=='denied'
        result=ledger.request(SpendConfigure(action='configure',binding=second,turn_limit='0.2',session_limit='0.2',profile_limit='0.2'))
        assert result.status=='configured' and result.profile_total=='0.1'
        q=reserve(second).model_copy(update={'turn_limit':'0.2','session_limit':'0.2','profile_limit':'0.2'})
        assert ledger.request(q).profile_total=='0.14'
    finally:ledger.close()


def test_cancelled_outcome_survives_restart_and_late_actual(tmp_path):
    path=tmp_path/'ledger.db';ledger=Spending(path);b=binding()
    sent(ledger,b)
    assert observe(ledger,b,outcome='cancelled',generation_id='gen-cancel',cached_tokens=2).actual_cost is None
    ledger.close();ledger=Spending(path)
    try:
        status=ledger.request(SpendTransition(action='status',binding=b))
        assert status.usage.outcome=='cancelled' and status.profile_total=='0.06'
        result=ledger.request(SpendObserve(action='observe',binding=b,observation=UsageObservation(source='generation-metadata',generation_id='gen-cancel',actual_cost='0.02')))
        assert result.usage.outcome=='cancelled' and result.usage.cached_tokens==2
        assert result.profile_total=='0.02'
    finally:ledger.close()

from poliscope_engine.contracts.spending import SpendHistory, SpendOrigin


def test_durable_usage_history_is_profile_scoped_paginated_and_recoverable(tmp_path):
    path=tmp_path/'ledger.db';ledger=Spending(path)
    origin=SpendOrigin(endpoint='https://openrouter.ai/api/v1',provider_kind='openrouter',allowed_models=['fixture/model'])
    for i in range(66):
        b=binding('dispatch_'+str(i))
        ledger.request(reserve(b,'0.000001').model_copy(update={'origin':origin}))
    ledger.close();ledger=Spending(path)
    try:
        page=ledger.request(SpendHistory(action='history',binding=binding('probe')))
        assert len(page.records)==64 and page.history_before=='dispatch_2'
        assert page.records[0].binding.dispatch_id=='dispatch_65'
        assert page.records[0].origin==origin
        older=ledger.request(SpendHistory(action='history',binding=binding('probe'),before_dispatch=page.history_before))
        assert len(older.records)==2 and older.history_before is None
        assert older.records[-1].binding.dispatch_id=='dispatch_0'
        other=binding('probe').model_copy(update={'profile_id':'other'})
        assert ledger.request(SpendHistory(action='history',binding=other,lookup_dispatch='dispatch_0')).records==[]
        record=older.records[0]
        ledger.request(SpendTransition(action='uncertain',binding=record.binding))
        assert observe(ledger,record.binding,generation_id='recoverable',actual_cost='0.0000001').actual_cost=='0.0000001'
        changed=reserve(record.binding,'0.000001').model_copy(update={'origin':origin.model_copy(update={'endpoint':'https://other.invalid'})})
        assert ledger.request(changed).status=='conflict'
    finally:ledger.close()


def test_legacy_reservations_remain_counted_and_visible_as_unrecoverable(tmp_path):
    ledger=Spending(tmp_path/'ledger.db');b=binding()
    try:
        ledger.request(reserve(b))
        ledger.db.execute('DELETE FROM dispatch_records') # exact pre-WP-048 storage shape
        status=ledger.request(SpendHistory(action='history',binding=binding('probe')))
        assert status.legacy_requests==1 and status.profile_total=='0.04'
        assert status.records==[]
    finally:ledger.close()
