"""Literal hypothetical decision oracles and actual DOM-02 shared time fixtures."""
from copy import deepcopy
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.governance import GovernanceRequest
from poliscope_engine.contracts.world import EntityDTO
from poliscope_engine.domains.governance import evaluate_governance
from poliscope_engine.world import WorldRegistry, PopulationDeclaration
from poliscope_engine.world.membership import WorldGraph
from test_policies import graph, mechanisms, binding, overlap, rule, PROVENANCE
from test_economy import units, account, claim, holder, activity


def world():
    base = graph()
    entities = [*base.registry.entities, *[EntityDTO(id=i, entity_kind='population_cohort',
        label=i, provenance=PROVENANCE) for i in ('cohort:a', 'cohort:b', 'cohort:c')]]
    return WorldGraph(WorldRegistry('civ', entities=entities, scopes=base.registry.scopes,
        populations=[PopulationDeclaration(i, 'fixed_input') for i in ('cohort:a', 'cohort:b', 'cohort:c')]), base.relationships)


def request(scope='local'):
    authority = 'local-authority' if scope == 'local' else 'regional-authority'
    return dict(contract_version=1, authority_id=authority, scope_id=scope,
        proposal_binding_id='a', target_id='water', parameter_id='synthetic:parameter',
        eligible_member_ids=['cohort:a', 'cohort:b', 'cohort:c'],
        ballots=[dict(member_id='cohort:a', vote='yes'), dict(member_id='cohort:b', vote='yes'),
                 dict(member_id='cohort:c', vote='no')], quorum=2, approval='strict_majority',
        bindings=[binding(scope_id=scope, authority_id=authority).model_dump()], rules=[],
        administration=dict(contract_version=1, period_id='day:0', batch=dict(contract_version=1,
            accounts=[account('time:a', 5, scope, 'hours')],
            claims=[claim('admin', 'time:a', 3, 'cohort:a'), claim('care', 'time:a', 4, 'cohort:a')],
            postings=[], reservations=[], subtotals=[]), holders=[holder('time:a', 'cohort:a', 'time')],
            activities=[activity('admin', 'participation'), activity('care', 'care')],
            procedure='priority', claim_order=['admin', 'care'], mechanism_ref='synthetic:admin',
            source_refs=['synthetic:source']), administrative_claim_ids=['admin'], source_refs=['synthetic:source'])


def run(data=None, **kwargs):
    return evaluate_governance(GovernanceRequest.model_validate(request() if data is None else data),
        graph=kwargs.get('graph', world()), mechanisms=mechanisms(), units=units())


@pytest.mark.parametrize('scope', ['local', 'region'])
def test_two_scopes_use_actual_finite_economy_time(scope):
    data = request(scope)
    before = deepcopy(data)
    result = run(data)
    assert (result.status, result.outcome, result.findings) == ('resolved', 'approved', [])
    assert [(a.claim_id, a.allocated, a.unmet) for a in result.administration.allocation.actuals] == [
        ('admin', '3', '0'), ('care', '2', '2')]
    assert result.administration.allocation.accounts.accounts[0].closing == '0'
    assert data == before
    data['ballots'][0]['vote'] = 'no'
    assert result.request.ballots[0].vote == 'yes'


@pytest.mark.parametrize('votes,approval,quorum,expected', [
    (['yes', 'yes', 'no'], 'unanimity', 2, 'rejected'),
    (['yes', 'yes', 'yes'], 'unanimity', 3, 'approved'),
    (['yes', 'no'], 'strict_majority', 2, 'rejected'),
    (['yes', 'abstain'], 'strict_majority', 2, 'rejected'),
    (['yes'], 'strict_majority', 2, 'no_quorum'),
    ([], 'strict_majority', 2, 'no_quorum'),
    (['yes', 'abstain', 'yes'], 'strict_majority', 3, 'approved'),
])
def test_declared_denominator_and_quorum(votes, approval, quorum, expected):
    data = request()
    data.update(approval=approval, quorum=quorum)
    data['ballots'] = [dict(member_id=m, vote=v) for m, v in zip(data['eligible_member_ids'], votes)]
    assert run(data).outcome == expected


def test_shared_care_precedence_blocks_decision_without_creating_time():
    data = request()
    data['administration']['claim_order'].reverse()
    result = run(data)
    assert result.outcome == 'capacity_blocked'
    assert [(a.claim_id, a.allocated, a.unmet) for a in result.administration.allocation.actuals] == [
        ('admin', '1', '2'), ('care', '4', '0')]


