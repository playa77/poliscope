"""Independent local expectations; no snapshot regeneration or social assertions."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.provisioning import ProvisioningRequest, ProcedureEdit, ProvisioningCoverage
from poliscope_engine.domains.provisioning.exploration import interview, preview, report, baseline
from poliscope_engine.numeric import Registry
from test_provisioning_chain import request, units, claim, choice, requirement, set_opening


def dto(data=None):
    return ProvisioningRequest.model_validate(data or request())


def edit(plan, phase='eat', scope='west', procedure='priority', order=None):
    card = interview(plan, units(), phase, scope)
    option = next(o for o in card.alternatives if o.procedure == procedure)
    return ProcedureEdit(baseline_digest=card.baseline_digest, scope_id=scope, phase_id=phase,
        option_id=option.definition.id, claim_order=order or card.claim_ids)


def test_explicit_alternatives_have_no_default_and_do_not_adopt_source_policies():
    for phase, scope in [('make','east'),('deliver','east'),('store','west'),('eat','west')]:
        card = interview(dto(), units(), phase, scope)
        assert card.selected_option_id is None
        assert {o.procedure for o in card.alternatives} == {'priority','all_or_nothing'}
        for o in card.alternatives:
            assert o.definition.origin == 'authored'
            assert o.definition.evidence == 'hypothetical'
            assert o.definition.source_decision_id is None
            assert 'supplied order' in o.definition.original_text


def competing():
    data = request()
    use = data['phases'][-1]
    use['claims'].append(claim('small', 'stored', 2))
    use['choices'].append(choice('small', [requirement('rights', kind='entitlement')]))
    use['claim_order'].append('small')
    return dto(data)


def test_two_competing_groups_change_distribution_only_under_explicit_order():
    plan = competing()
    before = plan.model_dump_json()
    first = preview(plan, units(), edit(plan)).report
    reverse = preview(plan, units(), edit(plan, order=['small','eat-food'])).report
    assert [(i.claim_id,i.actual) for i in first.indicators[-2:]] == [('eat-food','2'),('small','0')]
    assert [(i.claim_id,i.actual) for i in reverse.indicators[-2:]] == [('eat-food','0'),('small','2')]
    assert first.indicators[-2].constraints[0].available_before == '2'
    assert first.indicators[-2].constraints[0].available_after == '0'
    assert plan.model_dump_json() == before


def test_indivisible_large_claim_is_skipped_without_inventing_supply():
    plan = competing()
    result = preview(plan, units(), edit(plan, procedure='all_or_nothing'))
    assert [(i.actual,i.unmet) for i in result.report.indicators[-2:]] == [('0','6'),('2','0')]
    assert result.candidate_digest != result.edit.baseline_digest
    assert result.report.evaluation.request.phases[-1].procedure == 'all_or_nothing'


@pytest.mark.parametrize('aid,expected', [('raw','0'),('truck','14')])
def test_physical_shortfall_and_distant_surplus_are_distinct(aid, expected):
    data = request()
    set_opening(data, aid, 0)
    result = report(dto(data), units())
    freight = result.indicators[1]
    assert freight.actual == '0' and freight.unmet == '10'
    assert freight.available_before == expected
    assert freight.access == 'allowed'
    assert freight.constraints[0].kind == 'transport'
    assert freight.constraints[0].available_before == ('0' if aid == 'truck' else '10')


def test_denied_access_is_distinct_from_physical_supply_and_entitlement():
    data = request()
    data['phases'][-1]['choices'][0]['access'] = 'denied'
    local = report(dto(data), units()).indicators[-1]
    assert (local.available_before,local.actual,local.unmet,local.access) == ('3','0','6','denied')
    assert local.constraints[0].kind == 'entitlement'
    assert local.constraints[0].available_after == '2'


@pytest.mark.parametrize('stage',range(4))
@pytest.mark.parametrize('missing',['procedure','access','funding'])
def test_unknown_is_never_fabricated_zero_and_future_stages_are_not_evaluated(stage, missing):
    data = request()
    phase = data['phases'][stage]
    c = phase['routes' if phase['kind']=='freight' else 'choices'][0]
    if missing == 'procedure': phase['procedure'] = None
    if missing == 'access': c['access'] = 'unknown'
    if missing == 'funding': c['funding_known'] = False
    result = report(dto(data), units())
    assert result.status == 'unresolved' and result.evaluation.batch is None
    for i, row in enumerate(result.indicators):
        if i < stage: assert row.status == 'resolved' and row.actual is not None
        else:
            assert row.actual is None and row.unmet is None and row.posting_ids == []
            assert row.status == ('unresolved' if i == stage else 'not_evaluated')
    assert missing in result.indicators[stage].missing


@pytest.mark.parametrize('change', ['stock','order','access','yield','provenance','period','hold'])
def test_any_material_base_change_invalidates_prior_preview(change):
    data = request()
    prior = edit(dto(data))
    if change == 'stock': set_opening(data,'raw',10)
    if change == 'order': data['phases'][0]['procedure'] = 'all_or_nothing'
    if change == 'access': data['phases'][-1]['choices'][0]['access'] = 'denied'
    if change == 'yield': data['phases'][0]['choices'][0]['loss_per_unit'] = '0.2'
    if change == 'provenance': data['phases'][0]['source_refs'].append('new:source')
    if change == 'period': data['period_id'] = 'day:1'
    if change == 'hold': data['phases'][0]['reservations'] = [dict(id='h',account_id='raw',claim_id='make-food',amount='1')]
    with pytest.raises(AccountError,match='stale_provisioning_preview'): preview(dto(data), units(), prior)


def test_unit_semantics_are_part_of_preview_identity():
    plan = dto()
    original = units()
    changed = Registry((replace(original.units[0], scale=Decimal(2)), *original.units[1:]))
    with pytest.raises(AccountError,match='stale_provisioning_preview'): preview(plan, changed, edit(plan))


@pytest.mark.parametrize('field,value,code', [
    ('scope_id','east','incompatible_provisioning_scope'),
    ('phase_id','absent','unknown_provisioning_phase'),
    ('option_id','society:DEC-001/option/A','unknown_provisioning_option'),
    ('claim_order',['absent'],'invalid_claim_order'),
    ('claim_order',['eat-food','eat-food'],'invalid_claim_order')])
def test_conflicting_or_foreign_edits_are_rejected(field,value,code):
    plan = dto()
    bad = ProcedureEdit.model_validate(edit(plan).model_dump() | {field:value})
    with pytest.raises(AccountError,match=code): preview(plan, units(), bad)


def test_multi_scope_phase_requires_a_joint_procedure_not_local_authority():
    data = request()
    data['batch']['accounts'].append(dict(data['batch']['accounts'][4],id='other-store',scope_id='east'))
    data['resources'].append(dict(account_id='other-store',resource_id='food'))
    data['phases'][-1]['claims'].append(claim('east-user','other-store',1))
    data['phases'][-1]['choices'].append(choice('east-user'))
    data['phases'][-1]['claim_order'].append('east-user')
    for scope in ['east','west']:
        with pytest.raises(AccountError,match='incompatible_provisioning_scope'):
            interview(dto(data), units(), 'eat', scope)


def test_exact_account_and_flow_evidence_stays_linked_and_detached():
    plan = dto()
    before = plan.model_dump_json()
    result = report(plan, units())
    assert [(r.actual,r.unmet) for r in result.indicators] == [('20','10'),('4','6'),('3','7'),('2','4')]
    assert [r.scope_id for r in result.indicators] == ['east','east','west','west']
    assert all(r.period_id == 'day:0' and r.unit_id == 'kg' for r in result.indicators)
    posts = {p.id:p for p in result.evaluation.batch.postings}
    for row in result.indicators:
        assert row.posting_ids
        assert all(posts[p].claim_id == row.claim_id for p in row.posting_ids)
        assert row.source_refs == ['authored:provisioning-chain-v1']
    move = result.evaluation.phases[1].evidence.movements[0]
    assert posts[move.import_posting_id].amount == '4'
    assert result.evaluation.phases[0].evidence.actuals[0].loss == '2'
    result.indicators.clear()
    result.evaluation.request.phases.clear()
    assert plan.model_dump_json() == before
    assert len(report(plan,units()).indicators) == 4


def test_malformed_nested_dtos_and_excess_edit_fields_cannot_bypass_validation():
    plan = dto()
    plan.phases[-1].claim_order.append('extra')
    with pytest.raises(AccountError,match='invalid_claim_order'): report(plan,units())
    data = edit(dto()).model_dump() | {'outputs': []}
    with pytest.raises(ValidationError): ProcedureEdit.model_validate(data)


def test_coverage_reconciles_every_branch_leaf_decision_and_alternative():
    root = Path(__file__).resolve().parents[2]
    inventory = json.loads((root/'docs/roadmap/execution/society/inventory.json').read_text())
    coverage = ProvisioningCoverage.model_validate_json((root/'content/provisioning/coverage-v1.json').read_text())
    assert coverage.source_revision == inventory['revision']
    assert coverage.source_archive_digest == inventory['archive_digest']
    rows = {r.source_id:r for r in coverage.entries}
    assert len(rows) == len(coverage.entries)
    expected = {b['id'] for b in inventory['domains'][0]['branches']}
    expected |= {l['id'] for b in inventory['domains'][0]['branches'] for l in b['leaves']}
    expected |= {'society:'+d['id'] for d in inventory['decisions']+inventory['system_decisions']}
    assert set(rows) == expected and len(rows) == 38
    for branch in inventory['domains'][0]['branches']:
        for leaf in branch['leaves']: assert rows[leaf['id']].documents == leaf['documents']
    for source in inventory['decisions']:
        row = rows['society:'+source['id']]
        assert row.option_refs == source['option_ids']
        assert row.documents == source['amends']
        assert row.evidence_status == 'unreviewed' and not row.static_available
    assert all(not r.transition_available and r.next_research_task for r in coverage.entries)
    assert coverage.activation == 'not_activated'
    for sid in ['society:domain/01/1/2','society:domain/01/1/4','society:domain/01/3/2','society:domain/01/3/3']:
        assert rows[sid].status == 'unsupported' and not rows[sid].static_available


@pytest.mark.parametrize('phase,scope', [('make','east'),('deliver','east'),('store','west'),('eat','west')])
def test_each_phase_previews_the_real_indivisible_chain_without_other_edits(phase,scope):
    plan = dto()
    result = preview(plan,units(),edit(plan,phase=phase,scope=scope,procedure='all_or_nothing'))
    candidate = result.report.evaluation.request
    assert candidate.batch == plan.batch and candidate.resources == plan.resources
    for old, new in zip(plan.phases,candidate.phases):
        assert old.model_dump() | {'procedure':new.procedure} == new.model_dump()
        assert new.procedure == ('all_or_nothing' if old.id == phase else old.procedure)
    assert result.report.indicators[-1].actual == '0'


def test_explicit_procedure_can_resolve_an_unanswered_phase():
    data = request()
    data['phases'][-1].update(procedure=None,claim_order=[])
    plan = dto(data)
    assert report(plan,units()).indicators[-1].actual is None
    result = preview(plan,units(),edit(plan))
    assert result.report.status == 'resolved' and result.report.indicators[-1].actual == '2'
    assert plan.phases[-1].procedure is None


def test_report_keeps_holds_distinct_from_free_supply_without_deducting_twice():
    data = request()
    data['phases'][0]['reservations'] = [dict(id='hold',account_id='raw',claim_id='make-food',amount='20')]
    result = report(dto(data),units())
    production = result.indicators[0]
    assert (production.available_before,production.actual,production.unmet) == ('0','20','10')
    stage = result.evaluation.phases[0].evidence
    assert stage.request.batch.reservations[0].amount == '20'
    assert sum(Decimal(p.amount) for p in stage.batch.postings if p.reservation_id == 'hold') == 20
    assert next(a for a in stage.accounts.accounts if a.account_id == 'raw').outstanding_reserved == '0'


def test_unexecuted_ports_remain_declared_with_unknown_measured_balances():
    data = request()
    data['phases'][0]['procedure'] = None
    result = report(dto(data),units())
    use = result.indicators[-1]
    assert use.status == 'not_evaluated' and use.actual is None
    assert use.constraints[0].account_id == 'rights'
    assert use.constraints[0].available_before is None and use.constraints[0].available_after is None


@pytest.mark.parametrize('change,code', [
    ('missing','provisioning_coverage_inventory'),('duplicate','provisioning_coverage_inventory'),
    ('foreign','provisioning_coverage_inventory'),('revision','provisioning_source_drift'),
    ('documents','provisioning_source_references'),('alternative','provisioning_source_references'),
    ('availability','provisioning_coverage_availability'),('source-model','provisioning_source_activation')])
def test_content_validation_rejects_research_drift_and_implicit_source_activation(change,code):
    from poliscope_engine.domains.provisioning.coverage import validate_coverage
    root = Path(__file__).resolve().parents[2]
    source = json.loads((root/'docs/roadmap/execution/society/inventory.json').read_text())
    data = json.loads((root/'content/provisioning/coverage-v1.json').read_text())
    assert len(validate_coverage(data,source).entries) == 38
    if change == 'missing': data['entries'].pop()
    if change == 'duplicate': data['entries'].append(deepcopy(data['entries'][0]))
    if change == 'foreign': data['entries'][0]['source_id'] = 'society:foreign'
    if change == 'revision': data['source_revision'] = 'foreign'
    if change == 'documents': data['entries'][1]['documents'].clear()
    if change == 'alternative': next(r for r in data['entries'] if r['source_id']=='society:DEC-001')['option_refs'].pop()
    if change == 'availability': data['entries'][0]['evidence_status'] = 'unreviewed'
    if change == 'source-model': next(r for r in data['entries'] if r['source_id']=='society:DEC-001')['evidence_status'] = 'hypothetical'
    with pytest.raises(AccountError,match=code): validate_coverage(data,source)


def test_indicator_retains_full_union_of_bounded_provenance():
    data = request()
    phase = data['phases'][0]
    phase['source_refs'] = ['phase:source/'+str(i) for i in range(100)]
    phase['claims'][0]['source_refs'] = ['claim:source/'+str(i) for i in range(100)]
    phase['choices'][0]['source_refs'] = ['choice:source/'+str(i) for i in range(100)]
    result = report(dto(data),units())
    assert len(result.indicators[0].source_refs) == 300
    assert set(result.indicators[0].source_refs) == set(phase['source_refs']+phase['claims'][0]['source_refs']+phase['choices'][0]['source_refs'])
