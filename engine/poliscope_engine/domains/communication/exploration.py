"""Explicit message precedence over unchanged host prerequisites; no publication."""
from poliscope_engine.accounts import fail
from poliscope_engine.contracts.communication import (
    CommunicationRequest, CommunicationAlternative, CommunicationInterview, CommunicationEdit, CommunicationReport, CommunicationPreview,
)
from poliscope_engine.evaluation import EVALUATOR_ID
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.interviews import definition
from poliscope_engine.numeric import RUNTIME_ID
from . import evaluate_communication

VERSION = 'communication-exploration-v1'
MODEL = 'authored:communication-prerequisites-v1'
QUESTION = 'authored:communication/precedence'
LIMITS = ('Hypothetical message-slot prerequisites only. Explicitly retain or reverse the '
          'complete host queue; no default. Access, disclosure, recorded/available flags, '
          'channel reach, verification procedure, delay and finite accounts remain host inputs. '
          'No message is delivered, verified or published; no truth, trust, persuasion or '
          'institutional response is predicted. No application payload is read or shared.')


def detached(request):
    return CommunicationRequest.model_validate_json(request.model_dump_json())


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
    evaluate_communication(request, graph=graph, units=units)
    if request.scope_id != scope_id:
        fail('incompatible_communication_scope')
    question = definition(QUESTION, 'question', None,
        'Which explicit message claim precedence should this scope preview?')
    order = request.claim_order
    alternatives = [CommunicationAlternative(claim_order=queue,
        definition=definition(QUESTION + '/' + key, 'option', QUESTION, text).model_copy(update={
            'modeling': 'procedural', 'mechanism_refs': [MODEL]}))
        for key, queue, text in (
            ('declared', list(order), 'Retain every claim in the explicit host queue.'),
            ('reversed', list(reversed(order)), 'Reverse the complete host queue. '
             'Earlier claims may lose shared channel or verification capacity; no capacity or access changes.'))]
    return CommunicationInterview(baseline_digest=baseline(request, graph=graph, units=units),
        scope_id=scope_id, question=question, alternatives=alternatives,
        selected_option_id=None, limits=LIMITS)


def report(request, *, graph, units):
    request = detached(request)
    evaluation = evaluate_communication(request, graph=graph, units=units)
    return CommunicationReport(contract_version=1, adapter_version=VERSION,
        coverage_status='partial', evidence_status='hypothetical',
        baseline_digest=baseline(request, graph=graph, units=units), evaluation=evaluation)


def preview(request, *, graph, units, edit):
    request = detached(request)
    edit = CommunicationEdit.model_validate_json(edit.model_dump_json())
    if edit.baseline_digest != baseline(request, graph=graph, units=units):
        fail('stale_communication_preview')
    card = interview(request, graph=graph, units=units, scope_id=edit.scope_id)
    option = next((o for o in card.alternatives if o.definition.id == edit.option_id), None)
    if option is None:
        fail('unknown_communication_option')
    candidate = request.model_copy(update=dict(claim_order=option.claim_order))
    result = report(candidate, graph=graph, units=units)
    return CommunicationPreview(contract_version=1, edit=edit,
        candidate_digest=result.baseline_digest, report=result)