@pytest.mark.parametrize('missing,finding', [('vote', 'unknown_ballot'),
    ('approval', 'missing_approval_rule'), ('admin', 'unknown_administration')])
def test_unknown_is_not_rejection_or_approval(missing, finding):
    data = request()
    if missing == 'vote':
        data['ballots'][0]['vote'] = 'unknown'
    elif missing == 'approval':
        data['approval'] = None
    else:
        data['administration']['procedure'] = None
    result = run(data)
    assert result.status == 'unresolved' and result.outcome is None
    assert finding in result.findings


def test_overlap_never_uses_id_order_and_requires_exact_selected_proposal():
    data = request('region')
    data.update(bindings=[b.model_dump() for b in overlap()], proposal_binding_id='b')
    for bindings in (data['bindings'], list(reversed(data['bindings']))):
        data['bindings'] = bindings
        result = run(data)
        assert result.outcome is None and result.findings == ['institutional_conflict']
        assert 'authority_conflict' in [f.kind for f in result.policies.results[0].findings]
    data['rules'] = [rule().model_dump()]
    assert run(data).outcome == 'approved'
    data['rules'] = [rule(selected_id='a').model_dump()]
    assert run(data).findings == ['proposal_not_selected']


@pytest.mark.parametrize('mutation', ['duplicate_member', 'foreign_member', 'resource_member',
    'duplicate_ballot', 'ineligible_ballot', 'quorum', 'authority', 'proposal', 'target',
    'claim', 'duplicate_claim', 'kind', 'scope', 'zero_demand', 'foreign_claimant', 'missing_account'])
def test_invalid_host_inputs_rejected(mutation):
    data = request()
    if mutation == 'duplicate_member': data['eligible_member_ids'].append('cohort:a')
    elif mutation == 'foreign_member': data['eligible_member_ids'][0] = 'missing'
    elif mutation == 'resource_member': data['eligible_member_ids'][0] = 'water'
    elif mutation == 'duplicate_ballot': data['ballots'].append(data['ballots'][0])
    elif mutation == 'ineligible_ballot': data['ballots'][0]['member_id'] = 'local-authority'
    elif mutation == 'quorum': data['quorum'] = 4
    elif mutation == 'authority': data['authority_id'] = 'water'
    elif mutation == 'proposal': data['proposal_binding_id'] = 'missing'
    elif mutation == 'target': data['target_id'] = 'food'
    elif mutation == 'claim': data['administrative_claim_ids'] = ['missing']
    elif mutation == 'duplicate_claim': data['administrative_claim_ids'] *= 2
    elif mutation == 'kind': data['administration']['activities'][0]['kind'] = 'care'
    elif mutation == 'scope': data['administration']['batch']['accounts'][0]['scope_id'] = 'region'
    elif mutation == 'zero_demand': data['administration']['batch']['claims'][0]['requested'] = '0'
    elif mutation == 'missing_account': data['administration']['batch']['claims'][0]['account_id'] = 'missing'
    elif mutation == 'foreign_claimant': data['administration']['batch']['claims'][0]['claimant_id'] = 'missing'
    with pytest.raises((AccountError, ValidationError)):
        run(data)


def test_no_transitive_or_missing_jurisdiction():
    base = world()
    stripped = WorldGraph(base.registry, [e for e in base.relationships if e.id != 'local-j'])
    with pytest.raises(AccountError, match='missing_governance_jurisdiction'):
        run(graph=stripped)


def test_prior_fulfillment_does_not_spend_again():
    first = run()
    data = request()
    data['administration']['batch'] = first.administration.batch.model_dump()
    second = run(data)
    assert second.outcome == 'approved'
    assert all(a.allocated == '0' for a in second.administration.allocation.actuals)
    assert second.administration.batch == first.administration.batch


def test_nested_constructed_invalid_data_revalidated():
    req = GovernanceRequest.model_validate(request())
    req.ballots[0].__dict__['vote'] = 'forged'
    with pytest.raises(ValidationError):
        evaluate_governance(req, graph=world(), mechanisms=mechanisms(), units=units())


def test_unknown_selected_policy_retains_missing_input():
    data = request()
    data['bindings'][0]['value'] = dict(kind='unknown', reason='No reviewed quantity')
    result = run(data)
    assert result.status == 'unresolved' and result.outcome is None
    assert result.findings == ['missing_policy_input']
    assert result.policies.results[0].value is None
