"""Literal hypothetical case/work oracles; no legal merits or fairness claims."""
from copy import deepcopy
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.law_conflict import AdjudicationRequest
from poliscope_engine.domains.law_conflict import evaluate_adjudication
from poliscope_engine.world.membership import WorldGraph
from test_governance import world, request as governance_request
from test_policies import mechanisms, overlap, rule
from test_economy import claim, activity, units


def request(scope='local'):
    base = governance_request(scope)
    admin = base['administration']
    admin['batch']['claims'].insert(1, claim('case:b', 'time:a', 3, 'cohort:a'))
    admin['activities'].insert(1, activity('case:b', 'participation'))
    admin['claim_order'] = ['admin', 'case:b', 'care']
    cases = [dict(id='case:' + suffix, right_ref='hypothetical:right/access',
        claimant_id='cohort:' + suffix, authority_id=base['authority_id'],
        binding_id='a', target_id='water', parameter_id='synthetic:parameter',
        eligibility='eligible', incompatible_right_refs=[], disposition=disposition,
        rationale='Hypothetical host-selected ruling; no inferred merits.',
        work_claim_ids=[work], obligation_refs=['hypothetical:duty/' + suffix],
        source_refs=['synthetic:source']) for suffix, work, disposition in
        [('a', 'admin', 'upheld'), ('b', 'case:b', 'dismissed')]]
    return dict(contract_version=1, scope_id=scope, cases=cases,
        bindings=base['bindings'], rules=[], administration=admin, source_refs=['synthetic:source'])


def run(data=None, graph=None):
    return evaluate_adjudication(AdjudicationRequest.model_validate(request() if data is None else data),
        graph=graph or world(), mechanisms=mechanisms(), units=units())


@pytest.mark.parametrize('scope', ['local', 'region'])
def test_two_groups_and_finite_case_throughput(scope):
    data = request(scope); before = deepcopy(data)
    result = run(data)
    # Five hours can complete only one three-hour case. No fractional disposition.
    assert [r.outcome for r in result.results] == ['upheld', 'capacity_blocked']
    assert [r.status for r in result.results] == ['resolved', 'resolved']
    assert result.status == 'resolved' and result.evidence_status == 'hypothetical'
    assert [(i.claim_id, i.actual, i.unmet) for i in result.administration.indicators] == [
        ('admin','3','0'), ('case:b','2','1'), ('care','0','4')]
    assert data == before
    assert [c.claimant_id for c in result.request.cases] == ['cohort:a', 'cohort:b']
    assert all(c.right_ref == 'hypothetical:right/access' for c in result.request.cases)
    for i in result.administration.indicators:
        assert (i.scope_id, i.period_id, i.unit_id, i.budgets[0].holder_id) == (scope, 'day:0', 'hours', 'cohort:a')
        assert i.posting_ids == [p.id for p in result.administration.evaluation.batch.postings if p.claim_id == i.claim_id]
    assert result.results[0].proposed_obligation_refs == ['hypothetical:duty/a']
    assert result.results[1].proposed_obligation_refs == ['hypothetical:duty/b']


@pytest.mark.parametrize('order,outcomes,actuals', [
    (['case:b','admin','care'], ['capacity_blocked','dismissed'], ['2','3','0']),
    (['care','admin','case:b'], ['capacity_blocked','capacity_blocked'], ['1','0','4']),
])
def test_explicit_work_queue_changes_group_outcomes(order, outcomes, actuals):
    data = request(); data['administration']['claim_order'] = order
    result = run(data)
    assert [r.outcome for r in result.results] == outcomes
    assert [i.actual for i in result.administration.indicators] == actuals
    # Case report order cannot select winners.
    data['cases'].reverse()
    assert {r.case_id:r.outcome for r in run(data).results} == {r.case_id:r.outcome for r in result.results}


@pytest.mark.parametrize('disposition', ['upheld','dismissed'])
def test_complete_work_uses_only_explicit_host_disposition(disposition):
    data = request(); data['cases'][0]['disposition'] = disposition
    result = run(data)
    assert result.results[0].outcome == disposition
    assert result.request.cases[0].right_ref == data['cases'][0]['right_ref']
    assert result.request.cases[0].rationale == data['cases'][0]['rationale']


@pytest.mark.parametrize('eligibility', ['eligible','ineligible'])
def test_zero_capacity_retains_right_case_and_obligation(eligibility):
    data = request(); data['administration']['batch']['accounts'][0]['opening'] = '0'
    data['cases'][0]['eligibility'] = eligibility
    result = run(data)
    assert result.results[0].outcome == ('capacity_blocked' if eligibility == 'eligible' else 'ineligible')
    assert result.request.cases == AdjudicationRequest.model_validate(data).cases
    assert all(i.actual == '0' and i.unmet == i.requested for i in result.administration.indicators)


