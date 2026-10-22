"""Explicit infrastructure precedence over an unchanged host arrangement; no publication."""
from poliscope_engine.accounts import fail
from poliscope_engine.contracts.infrastructure import (
    InfrastructureRequest, InfrastructureAlternative, InfrastructureInterview, InfrastructureEdit, InfrastructureReport, InfrastructurePreview,
)
from poliscope_engine.evaluation import EVALUATOR_ID
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.interviews import definition
from poliscope_engine.numeric import RUNTIME_ID
from . import evaluate_infrastructure

VERSION = 'infrastructure-exploration-v1'
MODEL = 'authored:infrastructure-reach-v1'
QUESTION = 'authored:infrastructure/precedence'
LIMITS = ('Hypothetical facility-slot reach only. Explicitly retain or reverse the entire '
          'host queue; no option is selected by default. All paths, access, lifecycle '
          'declarations and capacity accounts remain host inputs. No construction, '
          'maintenance, entitlement, delivered service or population coverage is predicted. '
          'No durable state is published.')


def detached(request):
    return InfrastructureRequest.model_validate_json(request.model_dump_json())


def baseline(request, *, graph, units):
    # Bind the complete trusted host context, including topology and
    # implementation identities, never callback objects. Match evaluator identity.
    world = graph.registry
    return digest(dict(version=VERSION, model=MODEL, runtime=RUNTIME_ID, evaluator=EVALUATOR_ID,
        request=request, units=units,
        world=dict(civilization_id=world.civilization_id, entities=world.entities,
            scopes=world.scopes, values=world.values, owners=world.owners,
            populations=world.populations, relationships=graph.relationships)))



def interview(request, *, graph, units, scope_id):
    request = detached(request)
    evaluate_infrastructure(request, graph=graph, units=units)
    if request.scope_id != scope_id:
        fail('incompatible_infrastructure_scope')
    question = definition(QUESTION, 'question', None,
        'Which explicit facility claim precedence should this scope preview?')
    order = request.claim_order
    alternatives = [InfrastructureAlternative(claim_order=queue,
        definition=definition(QUESTION + '/' + key, 'option', QUESTION, text).model_copy(update={
            'modeling': 'procedural', 'mechanism_refs': [MODEL]}))
        for key, queue, text in (
            ('declared', list(order), 'Retain every claim in the explicit host queue.'),
            ('reversed', list(reversed(order)), 'Reverse the complete host queue. '
             'Earlier claims may lose shared link or facility capacity; no capacity or access changes.'))]
    return InfrastructureInterview(baseline_digest=baseline(request, graph=graph, units=units),
        scope_id=scope_id, question=question, alternatives=alternatives,
        selected_option_id=None, limits=LIMITS)


def report(request, *, graph, units):
    request = detached(request)
    evaluation = evaluate_infrastructure(request, graph=graph, units=units)
    return InfrastructureReport(contract_version=1, adapter_version=VERSION,
        coverage_status='partial', evidence_status='hypothetical',
        baseline_digest=baseline(request, graph=graph, units=units), evaluation=evaluation)


def preview(request, *, graph, units, edit):
    request = detached(request)
    edit = InfrastructureEdit.model_validate_json(edit.model_dump_json())
    if edit.baseline_digest != baseline(request, graph=graph, units=units):
        fail('stale_infrastructure_preview')
    card = interview(request, graph=graph, units=units, scope_id=edit.scope_id)
    option = next((o for o in card.alternatives if o.definition.id == edit.option_id), None)
    if option is None:
        fail('unknown_infrastructure_option')
    candidate = request.model_copy(update=dict(claim_order=option.claim_order))
    result = report(candidate, graph=graph, units=units)
    return InfrastructurePreview(contract_version=1, edit=edit,
        candidate_digest=result.baseline_digest, report=result)
