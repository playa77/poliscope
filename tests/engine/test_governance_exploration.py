"""Literal ballot/time oracles and source reconciliation; no legitimacy claims."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.governance import GovernanceRequest, GovernanceEdit
from poliscope_engine.domains.governance.exploration import interview, preview, report
from poliscope_engine.domains.governance.coverage import validate_coverage
from poliscope_engine.numeric import Registry
from poliscope_engine.world import WorldRegistry
from poliscope_engine.world.membership import WorldGraph
from test_governance import request, world
from test_policies import mechanisms, overlap, rule, edge
from test_economy import units, account, claim, activity, holder

ROOT = Path(__file__).resolve().parents[2]


def dto(data=None):
    return GovernanceRequest.model_validate(request() if data is None else data)


def context():
    return dict(graph=world(), mechanisms=mechanisms(), units=units())


def edit(plan, approval='strict_majority', **ctx):
    card = interview(plan, scope_id=plan.scope_id, **(ctx or context()))
    return GovernanceEdit(baseline_digest=card.baseline_digest, scope_id=plan.scope_id,
        option_id=next(o.definition.id for o in card.alternatives if o.approval == approval))


@pytest.mark.parametrize('scope', ['local', 'region'])
def test_scoped_choices_have_no_default_and_change_only_approval(scope):
    plan = dto(request(scope))
    before = plan.model_dump_json()
    card = interview(plan, scope_id=scope, **context())
    assert card.selected_option_id is None and card.scope_id == scope
    assert {o.approval for o in card.alternatives} == {'strict_majority', 'unanimity'}
    assert all(o.definition.origin == 'authored' and o.definition.evidence == 'hypothetical'
               and o.definition.source_decision_id is None for o in card.alternatives)
    majority = preview(plan, edit=edit(plan), **context())
    unanimous = preview(plan, edit=edit(plan, 'unanimity'), **context())
    assert majority.report.evaluation.outcome == 'approved'
    assert unanimous.report.evaluation.outcome == 'rejected'
    assert majority.candidate_digest != unanimous.candidate_digest
    expected = plan.model_dump()
    expected['approval'] = 'unanimity'
    assert unanimous.report.evaluation.request.model_dump() == expected
    assert majority.report.administration == unanimous.report.administration
    assert plan.model_dump_json() == before
    assert majority.report.evaluation.request.eligible_member_ids == ['cohort:a', 'cohort:b', 'cohort:c']


@pytest.mark.parametrize('votes,quorum,approval,outcome', [
    (['yes', 'abstain'], 2, 'strict_majority', 'rejected'),
    (['yes'], 2, 'unanimity', 'no_quorum'),
    (['yes', 'yes'], 2, 'unanimity', 'approved'),
    ([], 1, 'strict_majority', 'no_quorum'),
])
def test_abstentions_and_absent_members_remain_explicit(votes, quorum, approval, outcome):
    data = request()
    data['quorum'] = quorum
    data['ballots'] = [dict(member_id=m, vote=v) for m, v in zip(data['eligible_member_ids'], votes)]
    plan = dto(data)
    result = preview(plan, edit=edit(plan, approval), **context()).report
    assert result.evaluation.outcome == outcome
    assert [b.vote for b in result.evaluation.request.ballots] == votes


@pytest.mark.parametrize('missing,finding', [('vote','unknown_ballot'), ('procedure','unknown_administration'),
    ('eligibility','unknown_administration'), ('terms','unknown_administration'), ('policy','missing_policy_input')])
def test_unknown_is_null_and_admin_measurements_have_independent_status(missing, finding):
    data = request()
    if missing == 'vote': data['ballots'][0]['vote'] = 'unknown'
    elif missing == 'procedure': data['administration']['procedure'] = None
    elif missing == 'eligibility': data['administration']['activities'][0]['eligibility'] = 'unknown'
    elif missing == 'terms': data['administration']['activities'][0]['terms_known'] = False
    else: data['bindings'][0]['value'] = dict(kind='unknown', reason='No reviewed value')
    plan = dto(data)
    result = preview(plan, edit=edit(plan), **context()).report
    assert result.evaluation.status == 'unresolved' and result.evaluation.outcome is None
    assert finding in result.evaluation.findings
    if finding == 'unknown_administration':
        assert result.administration.status == 'unresolved'
        assert result.administration.evaluation.batch is None
        assert all(i.actual is None and i.unmet is None for i in result.administration.indicators)
    else:
        assert result.administration.status == 'resolved'


def test_unanswered_approval_can_be_previewed_without_mutation():
    data = request(); data['approval'] = None
    plan = dto(data)
    assert report(plan, **context()).evaluation.findings == ['missing_approval_rule']
    assert preview(plan, edit=edit(plan), **context()).report.evaluation.outcome == 'approved'
    assert plan.approval is None


def test_care_contention_exposes_time_holder_period_and_postings():
    data = request(); data['administration']['claim_order'].reverse()
    result = report(dto(data), **context())
    assert result.evaluation.outcome == 'capacity_blocked'
    admin, care = result.administration.indicators
    assert (admin.actual, admin.unmet, care.actual, care.unmet) == ('1','2','4','0')
    for i in [admin, care]:
        assert (i.claimant_id, i.unit_id, i.period_id, i.scope_id) == ('cohort:a','hours','day:0','local')
        assert (i.budgets[0].holder_id, i.budgets[0].available_before, i.budgets[0].available_after) == ('cohort:a','5','0')
        assert i.posting_ids == [p.id for p in result.evaluation.administration.batch.postings if p.claim_id == i.claim_id]
    assert result.administration.evaluation == result.evaluation.administration


def test_prior_fulfillment_and_reservations_do_not_spend_again():
    data = request()
    data['administration']['batch']['reservations'] = [dict(id='hold:admin', account_id='time:a', claim_id='admin', amount='2')]
    first = report(dto(data), **context())
    data['administration']['batch'] = first.evaluation.administration.batch.model_dump()
    second = report(dto(data), **context())
    assert second.evaluation.outcome == 'approved'
    assert [(i.actual_before, i.actual, i.unmet) for i in second.administration.indicators] == [('3','0','0'),('2','0','2')]
    assert second.evaluation.administration.batch == first.evaluation.administration.batch


def test_overlap_and_exact_proposal_resolution_survive_exploration():
    data = request('region'); data.update(bindings=[b.model_dump() for b in overlap()], proposal_binding_id='b')
    for bindings in (data['bindings'], list(reversed(data['bindings']))):
        data['bindings'] = bindings
        plan = dto(data)
        result = preview(plan, edit=edit(plan), **context()).report
        assert result.evaluation.outcome is None
        assert result.evaluation.findings == ['institutional_conflict']
        assert 'authority_conflict' in [f.kind for f in result.evaluation.policies.results[0].findings]
    data['rules'] = [rule().model_dump()]
    assert report(dto(data), **context()).evaluation.outcome == 'approved'
    data['rules'] = [rule(selected_id='a').model_dump()]
    assert report(dto(data), **context()).evaluation.findings == ['proposal_not_selected']


@pytest.mark.parametrize('scope', ['region', 'missing'])
def test_foreign_scope_rejected(scope):
    plan = dto()
    with pytest.raises(AccountError, match='incompatible_governance_scope'):
        interview(plan, scope_id=scope, **context())
    change = edit(plan).model_copy(update=dict(scope_id=scope))
    with pytest.raises(AccountError, match='incompatible_governance_scope'):
        preview(plan, edit=change, **context())


def test_multi_scope_competing_work_is_reportable_but_not_locally_editable():
    data = request(); a = data['administration']
    a['batch']['accounts'].append(account('time:b', 2, 'region', 'hours'))
    a['batch']['claims'].append(claim('care:b', 'time:b', 3, 'cohort:b'))
    a['activities'].append(activity('care:b', 'care')); a['holders'].append(holder('time:b','cohort:b','time'))
    a['claim_order'].append('care:b')
    plan = dto(data)
    i = report(plan, **context()).administration.indicators[-1]
    assert (i.scope_id, i.claimant_id, i.actual, i.unmet) == ('region','cohort:b','2','1')
    with pytest.raises(AccountError, match='incompatible_governance_scope'):
        interview(plan, scope_id='local', **context())


def test_foreign_option_rejected():
    plan = dto()
    change = edit(plan).model_copy(update=dict(option_id='society:DEC-001'))
    with pytest.raises(AccountError, match='unknown_governance_option'):
        preview(plan, edit=change, **context())


@pytest.mark.parametrize('field', ['ballot','electorate','quorum','approval','proposal','policy','provenance','time','order','terms'])
def test_complete_request_bound_against_stale_preview(field):
    plan = dto(); old = edit(plan)
    data = plan.model_dump()
    if field == 'ballot': data['ballots'][0]['vote'] = 'no'
    elif field == 'electorate': data['eligible_member_ids'].pop()
    elif field == 'quorum': data['quorum'] = 3
    elif field == 'approval': data['approval'] = 'unanimity'
    elif field == 'proposal': data['proposal_binding_id'] = 'foreign'
    elif field == 'policy': data['bindings'][0]['value']['value'] = '9'
    elif field == 'provenance': data['source_refs'].append('authored:changed')
    elif field == 'time': data['administration']['batch']['accounts'][0]['opening'] = '6'
    elif field == 'order': data['administration']['claim_order'].reverse()
    else: data['administration']['activities'][0]['terms_known'] = False
    plan = dto(data)
    with pytest.raises(AccountError, match='stale_governance_preview'):
        preview(plan, edit=old, **context())


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
    with pytest.raises(AccountError, match='stale_governance_preview'):
        preview(plan, edit=old, **ctx)


@pytest.mark.parametrize('identity', ['VERSION','RUNTIME_ID','EVALUATOR_ID'])
def test_runtime_identity_bound(monkeypatch, identity):
    import poliscope_engine.domains.governance.exploration as module
    plan = dto(); old = edit(plan)
    monkeypatch.setattr(module, identity, 'changed')
    with pytest.raises(AccountError, match='stale_governance_preview'):
        preview(plan, edit=old, **context())


def test_detached_results_and_nested_revalidation():
    plan = dto(); change = edit(plan)
    result = preview(plan, edit=change, **context())
    result.edit.__dict__['option_id'] = 'changed'
    result.report.evaluation.request.eligible_member_ids.clear()
    result.report.administration.indicators[0].source_refs.clear()
    assert plan == dto() and change == edit(plan)
    plan.ballots[0].__dict__['vote'] = 'forged'
    with pytest.raises(ValidationError): report(plan, **context())


def coverage():
    return json.loads((ROOT / 'content/governance/coverage-v1.json').read_text())


def source():
    return json.loads((ROOT / 'docs/roadmap/execution/society/inventory.json').read_text())


def test_complete_source_inventory_preserves_all_alternatives():
    result = validate_coverage(coverage(), source())
    assert len(result.entries) == 37
    assert len([r for r in result.entries if r.static_available]) == 5
    provenance = [r for r in result.entries if r.classification == 'provenance']
    assert len(provenance) == 25 and all(not r.static_available and r.evidence_status == 'unreviewed' for r in provenance)
    assert all(not r.transition_available for r in result.entries)
    for suffix in ['1/2','2/2','2/3','3','3/1','3/2','3/3']:
        row = next(r for r in result.entries if r.source_id == 'society:domain/03/' + suffix)
        assert row.status == 'unsupported' and not row.static_available


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
