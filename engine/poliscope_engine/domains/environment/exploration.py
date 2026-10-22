"""Explicit ecological claim precedence over unchanged host prerequisites; no publication."""
from poliscope_engine.accounts import fail
from poliscope_engine.contracts.environment import (
    EnvironmentRequest, EnvironmentAlternative, EnvironmentInterview, EnvironmentEdit, EnvironmentReport, EnvironmentPreview,
)
from poliscope_engine.evaluation import EVALUATOR_ID
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.interviews import definition
from poliscope_engine.numeric import RUNTIME_ID
from . import evaluate_environment

VERSION = 'environment-exploration-v1'
MODEL = 'authored:ecological-prerequisites-v1'
QUESTION = 'authored:environment/precedence'
LIMITS = ('Hypothetical extraction-stock and dated sink-allowance prerequisites only. '
          'Explicitly retain or reverse the complete host queue; no default. Physical '
          'estimates, access ceilings and selected policy-limit diagnostics remain host inputs. '
          'No delivery, regeneration, absorption, exposure, production or emissions effect '
          'is inferred; no ecological score or policy is imposed.')


def detached(request):
    return EnvironmentRequest.model_validate_json(request.model_dump_json())


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
    evaluate_environment(request, graph=graph, units=units)
    if request.scope_id != scope_id:
        fail('incompatible_environment_scope')
    question = definition(QUESTION, 'question', None,
        'Which explicit ecological claim precedence should this scope preview?')
    order = request.claim_order
    alternatives = [EnvironmentAlternative(claim_order=queue,
        definition=definition(QUESTION + '/' + key, 'option', QUESTION, text).model_copy(update={
            'modeling': 'procedural', 'mechanism_refs': [MODEL]}))
        for key, queue, text in (
            ('declared', list(order), 'Retain every claim in the explicit host queue.'),
            ('reversed', list(reversed(order)), 'Reverse the complete host queue. '
             'Earlier claims may lose shared extraction stock or sink allowance; no capacity or access changes.'))]
    return EnvironmentInterview(baseline_digest=baseline(request, graph=graph, units=units),
        scope_id=scope_id, question=question, alternatives=alternatives,
        selected_option_id=None, limits=LIMITS)


def report(request, *, graph, units):
    request = detached(request)
    evaluation = evaluate_environment(request, graph=graph, units=units)
    return EnvironmentReport(contract_version=1, adapter_version=VERSION,
        coverage_status='partial', evidence_status='hypothetical',
        baseline_digest=baseline(request, graph=graph, units=units), evaluation=evaluation)


def preview(request, *, graph, units, edit):
    request = detached(request)
    edit = EnvironmentEdit.model_validate_json(edit.model_dump_json())
    if edit.baseline_digest != baseline(request, graph=graph, units=units):
        fail('stale_environment_preview')
    card = interview(request, graph=graph, units=units, scope_id=edit.scope_id)
    option = next((o for o in card.alternatives if o.definition.id == edit.option_id), None)
    if option is None:
        fail('unknown_environment_option')
    candidate = request.model_copy(update=dict(claim_order=option.claim_order))
    result = report(candidate, graph=graph, units=units)
    return EnvironmentPreview(contract_version=1, edit=edit,
        candidate_digest=result.baseline_digest, report=result)
