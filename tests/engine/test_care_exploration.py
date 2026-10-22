"""Independent queue/time oracles, retained host context and source gaps."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from itertools import permutations
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.social_organization import CareRequest, CareEdit
from poliscope_engine.contracts.world import PartitionValueDTO
from poliscope_engine.domains.social_organization.exploration import interview, report, preview
from poliscope_engine.domains.social_organization.coverage import validate_coverage
from poliscope_engine.numeric import Registry
from poliscope_engine.world import WorldRegistry
from poliscope_engine.world.membership import WorldGraph
from test_social_organization import request, world, units
from test_economy import claim, activity
from test_law_conflict import request as law_request
from test_policies import mechanisms
from poliscope_engine.contracts.law_conflict import AdjudicationRequest
from poliscope_engine.domains.law_conflict import evaluate_adjudication

ROOT = Path(__file__).resolve().parents[2]


def dto(data=None):
    return CareRequest.model_validate(request() if data is None else data)


def context():
    return dict(graph=world(), units=units())


def edit(plan, choice='declared', **ctx):
    card = interview(plan, scope_id=plan.scope_id, **(ctx or context()))
    return CareEdit(baseline_digest=card.baseline_digest, scope_id=plan.scope_id,
                    option_id='authored:care/precedence/' + choice)


@pytest.mark.parametrize('scope', ['local', 'region'])
def test_five_hours_and_ten_people_under_both_explicit_choices(scope):
    plan = dto(request(scope)); before = plan.model_dump_json()
    card = interview(plan, scope_id=scope, **context())
    assert card.selected_option_id is None
    assert all(o.definition.origin == 'authored' and o.definition.evidence == 'hypothetical'
               and o.definition.source_decision_id is None for o in card.alternatives)
    a = preview(plan, edit=edit(plan), **context())
    b = preview(plan, edit=edit(plan, 'care-first'), **context())
    assert a.report.evaluation.population.value == b.report.evaluation.population.value == '10'
    assert [(i.actual, i.unmet) for i in a.report.evaluation.work.indicators] == [('0','4'),('3','0'),('2','0')]
    assert [(i.actual, i.unmet) for i in b.report.evaluation.work.indicators] == [('4','0'),('1','2'),('0','2')]
    result = b.report.evaluation
    assert (result.results[0].beneficiary_id, result.results[0].provider_id) == ('cohort:a', 'cohort:a')
    assert result.results[0].posting_ids == result.work.indicators[0].posting_ids
    assert result.results[0].unit_id == 'hours' and result.results[0].period_id == 'day:0'
    assert result.request == plan.model_copy(update={'work':plan.work.model_copy(
        update={'claim_order':['care','job','learning']})})
    assert a.candidate_digest != b.candidate_digest and plan.model_dump_json() == before
    assert b.candidate_digest == b.report.baseline_digest


def test_all_orders_stably_partition_care_without_sorting_ids_or_duties():
    data = request()
    data['work']['batch']['claims'].append(claim('care:z', 'time:a', 2, 'cohort:a'))
    data['work']['activities'].append(activity('care:z', 'care'))
    data['obligations'].insert(0, data['obligations'][0] | {'id':'duty:z','claim_id':'care:z'})
    for order in permutations(['job','care:z','learning','care']):
        data['work']['claim_order'] = list(order); plan = dto(data)
        result = preview(plan, edit=edit(plan, 'care-first'), **context()).report.evaluation
        care = [c for c in order if c.startswith('care')]
        other = [c for c in order if not c.startswith('care')]
        assert result.request.work.claim_order == care + other
        first = next(i for i in result.work.indicators if i.claim_id == care[0])
        second = next(i for i in result.work.indicators if i.claim_id == care[1])
        expected_first = '2' if care[0] == 'care:z' else '4'
        assert first.actual == expected_first
        assert second.actual == ('3' if expected_first == '2' else '1')
        assert all(i.actual == '0' for i in result.work.indicators if i.claim_id in other)


@pytest.mark.parametrize('unknown', ['procedure','access','terms','population','order'])
def test_unknowns_are_preserved_and_never_choose_a_procedure(unknown):
    data = request()
    if unknown == 'procedure': data['work']['procedure'] = None
    elif unknown == 'order':
        data['work']['procedure'] = None
        data['work']['claim_order'] = []
    elif unknown == 'access': data['work']['activities'][0]['eligibility'] = 'unknown'
    elif unknown == 'terms': data['work']['activities'][0]['terms_known'] = False
    else: data['population_property_id'] = 'missing'
    plan = dto(data)
    result = preview(plan, edit=edit(plan, 'care-first'), **context()).report.evaluation
    assert result.status == 'unresolved'
    if unknown == 'population':
        assert result.population.kind == 'unknown' and result.results[0].actual == '4'
    else:
        assert result.results[0].actual is None and result.results[0].unmet is None
        assert result.work.evaluation.batch is None


def test_prior_postings_and_holds_are_not_reallocated():
    data = request()
    data['work']['batch']['reservations'] = [dict(id='care:hold', account_id='time:a', claim_id='care', amount='4')]
    plan = dto(data)
    first = preview(plan, edit=edit(plan), **context()).report.evaluation
    assert first.results[0].actual == '4' and first.results[0].unmet == '0'
    data['work']['batch'] = first.work.evaluation.batch.model_dump(); plan = dto(data)
    again = preview(plan, edit=edit(plan, 'care-first'), **context()).report.evaluation
    assert again.results[0].actual_before == '4' and again.results[0].actual == '0'
    assert again.work.evaluation.batch == first.work.evaluation.batch


def test_actual_law_competes_with_previewed_care_in_identical_batch():
    data = request(); law = law_request(); data['work'] = law['administration']; plan = dto(data)
    for choice, outcomes, actual in [('declared',['upheld','capacity_blocked'],'0'),
                                     ('care-first',['capacity_blocked','capacity_blocked'],'4')]:
        result = preview(plan, edit=edit(plan, choice), **context()).report.evaluation
        law['administration'] = result.request.work.model_dump()
        legal = evaluate_adjudication(AdjudicationRequest.model_validate(law),
                                     graph=world(), mechanisms=mechanisms(), units=units())
        assert result.work == legal.administration
        assert [r.outcome for r in legal.results] == outcomes
        assert result.results[0].actual == actual
        assert result.request.obligations == plan.obligations


def test_all_or_nothing_access_and_foreign_work_are_not_overridden():
    data = request(); data['work']['procedure'] = 'all_or_nothing'
    data['work']['activities'][0]['eligibility'] = 'denied'; plan = dto(data)
    result = preview(plan, edit=edit(plan, 'care-first'), **context()).report.evaluation
    assert result.results[0].actual == '0' and result.results[0].unmet == '4'
    assert result.request.work.procedure == 'all_or_nothing'
    data['work']['batch']['accounts'][0]['scope_id'] = 'region'
    with pytest.raises(AccountError, match='incompatible_care_work_scope'):
        interview(dto(data), scope_id='local', **context())


@pytest.mark.parametrize('field', ['beneficiary','provider','arrangement','authority','obligation','claim',
    'population','source','capacity','order','terms','category','period','procedure','reservation'])
def test_complete_request_staleness(field):
    plan = dto(); old = edit(plan); data = plan.model_dump(); duty = data['obligations'][0]
    if field in ('beneficiary','provider'): duty[field+'_id'] = 'cohort:b'
    elif field == 'arrangement': duty['arrangement_id'] = 'network'
    elif field == 'authority': duty['authority_id'] = None
    elif field == 'obligation': duty['obligation_ref'] = 'changed'
    elif field == 'claim': data['work']['batch']['claims'][0]['requested'] = '3'
    elif field == 'population': data['population_property_id'] = 'missing'
    elif field == 'source': duty['source_refs'].append('changed')
    elif field == 'capacity': data['work']['batch']['accounts'][0]['opening'] = '6'
    elif field == 'order': data['work']['claim_order'].reverse()
    elif field == 'terms': data['work']['activities'][0]['terms_known'] = False
    elif field == 'category': data['work']['activities'][1]['kind'] = 'unpaid_work'
    elif field == 'period': data['work']['period_id'] = 'day:1'
    elif field == 'procedure': data['work']['procedure'] = 'all_or_nothing'
    else: data['work']['batch']['reservations'] = [dict(id='hold',account_id='time:a',claim_id='care',amount='1')]
    with pytest.raises(AccountError, match='stale_care_preview'):
        preview(dto(data), edit=old, **context())


@pytest.mark.parametrize('field', ['relationship','entity','scope','population_role','population_value','owner','unit','civilization'])
def test_complete_world_and_unit_context_bound(field):
    ctx = context(); plan = dto(); old = edit(plan, **ctx); g = ctx['graph']; w = g.registry
    if field == 'unit':
        ctx['units'] = Registry(tuple(replace(u, scale=Decimal(2)) if u.id == 'hours' else u for u in ctx['units'].units))
    else:
        fields = dict(entities=w.entities, scopes=w.scopes, values=w.values, owners=w.owners, populations=w.populations)
        edges = list(g.relationships); civ = w.civilization_id
        if field == 'relationship': edges[-1] = edges[-1].model_copy(update={'relationship_version':'changed'})
        elif field == 'entity': fields['entities'] = [e.model_copy(update={'label':'changed'}) for e in w.entities]
        elif field == 'scope': fields['scopes'] = [s.model_copy(update={'label':'changed'}) for s in w.scopes]
        elif field == 'population_role': fields['populations'] = [replace(p,role='dynamic_state') for p in w.populations]
        elif field == 'owner': fields['owners'] = [replace(o,writer_id='changed') for o in w.owners]
        elif field == 'population_value':
            raw = w.values[0].model_dump(); raw['value']['value'] = '11'
            fields['values'] = [PartitionValueDTO.model_validate(raw)]
        else:
            civ = 'changed'
            fields['entities'] = [e.model_copy(update={'id':civ}) if e.id == w.civilization_id else e for e in w.entities]
            edges = [r.model_copy(update={k:civ if getattr(r,k) == w.civilization_id else getattr(r,k)
                                         for k in ('from_id','to_id')}) for r in edges]
        ctx['graph'] = WorldGraph(WorldRegistry(civ, **fields), edges)
    with pytest.raises(AccountError, match='stale_care_preview'):
        preview(plan, edit=old, **ctx)


@pytest.mark.parametrize('identity', ['VERSION','MODEL','ECONOMY_VERSION','RUNTIME_ID','EVALUATOR_ID'])
def test_runtime_identity_bound(monkeypatch, identity):
    import poliscope_engine.domains.social_organization.exploration as module
    plan = dto(); old = edit(plan)
    monkeypatch.setattr(module, identity, 'changed')
    with pytest.raises(AccountError, match='stale_care_preview'):
        preview(plan, edit=old, **context())


def test_detachment_and_forged_nested_values():
    plan = dto(); change = edit(plan)
    result = preview(plan, edit=change, **context())
    result.edit.__dict__['option_id'] = 'changed'
    result.report.evaluation.request.obligations.clear()
    result.report.evaluation.work.indicators[0].source_refs.clear()
    assert plan == dto() and change == edit(plan)
    plan.obligations[0].__dict__['provider_id'] = 123
    with pytest.raises(ValidationError): report(plan, **context())
    change.__dict__['scope_id'] = 123
    with pytest.raises(ValidationError): preview(dto(), edit=change, **context())


@pytest.mark.parametrize('scope,option,error', [('region','declared','incompatible_care_scope'),
    ('local','foreign','unknown_care_option')])
def test_rejected_scope_and_option(scope, option, error):
    plan = dto(); change = edit(plan).model_copy(update=dict(scope_id=scope,option_id='authored:care/precedence/'+option))
    with pytest.raises(AccountError, match=error): preview(plan, edit=change, **context())


def coverage():
    return json.loads((ROOT / 'content/social-organization/coverage-v1.json').read_text())


def source():
    return json.loads((ROOT / 'docs/roadmap/execution/society/inventory.json').read_text())


def test_complete_source_inventory():
    result = validate_coverage(coverage(), source())
    assert len(result.entries) == 37
    assert sum(r.static_available for r in result.entries) == 4
    model = json.loads((ROOT / 'engine/poliscope_engine/domains/social_organization/care-v1.json').read_text())
    assert all(r.implementation_refs == [model['id'], 'authored:care/precedence']
               for r in result.entries if r.static_available)
    assert sum(r.classification == 'provenance' for r in result.entries) == 25
    assert all(not r.transition_available for r in result.entries)


@pytest.mark.parametrize('change', ['revision','digest','missing','duplicate','foreign','title','document','option',
    'classification','availability','model','scope','evidence','status','activation','transition','source_activation'])
def test_coverage_rejects_source_and_availability_drift(change):
    data = coverage(); row = data['entries'][0]
    if change == 'revision': data['source_revision'] = 'wrong'
    elif change == 'digest': data['source_archive_digest'] = 'sha256:' + '0'*64
    elif change == 'missing': data['entries'].pop()
    elif change == 'duplicate': data['entries'].append(deepcopy(row))
    elif change == 'foreign': row['source_id'] = 'society:domain/02/1'
    elif change == 'title': row['title'] = 'wrong'
    elif change == 'document': row['documents'].append('foreign.md')
    elif change == 'option': data['entries'][12]['option_refs'].append('foreign')
    elif change == 'classification': row['classification'] = 'provenance'
    elif change == 'availability': row['static_available'] = False
    elif change == 'model': row['implementation_refs'] = ['invented:model']
    elif change == 'scope': row['supported_scope_kinds'] = ['global_external']
    elif change == 'evidence': row['evidence_status'] = 'unreviewed'
    elif change == 'status': row['status'] = 'qualitative'
    elif change == 'activation': data['activation'] = 'activated'
    elif change == 'transition': row['transition_available'] = True
    else: data['entries'][12]['static_available'] = True
    with pytest.raises((AccountError, ValidationError)): validate_coverage(data, source())
