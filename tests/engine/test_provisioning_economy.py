"""Actual DOM-01/02 path; independent arithmetic and adversarial boundaries."""
from copy import deepcopy
from fractions import Fraction
from itertools import product
import pytest
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.provisioning_economy import ProvisioningEconomyRequest
from poliscope_engine.contracts.world import LabelValue
from poliscope_engine.domains import conformance_catalog, ConformanceError
from poliscope_engine.domains.conformance import run_case, ConformanceCase
from poliscope_engine.domains.provisioning.economy import evaluate_pair
from poliscope_engine.domains.provisioning.counterpart import (
    binding, host_registry, run_bound_case, CONTEXT, WORK, BOOK, CANDIDATE,
)
from poliscope_engine.mechanisms import MechanismError
from provisioning_economy_fixture import fixture, setup, trusted


def run(data=None):
    request, _, graph, units = setup(data)
    return evaluate_pair(request, graph=graph, units=units)


def balances(result):
    return {a.account_id: a.closing for a in result.provisioning.accounts.accounts}


def test_real_adapters_literal_oracle_and_complete_retained_evidence():
    data = fixture()
    before = deepcopy(data)
    result = run(data)
    assert data == before and result.status == 'resolved'
    assert balances(result) == data['expected']['accounts']
    assert {c.claim_id: [c.actual, c.unmet] for c in result.provisioning.accounts.claims} == data['expected']['claims']
    assert result.batch.postings[0].model_dump() == data['request']['work']['batch']['postings'][0]
    assert sum(p.id == 'prior:care' for p in result.batch.postings) == 1
    assert result.batch.reservations == result.work.batch.reservations
    assert all(p.source_refs and p.mechanism_ref for p in result.batch.postings)
    b = balances(result)
    assert sum(Fraction(b[a]) for a in ['raw', 'product', 'residual', 'receiving', 'stored']) + 1 + 1 == 20
    assert next(a for a in result.provisioning.phases[0].evidence.actuals if a.claim_id == 'make-food').loss == '1'
    assert result.provisioning.request.batch == result.work.batch
    assert result.provisioning.request.phases[-1].choices[-1].mechanism_ref == 'authored:economy-access-work-v1'
    # The same account can appear in local, region and watershed projections.
    assert len([a for a in result.batch.accounts if a.id == 'labor']) == 1
    assert result.batch.subtotals == result.request.work.batch.subtotals


def test_common_conformance_runs_actual_pair_and_typed_binding():
    request, inputs, graph, units = setup()
    registry, inputs = trusted(request, inputs, graph, units)
    catalog = conformance_catalog()
    branches = [c.branch_id for m in catalog.modules for c in m.coverage]
    case = ConformanceCase(inputs=inputs, outcome='incomplete', observations=(
        dict(node=['output', 'work', WORK], status='partial'),
        dict(node=['output', 'provision', CANDIDATE], status='partial'),
    ), trace_edges=((('output', 'work', WORK), ('input', 'provision', BOOK)),))
    result = run_case(case, catalog=catalog, mechanisms=registry, branch_ids=branches)
    assert run_bound_case(case, request=request, units=units, reviews=registry.reviews) == result
    # Partial host bindings retain incomplete status. Unmet goods remain in the full
    # paired report; no generic numerical account publication is implemented.
    assert result.accounts is None
    assert registry.bind(('authored:pair-work-mechanism', 'v1'),
        ('authored:pair-provisioning-mechanism', 'v1'), output_id=WORK, input_id=BOOK,
        world=graph.registry, scope_id='east', producer_entity_id='east-authority',
        consumer_entity_id='east-authority').kind == 'label'


def test_declarations_never_grant_review_or_execution_permission():
    request, _, graph, units = setup()
    registry = host_registry(request, graph=graph, units=units, reviews=[])
    with pytest.raises(MechanismError, match='review_required'):
        registry.activate('authored:pair-work-mechanism', 'v1', phase='static',
            world=graph.registry, scope_id='east', entity_id='east-authority')


