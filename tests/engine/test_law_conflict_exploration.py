"""Literal ballot/time oracles and source reconciliation; no legitimacy claims."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.law_conflict import AdjudicationRequest, AdjudicationEdit
from poliscope_engine.domains.law_conflict.exploration import interview, preview, report
from poliscope_engine.domains.law_conflict.coverage import validate_coverage
from poliscope_engine.numeric import Registry
from poliscope_engine.world import WorldRegistry
from poliscope_engine.world.membership import WorldGraph
from test_law_conflict import request, world
from test_policies import mechanisms, overlap, rule, edge
from test_economy import units, account, claim, activity, holder

ROOT = Path(__file__).resolve().parents[2]


def dto(data=None):
    return AdjudicationRequest.model_validate(request() if data is None else data)


def context():
    return dict(graph=world(), mechanisms=mechanisms(), units=units())


def edit(plan, choice='declared', **ctx):
    card = interview(plan, scope_id=plan.scope_id, **(ctx or context()))
    return AdjudicationEdit(baseline_digest=card.baseline_digest, scope_id=plan.scope_id,
        option_id='authored:adjudication/queue/' + choice)


@pytest.mark.parametrize('scope', ['local','region'])
def test_literal_queue_capacity_and_unchanged_legal_terms(scope):
    plan = dto(request(scope)); before = plan.model_dump_json()
    card = interview(plan, scope_id=scope, **context())
    assert card.selected_option_id is None
    assert all(o.definition.origin == 'authored' and o.definition.evidence == 'hypothetical'
               and o.definition.source_decision_id is None for o in card.alternatives)
    a = preview(plan, edit=edit(plan), **context())
    b = preview(plan, edit=edit(plan, 'reverse'), **context())
    assert [r.outcome for r in a.report.evaluation.results] == ['upheld','capacity_blocked']
    assert [r.outcome for r in b.report.evaluation.results] == ['capacity_blocked','dismissed']
    assert [(i.actual,i.unmet) for i in b.report.administration.indicators] == [('2','1'),('3','0'),('0','4')]
    assert b.report.evaluation.request.cases == plan.cases
    assert b.report.evaluation.request.administration.claim_order == ['case:b','admin','care']
    assert a.candidate_digest != b.candidate_digest and plan.model_dump_json() == before


def test_care_priority_and_unknown_capacity_survive_preview():
    data = request(); data['administration']['claim_order'] = ['care','admin','case:b']
    plan = dto(data)
    result = preview(plan, edit=edit(plan,'reverse'), **context()).report
    assert result.evaluation.request.administration.claim_order == ['care','case:b','admin']
    assert [r.outcome for r in result.evaluation.results] == ['capacity_blocked','capacity_blocked']
    data['administration']['procedure'] = None; plan = dto(data)
    result = preview(plan, edit=edit(plan), **context()).report
    assert all(r.outcome is None and 'unknown_case_capacity' in r.findings for r in result.evaluation.results)
    assert all(i.actual is None and i.unmet is None for i in result.administration.indicators)


@pytest.mark.parametrize('field', ['right','claimant','rationale','eligibility','disposition','work','obligation','source','policy','capacity','order','terms'])
def test_complete_request_staleness(field):
    plan = dto(); old = edit(plan); data = plan.model_dump(); case = data['cases'][0]
    if field == 'right': case['right_ref'] = 'changed'
    elif field == 'claimant': case['claimant_id'] = 'cohort:b'
    elif field == 'rationale': case['rationale'] = 'Changed host reason'
    elif field == 'eligibility': case['eligibility'] = 'unknown'
    elif field == 'disposition': case['disposition'] = 'dismissed'
    elif field == 'work': case['work_claim_ids'] = ['case:b']
    elif field == 'obligation': case['obligation_refs'].append('changed')
    elif field == 'source': data['source_refs'].append('changed')
    elif field == 'policy': data['bindings'][0]['value']['value'] = '9'
    elif field == 'capacity': data['administration']['batch']['accounts'][0]['opening'] = '6'
    elif field == 'order': data['administration']['claim_order'].reverse()
    else: data['administration']['activities'][0]['terms_known'] = False
    with pytest.raises(AccountError, match='stale_adjudication_preview'):
        preview(dto(data), edit=old, **context())


@pytest.mark.parametrize('field', ['relationship','entity','population','mechanism','review','implementation','unit','model','source'])
def test_complete_host_context_bound(field):
    ctx = context(); plan = dto(); old = edit(plan, **ctx)
    w = ctx['graph']; m = ctx['mechanisms']
    if field == 'relationship': ctx['graph'] = WorldGraph(w.registry, [*w.relationships, edge('extra','regional-authority','local')])
    elif field in ('entity','population'):
        entities = list(w.registry.entities)
        populations = w.registry.populations
        if field == 'entity': entities[0] = entities[0].model_copy(update=dict(label='changed'))
        else: populations = tuple(replace(p, role='dynamic_state') for p in populations)
        ctx['graph'] = WorldGraph(WorldRegistry('civ', entities=entities, scopes=w.registry.scopes, populations=populations), w.relationships)
    elif field == 'unit': ctx['units'] = Registry(tuple(replace(u, scale=Decimal(2)) if u.id == 'hours' else u for u in ctx['units'].units))
    else:
        fields = dict(model=m.model, units=m.units, times=m.times, source_ids=m.source_ids, assumption_ids=m.assumption_ids,
            fixture_ids=m.fixture_ids, implementations=m.implementations, reviews=m.reviews, definitions=m.definitions, graphs=m.graphs)
        if field == 'mechanism': fields['definitions'] = [m.definitions[0].model_copy(update=dict(version='v2'))]
        elif field == 'review': fields['reviews'] = ()
        elif field == 'implementation': fields['implementations'] = ()
        elif field == 'model': fields['model'] = ('changed','v1')
        else: fields['source_ids'] = {*m.source_ids,'new:source'}
        ctx['mechanisms'] = type(m)(**fields)
    with pytest.raises(AccountError, match='stale_adjudication_preview'):
        preview(plan, edit=old, **ctx)


@pytest.mark.parametrize('identity', ['VERSION','RUNTIME_ID','EVALUATOR_ID'])
def test_runtime_identity_bound(monkeypatch, identity):
    import poliscope_engine.domains.law_conflict.exploration as module
    plan = dto(); old = edit(plan)
    monkeypatch.setattr(module, identity, 'changed')
    with pytest.raises(AccountError, match='stale_adjudication_preview'):
        preview(plan, edit=old, **context())


def test_detachment_and_forged_nested_values():
    plan = dto(); change = edit(plan)
    result = preview(plan, edit=change, **context())
    result.edit.__dict__['option_id'] = 'changed'
    result.report.evaluation.request.cases.clear()
    result.report.administration.indicators[0].source_refs.clear()
    assert plan == dto() and change == edit(plan)
    plan.cases[0].__dict__['eligibility'] = 'forged'
    with pytest.raises(ValidationError): report(plan, **context())


@pytest.mark.parametrize('scope,option,error', [('region','declared','incompatible_adjudication_scope'),
    ('local','foreign','unknown_adjudication_option')])
def test_rejected_scope_and_option(scope,option,error):
    plan = dto(); change = edit(plan).model_copy(update=dict(scope_id=scope,option_id='authored:adjudication/queue/'+option))
    with pytest.raises(AccountError,match=error): preview(plan,edit=change,**context())


def coverage():
    return json.loads((ROOT / 'content/law-conflict/coverage-v1.json').read_text())


def source():
    return json.loads((ROOT / 'docs/roadmap/execution/society/inventory.json').read_text())


def test_complete_source_inventory():
    result = validate_coverage(coverage(), source())
    assert len(result.entries) == 41
    assert sum(r.static_available for r in result.entries) == 4
    model = json.loads((ROOT / 'engine/poliscope_engine/domains/law_conflict/adjudication-v1.json').read_text())
    assert all(r.implementation_refs == [model['id'], 'authored:adjudication/queue']
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
    with pytest.raises((AccountError, ValidationError)):
        validate_coverage(data, source())
