"""Pure host-only approval exploration; selection never adopts a policy."""
from dataclasses import asdict
from poliscope_engine.accounts import fail, index
from poliscope_engine.contracts.governance import (
    GovernanceRequest, GovernanceAlternative, GovernanceInterview, GovernanceEdit,
    GovernanceReport, GovernancePreview,
)
from poliscope_engine.domains.economy.exploration import report as economy_report
from poliscope_engine.evaluation import EVALUATOR_ID
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.interviews import definition
from poliscope_engine.numeric import RUNTIME_ID
from . import evaluate_governance

VERSION = 'governance-exploration-v1'
MODEL = 'authored:governance-decision-v1'
LIMITS = ('Hypothetical equal-member ballots only. The host supplies canonical electorate, '
          'eligibility, mandates, quorum, ballots and administrative costs. No default option. '
          'Abstentions count toward quorum and the approval denominator; absent members do not. '
          'No population weighting, delegation, deliberation, legitimacy or behavioral effects. '
          'Approval does not adopt a policy, spend time, publish or execute institutional action.')


def detached(request):
    return GovernanceRequest.model_validate_json(request.model_dump_json())


def baseline(request, *, graph, mechanisms, units):
    # Bind the complete trusted host context, including review dispositions and
    # implementation identities, never callback objects. Match evaluator identity.
    world = graph.registry
    return digest(dict(version=VERSION, runtime=RUNTIME_ID, evaluator=EVALUATOR_ID,
        request=request, units=units,
        world=dict(civilization_id=world.civilization_id, entities=world.entities,
            scopes=world.scopes, values=world.values, owners=world.owners,
            populations=world.populations, relationships=graph.relationships),
        mechanisms=dict(model=mechanisms.model, definitions=mechanisms.definitions,
            graphs=mechanisms.graphs, reviews=[asdict(r) for r in mechanisms.reviews],
            implementations=[dict(id=i.id, version=i.version, phase=i.phase)
                             for i in mechanisms.implementations],
            units=mechanisms.units, times=mechanisms.times, source_ids=mechanisms.source_ids,
            assumption_ids=mechanisms.assumption_ids, fixture_ids=mechanisms.fixture_ids)))


def scoped(request, scope_id):
    accounts = index(request.administration.batch.accounts)
    # A local approval choice must not appear to govern another scope's work.
    if request.scope_id != scope_id or any(
            accounts[c.account_id].scope_id != scope_id
            for c in request.administration.batch.claims):
        fail('incompatible_governance_scope')


def interview(request, *, graph, mechanisms, units, scope_id):
    request = detached(request)
    evaluate_governance(request, graph=graph, mechanisms=mechanisms, units=units)
    scoped(request, scope_id)
    qid = 'authored:governance/approval'
    question = definition(qid, 'question', None,
        'Which approval rule should this scope preview for the declared equal-member ballots?')
    alternatives = [GovernanceAlternative(approval=approval,
        definition=definition(qid + '/' + approval, 'option', qid, text).model_copy(update={
            'modeling': 'procedural', 'mechanism_refs': [MODEL]}))
        for approval, text in (
            ('strict_majority', 'Approve only when more than half of submitted ballots are yes. '
             'Abstentions count in the denominator. Quorum and complete administrative work are required.'),
            ('unanimity', 'Approve only when every submitted ballot is yes. '
             'Abstentions prevent approval. Quorum and complete administrative work are required.'))]
    return GovernanceInterview(baseline_digest=baseline(request, graph=graph,
        mechanisms=mechanisms, units=units), scope_id=scope_id, question=question,
        alternatives=alternatives, selected_option_id=None, limits=LIMITS)


def report(request, *, graph, mechanisms, units):
    request = detached(request)
    evaluation = evaluate_governance(request, graph=graph, mechanisms=mechanisms, units=units)
    return GovernanceReport(contract_version=1, adapter_version=VERSION,
        coverage_status='partial', evidence_status='hypothetical',
        baseline_digest=baseline(request, graph=graph, mechanisms=mechanisms, units=units),
        evaluation=evaluation, administration=economy_report(request.administration, units))


def preview(request, *, graph, mechanisms, units, edit):
    request = detached(request)
    edit = GovernanceEdit.model_validate_json(edit.model_dump_json())
    if edit.baseline_digest != baseline(request, graph=graph, mechanisms=mechanisms, units=units):
        fail('stale_governance_preview')
    card = interview(request, graph=graph, mechanisms=mechanisms, units=units, scope_id=edit.scope_id)
    option = next((o for o in card.alternatives if o.definition.id == edit.option_id), None)
    if option is None:
        fail('unknown_governance_option')
    candidate = request.model_copy(update=dict(approval=option.approval))
    result = report(candidate, graph=graph, mechanisms=mechanisms, units=units)
    return GovernancePreview(contract_version=1, edit=edit,
        candidate_digest=result.baseline_digest, report=result)