@pytest.mark.parametrize('where', ['work', 'use', 'production', 'freight', 'storage'])
def test_unknown_inputs_withhold_complete_candidate(where):
    data = fixture()
    if where == 'work':
        data['request']['work']['activities'][0]['terms_known'] = False
    elif where == 'use':
        data['request']['use_terms'][0]['activities'][0]['eligibility'] = 'unknown'
    else:
        p = next(p for p in data['request']['chain']['phases'] if p['kind'] == where)
        p['routes' if where == 'freight' else 'choices'][0]['funding_known'] = False
    result = run(data)
    assert result.status == 'unresolved' and result.batch is None
    if where == 'work':
        assert result.provisioning is None and result.work.batch is None
    else:
        assert result.provisioning.batch is None and result.provisioning.accounts is None


def test_access_denial_preserves_available_goods_and_named_reason():
    data = fixture()
    data['request']['use_terms'][0]['activities'][0]['eligibility'] = 'denied'
    result = run(data)
    assert result.status == 'resolved' and balances(result)['stored'] == '2'
    actual = next(a for a in result.provisioning.phases[-1].evidence.actuals if a.claim_id == 'eat-food')
    assert (actual.allocated, actual.unmet, actual.reason) == ('0', '6', 'denied')


@pytest.mark.parametrize('change,code', [
    ('batch', 'counterpart_batch_mismatch'), ('period', 'counterpart_period_mismatch'),
    ('entity', 'counterpart_account_identity'), ('scope', 'counterpart_scope_identity'),
    ('resource', 'counterpart_resource_identity'), ('claimant', 'counterpart_claimant_identity'),
    ('holder', 'counterpart_holder_identity'), ('duplicate_time', 'duplicate_cohort_time_budget'),
    ('use_choice', 'counterpart_use_terms'), ('missing_terms', 'at least 1 item'),
    ('wrong_terms', 'counterpart_use_terms'), ('duplicate_phase', 'duplicate_phase'),
    ('wrong_unit', 'counterpart_time_holders'), ('wrong_rights_owner', 'invalid_economy_term_holder'),
    ('foreign_rights_scope', 'incompatible_requirement'),
])
def test_invalid_counterpart_inputs_reject_without_mutation(change, code):
    data = fixture()
    req = data['request']
    if change == 'batch': req['chain']['batch']['accounts'][0]['opening'] = '19'
    if change == 'period': req['chain']['period_id'] = 'day:1'
    if change in ('entity', 'scope', 'resource', 'holder'):
        target = {'entity':'raw', 'resource':'food', 'holder':'shared:cohort'}.get(change)
        if change == 'scope':
            next(s for s in data['inputs']['scopes'] if s['id'] == 'east')['scope_kind'] = 'community'
        else:
            next(e for e in data['inputs']['entities'] if e['id'] == target)['entity_kind'] = 'asset'
            if change == 'holder': data['inputs']['populations'] = []
    if change == 'claimant': req['chain']['phases'][0]['claims'][0]['claimant_id'] = 'food'
    if change == 'duplicate_time':
        for part in [req['work'], req['chain']]:
            part['batch']['accounts'].append(part['batch']['accounts'][5] | {'id':'duplicate:time'})
        req['work']['holders'].append(dict(account_id='duplicate:time', holder_id='shared:cohort', role='time'))
        data['inputs']['entities'].append(data['inputs']['entities'][0] | {'id':'duplicate:time', 'entity_kind':'account'})
    if change == 'use_choice': req['chain']['phases'][-1]['choices'] = [dict(claim_id='eat-food', access='allowed', access_limit='6',funding_known=True,requirements=[],outputs=[],loss_per_unit='0',mechanism_ref='forged',source_refs=[])]
    if change == 'missing_terms': req['use_terms'] = []
    if change == 'wrong_terms': req['use_terms'][0]['phase_id'] = 'missing'
    if change == 'duplicate_phase': req['chain']['phases'][1]['id'] = 'make'
    if change == 'wrong_unit':
        for part in [req['work'],req['chain']]:
            next(a for a in part['batch']['accounts'] if a['id']=='labor')['unit_id'] = 'rights'
    if change == 'wrong_rights_owner':
        req['work']['holders'][1]['holder_id'] = 'other:cohort'
        data['inputs']['entities'].append(data['inputs']['entities'][0] | {'id':'other:cohort','entity_kind':'population_cohort'})
        data['inputs']['populations'].append(dict(entity_id='other:cohort',role='fixed_input'))
    if change == 'foreign_rights_scope':
        for part in [req['work'],req['chain']]:
            next(a for a in part['batch']['accounts'] if a['id']=='rights')['scope_id'] = 'east'
    before = deepcopy(data)
    with pytest.raises((AccountError, ValueError), match=code):
        run(data)
    assert data == before