@pytest.mark.parametrize('missing,finding', [('eligibility','unknown_legal_eligibility'),
    ('right','incompatible_rights'), ('disposition','missing_disposition'), ('rationale','missing_disposition'),
    ('policy','missing_policy_input')])
def test_unknown_or_conflicting_legal_inputs_withhold_outcome(missing, finding):
    data = request(); case = data['cases'][0]
    if missing == 'eligibility': case['eligibility'] = 'unknown'
    elif missing == 'right': case['incompatible_right_refs'] = ['hypothetical:right/conflicting']
    elif missing in ('disposition','rationale'): case[missing] = None
    else: data['bindings'][0]['value'] = dict(kind='unknown',reason='No reviewed policy input')
    result = run(data)
    assert result.status == 'unresolved'
    assert result.results[0].outcome is None and result.results[0].findings == [finding]
    # A legal gap is not a fabricated zero capacity measurement.
    assert result.administration.status == 'resolved'
    assert result.administration.indicators[0].actual == '3'
    if missing != 'policy': assert result.results[1].outcome == 'capacity_blocked'


@pytest.mark.parametrize('missing', ['procedure','eligibility','terms'])
def test_unknown_capacity_has_null_actuals_and_no_candidate(missing):
    data = request(); admin = data['administration']
    if missing == 'procedure': admin['procedure'] = None
    elif missing == 'eligibility': admin['activities'][0]['eligibility'] = 'unknown'
    else: admin['activities'][0]['terms_known'] = False
    result = run(data)
    assert result.status == 'unresolved' and result.administration.status == 'unresolved'
    assert result.administration.evaluation.batch is None
    assert all(i.actual is None and i.unmet is None for i in result.administration.indicators)
    assert all(r.outcome is None and r.findings == ['unknown_case_capacity'] for r in result.results)


def test_actual_authority_conflict_and_exact_selection():
    data = request('region')
    data['bindings'] = [b.model_dump() for b in overlap()]
    for case in data['cases']: case['binding_id'] = 'b'
    for bindings in (data['bindings'], list(reversed(data['bindings']))):
        data['bindings'] = bindings
        result = run(data)
        assert all(r.outcome is None and r.findings == ['institutional_conflict'] for r in result.results)
        assert 'authority_conflict' in [f.kind for f in result.policies.results[0].findings]
    data['rules'] = [rule().model_dump()]
    assert run(data).results[0].outcome == 'upheld'
    data['rules'] = [rule(selected_id='a').model_dump()]
    assert all(r.findings == ['adjudication_binding_not_selected'] for r in run(data).results)


def test_prior_work_and_reservations_do_not_resolve_twice_or_spend_twice():
    data = request()
    data['administration']['batch']['reservations'] = [dict(id='hold:case',account_id='time:a',claim_id='admin',amount='2')]
    first = run(data)
    data['administration']['batch'] = first.administration.evaluation.batch.model_dump()
    second = run(data)
    assert [r.outcome for r in second.results] == ['upheld','capacity_blocked']
    assert second.administration.evaluation.batch == first.administration.evaluation.batch
    assert [(i.actual_before,i.actual,i.unmet) for i in second.administration.indicators] == [
        ('3','0','0'),('2','0','1'),('0','0','4')]


@pytest.mark.parametrize('mutation', ['scope','claimant','resource_claimant','authority','jurisdiction',
    'binding','binding_authority','binding_scope','parameter','target','duplicate_case','duplicate_work',
    'shared_work','missing_work','kind','work_scope','zero_work','foreign_worker','missing_account',
    'duplicate_time','period','work_owner','missing_order'])
