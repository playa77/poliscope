"""Explicit care precedence over an unchanged host arrangement; no publication."""
from poliscope_engine.accounts import fail
from poliscope_engine.contracts.social_organization import (
    CareRequest, CareAlternative, CareInterview, CareEdit, CareReport, CarePreview,
)
from poliscope_engine.domains.economy.exploration import VERSION as ECONOMY_VERSION
from poliscope_engine.evaluation import EVALUATOR_ID
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.interviews import definition
from poliscope_engine.numeric import RUNTIME_ID
from . import evaluate_care

VERSION = 'care-exploration-v1'
MODEL = 'authored:social-care-v1'
QUESTION = 'authored:care/precedence'
LIMITS = ('Hypothetical care-time arrangement only. Explicitly retain the host queue or '
          'move care claims before other work, preserving order within both groups. '
          'No choice is selected by default. Membership, obligations, providers, access, '
          'paid/unpaid definitions, requested hours and institutions remain host inputs. '
          'Paid work does not imply wages; care does not imply an employment status. '
          'No household, health, demographic, learning or belonging effects are predicted. '
          'No durable arrangement, legal enforcement or service delivery is published.')


def detached(request):
    return CareRequest.model_validate_json(request.model_dump_json())


def baseline(request, *, graph, units):
    world = graph.registry
    return digest(dict(version=VERSION, model=MODEL, economy=ECONOMY_VERSION,
        runtime=RUNTIME_ID, evaluator=EVALUATOR_ID, request=request, units=units,
        world=dict(civilization_id=world.civilization_id, entities=world.entities,
            scopes=world.scopes, values=world.values, owners=world.owners,
            populations=world.populations, relationships=graph.relationships)))


def interview(request, *, graph, units, scope_id):
    request = detached(request)
    evaluate_care(request, graph=graph, units=units)
    if request.scope_id != scope_id:
        fail('incompatible_care_scope')
    question = definition(QUESTION, 'question', None,
        'Which explicit care and other-work precedence should this scope preview?')
    care_ids = {d.claim_id for d in request.obligations}
    order = request.work.claim_order
    care_first = [c for c in order if c in care_ids] + [c for c in order if c not in care_ids]
    alternatives = [CareAlternative(claim_order=queue,
        definition=definition(QUESTION + '/' + key, 'option', QUESTION, text).model_copy(update={
            'modeling': 'procedural', 'mechanism_refs': [MODEL]}))
        for key, queue, text in (
            ('declared', list(order), 'Retain every claim in the explicit host queue. '
             'No family, care or employment priority is inferred.'),
            ('care-first', care_first, 'Move declared care claims before other work, '
             'preserving relative order within each group. Employment, learning and '
             'participation may lose capacity; no obligation, membership or budget changes.'))]
    return CareInterview(baseline_digest=baseline(request, graph=graph, units=units),
        scope_id=scope_id, question=question, alternatives=alternatives,
        selected_option_id=None, limits=LIMITS)


def report(request, *, graph, units):
    request = detached(request)
    evaluation = evaluate_care(request, graph=graph, units=units)
    return CareReport(contract_version=1, adapter_version=VERSION,
        coverage_status='partial', evidence_status='hypothetical',
        baseline_digest=baseline(request, graph=graph, units=units), evaluation=evaluation)


def preview(request, *, graph, units, edit):
    request = detached(request)
    edit = CareEdit.model_validate_json(edit.model_dump_json())
    if edit.baseline_digest != baseline(request, graph=graph, units=units):
        fail('stale_care_preview')
    card = interview(request, graph=graph, units=units, scope_id=edit.scope_id)
    option = next((o for o in card.alternatives if o.definition.id == edit.option_id), None)
    if option is None:
        fail('unknown_care_option')
    candidate = request.model_copy(update=dict(work=request.work.model_copy(
        update=dict(claim_order=option.claim_order))))
    result = report(candidate, graph=graph, units=units)
    return CarePreview(contract_version=1, edit=edit,
        candidate_digest=result.baseline_digest, report=result)