def test_independent_small_supply_and_entitlement_oracle():
    # Fixed work and upstream chain deliver exactly 2 kg; vary rights and demand.
    for rights, demand in product(range(4), range(1, 5)):
        data = fixture()
        for part in [data['request']['work'], data['request']['chain']]:
            next(a for a in part['batch']['accounts'] if a['id']=='rights')['opening'] = str(rights)
        data['request']['chain']['phases'][-1]['claims'][0]['requested'] = str(demand)
        actual = next(c for c in run(data).provisioning.accounts.claims if c.claim_id=='eat-food')
        assert (int(actual.actual), int(actual.unmet)) == (min(2, rights, demand), demand-min(2, rights, demand))


def test_independent_shared_work_and_mass_oracle():
    for care, training in product(range(2, 5), range(4)):
        data = fixture()
        for part in [data['request']['work'], data['request']['chain']]:
            part['batch']['claims'][0]['requested'] = str(care)
            part['batch']['claims'][1]['requested'] = str(training)
        result = run(data)
        claims = {c.claim_id: int(c.actual) for c in result.provisioning.accounts.claims}
        hours = 12 - care - training
        raw = min(20, 10 * (hours // 5))
        delivered = min(raw * 7 // 10, (hours - raw // 2) * 2, 10)
        stored = min(3, delivered)
        used = min(1, stored)
        assert claims == dict(care=care, training=training, **{
            'make-food':raw, 'ship-food':delivered, 'store-food':stored, 'eat-food':used})
        b = balances(result)
        assert sum(Fraction(b[a]) for a in ['raw','product','residual','receiving','stored']) + raw // 10 + used == 20


@pytest.mark.parametrize('change', ['world', 'request', 'units'])
def test_bound_conformance_rejects_stale_context(change):
    from dataclasses import replace
    from poliscope_engine.numeric import Registry
    request, inputs, graph, units = setup()
    registry, inputs = trusted(request, inputs, graph, units)
    case = ConformanceCase(inputs=inputs, outcome='incomplete', observations=(
        dict(node=['output','provision',CANDIDATE],status='partial'),))
    if change == 'world':
        rows = list(inputs.entities)
        rows[0] = rows[0].model_copy(update={'label':'Changed world context'})
        case = replace(case, inputs=inputs.model_copy(update={'entities':rows}))
    if change == 'request':
        request.use_terms[0].activities[0] = request.use_terms[0].activities[0].model_copy(
            update={'eligibility':'denied'})
    if change == 'units':
        units = Registry(tuple(replace(u, scale=u.scale * 2) if u.id == 'kg' else u for u in units.units))
    with pytest.raises(ConformanceError, match='stale_counterpart_context'):
        run_bound_case(case, request=request, units=units, reviews=registry.reviews)


@pytest.mark.parametrize('change,code', [('missing_holder','counterpart_time_holders'),
    ('missing_procedure',None), ('duplicate_claim','duplicate_identity')])
def test_additional_authority_and_procedure_boundaries(change, code):
    data = fixture()
    if change == 'missing_holder': data['request']['work']['holders'].pop(0)
    if change == 'missing_procedure':
        data['request']['work'].update(procedure=None,claim_order=[])
        assert run(data).batch is None
        return
    if change == 'duplicate_claim':
        data['request']['chain']['phases'][-1]['claims'][0]['id'] = 'care'
        data['request']['chain']['phases'][-1]['claim_order'] = ['care']
        data['request']['use_terms'][0]['activities'][0]['claim_id'] = 'care'
    with pytest.raises(ValueError, match=code): run(data)


def test_private_binding_rejects_forged_or_stale_work_book():
    request, inputs, graph, units = setup()
    registry, _ = trusted(request, inputs, graph, units)
    callbacks = {i.id:i.callback for i in registry.implementations}
    context = binding(request, graph, units)
    with pytest.raises(AccountError, match='stale_counterpart_context'):
        callbacks['authored:pair-work'](WORK, {CONTEXT: LabelValue(kind='label', value='forged')})
    with pytest.raises(AccountError, match='stale_counterpart_book'):
        callbacks['authored:pair-provisioning'](CANDIDATE, {BOOK: LabelValue(kind='label', value=context)})
    staged = callbacks['authored:pair-work'](WORK, {CONTEXT:LabelValue(kind='label', value=context)})
    first = callbacks['authored:pair-provisioning'](CANDIDATE, {BOOK:LabelValue(**staged)})
    request.use_terms[0].activities.clear()
    assert callbacks['authored:pair-provisioning'](CANDIDATE, {BOOK:LabelValue(**staged)}) == first
    assert binding(request, graph, units) != context


def test_pair_report_is_detached_and_only_validated_pairs_are_ready():
    request, _, graph, units = setup()
    result = evaluate_pair(request, graph=graph, units=units)
    result.batch.postings.clear()
    assert evaluate_pair(request, graph=graph, units=units).batch.postings
    catalog = conformance_catalog()
    assert [p.id for p in catalog.pairs if p.status == 'ready_for_conformance'] == ['pair:DOM-01:DOM-02', 'pair:DOM-01:DOM-05', 'pair:DOM-01:DOM-06', 'pair:DOM-01:DOM-07', 'pair:DOM-01:DOM-08', 'pair:DOM-01:DOM-10', 'pair:DOM-01:DOM-12', 'pair:DOM-02:DOM-03', 'pair:DOM-02:DOM-04', 'pair:DOM-02:DOM-05', 'pair:DOM-02:DOM-06', 'pair:DOM-02:DOM-07', 'pair:DOM-02:DOM-08', 'pair:DOM-03:DOM-04']


@pytest.mark.parametrize('field', ['model_id', 'numeric_runtime_id', 'catalog_id'])
def test_bound_case_rejects_foreign_runtime_and_model(field):
    request, inputs, graph, units = setup()
    registry, inputs = trusted(request, inputs, graph, units)
    inputs = inputs.model_copy(update={'versions':inputs.versions.model_copy(update={field:'foreign:v1'})})
    with pytest.raises(ConformanceError, match='counterpart_version_mismatch'):
        run_bound_case(ConformanceCase(inputs=inputs,outcome='incomplete',observations=()),
            request=request, units=units, reviews=registry.reviews)


@pytest.mark.parametrize('change,code', [('port','interface_type_mismatch'),
    ('reference','counterpart_identity_mismatch'), ('fixture','unresolved_counterpart_fixture')])
def test_real_pair_rejects_forged_conformance_declarations(change, code):
    from poliscope_engine.domains import DomainRegistry
    request, inputs, graph, units = setup()
    registry, _ = trusted(request, inputs, graph, units)
    catalog = conformance_catalog()
    modules, pairs = list(catalog.modules), list(catalog.pairs)
    if change == 'port':
        module = next(m for m in modules if m.domain == 'provisioning')
        port = next(i for i in module.interfaces if i.port_id == BOOK)
        from poliscope_engine.contracts.mechanisms import ReferenceType
        module.interfaces[module.interfaces.index(port)] = port.model_copy(
            update={'value_type':ReferenceType(kind='reference',entity_kind='account')})
    if change == 'reference':
        module = next(m for m in modules if m.domain == 'provisioning')
        port = next(i for i in module.interfaces if i.port_id == BOOK)
        port.references.pop()
    if change == 'fixture':
        from poliscope_engine.contracts.packs import Identity
        pairs[0].fixture_refs[0] = Identity(id='forged:fixture',version='v1')
    with pytest.raises(ConformanceError,match=code):
        DomainRegistry(modules,pairs).validate(world=graph.registry,mechanisms=registry,
            branch_ids=[c.branch_id for m in modules for c in m.coverage])


def test_nested_forged_contract_is_revalidated_before_any_allocation():
    from pydantic import ValidationError
    request, _, graph, units = setup()
    request.use_terms[0].activities[0].requirements.append(
        dict(account_id='rights', per_unit=2, kind='entitlement'))
    with pytest.warns(UserWarning,match='Pydantic serializer warnings'):
        with pytest.raises(ValidationError): evaluate_pair(request,graph=graph,units=units)