def test_invalid_canonical_and_work_inputs_rejected(mutation):
    data = request(); case = data['cases'][0]; admin = data['administration']; graph = world()
    if mutation == 'scope': data['scope_id'] = 'missing'
    elif mutation == 'claimant': case['claimant_id'] = 'missing'
    elif mutation == 'resource_claimant': case['claimant_id'] = 'water'
    elif mutation == 'authority': case['authority_id'] = 'water'
    elif mutation == 'jurisdiction': graph = WorldGraph(graph.registry,[e for e in graph.relationships if e.id != 'local-j'])
    elif mutation == 'binding': case['binding_id'] = 'missing'
    elif mutation == 'binding_authority': data['bindings'][0]['authority_id'] = 'regional-authority'
    elif mutation == 'binding_scope': data['bindings'][0]['scope_id'] = 'region'
    elif mutation == 'parameter': case['parameter_id'] = 'missing'
    elif mutation == 'target': case['target_id'] = 'food'
    elif mutation == 'duplicate_case': data['cases'].append(deepcopy(case))
    elif mutation == 'duplicate_work': case['work_claim_ids'] *= 2
    elif mutation == 'shared_work': data['cases'][1]['work_claim_ids'] = case['work_claim_ids']
    elif mutation == 'missing_work': case['work_claim_ids'] = ['missing']
    elif mutation == 'kind': admin['activities'][0]['kind'] = 'care'
    elif mutation == 'work_scope': admin['batch']['accounts'][0]['scope_id'] = 'region'
    elif mutation == 'zero_work': admin['batch']['claims'][0]['requested'] = '0'
    elif mutation == 'foreign_worker': admin['batch']['claims'][0]['claimant_id'] = 'missing'
    elif mutation == 'missing_account': admin['batch']['claims'][0]['account_id'] = 'missing'
    elif mutation == 'duplicate_time':
        extra = deepcopy(admin['batch']['accounts'][0]); extra['id'] = 'time:duplicate'
        admin['batch']['accounts'].append(extra)
        extra = deepcopy(admin['holders'][0]); extra['account_id'] = 'time:duplicate'; admin['holders'].append(extra)
    elif mutation == 'period': admin['period_id'] = 'day:1'
    elif mutation == 'work_owner': admin['holders'][0]['holder_id'] = 'cohort:b'
    elif mutation == 'missing_order': admin['claim_order'].pop()
    with pytest.raises((AccountError, ValidationError, ValueError)):
        run(data, graph)


def test_input_and_result_are_detached_and_nested_dtos_revalidated():
    data = request(); plan = AdjudicationRequest.model_validate(data)
    result = evaluate_adjudication(plan,graph=world(),mechanisms=mechanisms(),units=units())
    result.request.cases[0].obligation_refs.clear()
    result.results[0].proposed_obligation_refs.append('changed')
    result.administration.indicators[0].posting_ids.clear()
    assert plan == AdjudicationRequest.model_validate(data)
    plan.cases[0].__dict__['eligibility'] = 'forged'
    with pytest.raises(ValidationError):
        evaluate_adjudication(plan,graph=world(),mechanisms=mechanisms(),units=units())


@pytest.mark.parametrize('governance_first', [True, False])
def test_actual_governance_and_law_share_one_canonical_time_batch(governance_first):
    from poliscope_engine.contracts.governance import GovernanceRequest
    from poliscope_engine.domains.governance import evaluate_governance
    data = request(); admin = data['administration']
    admin['batch']['claims'].append(claim('governance', 'time:a', 2, 'cohort:a'))
    admin['activities'].append(activity('governance', 'participation'))
    admin['claim_order'] = (['governance','admin','case:b','care'] if governance_first
                            else ['admin','case:b','governance','care'])
    gov = governance_request()
    gov['administration'] = deepcopy(admin); gov['administrative_claim_ids'] = ['governance']
    institutional = evaluate_governance(GovernanceRequest.model_validate(gov),
        graph=world(), mechanisms=mechanisms(), units=units())
    legal = run(data)
    assert legal.administration.evaluation.batch == institutional.administration.batch
    assert institutional.outcome == ('approved' if governance_first else 'capacity_blocked')
    assert [r.outcome for r in legal.results] == ['upheld','capacity_blocked']
    assert [i.actual for i in legal.administration.indicators] == (
        ['3','0','0','2'] if governance_first else ['3','2','0','0'])
    assert legal.administration.evaluation.allocation.accounts.accounts[0].closing == '0'


def test_multiple_required_work_claims_must_all_complete():
    data = request()
    data['cases'] = [data['cases'][0]]
    data['cases'][0]['work_claim_ids'].append('case:b')
    assert run(data).results[0].outcome == 'capacity_blocked'


def test_unknown_case_does_not_block_independent_known_case():
    data = request(); data['cases'][1]['eligibility'] = 'unknown'
    result = run(data)
    assert result.status == 'unresolved'
    assert result.results[0].outcome == 'upheld' and result.results[0].status == 'resolved'
    assert result.results[1].outcome is None


def test_unsupported_scope_and_transitive_authority_are_not_inferred():
    from poliscope_engine.world import WorldRegistry
    base = world()
    scopes = [s.model_copy(update=dict(scope_kind='civilization')) if s.id == 'local' else s
              for s in base.registry.scopes]
    graph = WorldGraph(WorldRegistry('civ', entities=base.registry.entities, scopes=scopes,
        populations=base.registry.populations), base.relationships)
    with pytest.raises(AccountError, match='invalid_adjudication_scope'):
        run(graph=graph)
