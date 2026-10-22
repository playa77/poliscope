"""Explicit education precedence over an unchanged host arrangement; no publication."""
from dataclasses import asdict
from poliscope_engine.accounts import fail
from poliscope_engine.contracts.knowledge_culture import (
    EducationRequest, EducationAlternative, EducationInterview, EducationEdit, EducationReport, EducationPreview,
)
from poliscope_engine.domains.economy.exploration import VERSION as ECONOMY_VERSION
from poliscope_engine.evaluation import EVALUATOR_ID
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.interviews import definition
from poliscope_engine.numeric import RUNTIME_ID
from . import evaluate_education

VERSION = 'education-exploration-v1'
MODEL = 'authored:education-capacity-v1'
QUESTION = 'authored:education/precedence'
LIMITS = ('Hypothetical education-time arrangement only. Explicitly retain the host queue or '
          'move education claims before other work, preserving order within both groups. '
          'No choice is selected by default. Participants, qualifications, facilities, access, '
          'requested inputs and institutions remain host inputs. Facility queue is unchanged. '
          'Paid work does not imply wages; education does not imply an employment status. '
          'No attendance, completion, learning or cultural effects are predicted. '
          'No durable arrangement, legal enforcement or service delivery is published.')


def detached(request):
    return EducationRequest.model_validate_json(request.model_dump_json())


def baseline(request, *, graph, mechanisms, units):
    # Bind the complete trusted host context, including review dispositions and
    # implementation identities, never callback objects. Match evaluator identity.
    world = graph.registry
    return digest(dict(version=VERSION, model=MODEL, economy=ECONOMY_VERSION, runtime=RUNTIME_ID, evaluator=EVALUATOR_ID,
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


def interview(request, *, graph, mechanisms, units, scope_id):
    request = detached(request)
    evaluate_education(request, graph=graph, mechanisms=mechanisms, units=units)
    if request.scope_id != scope_id:
        fail('incompatible_education_scope')
    question = definition(QUESTION, 'question', None,
        'Which explicit education and other-work precedence should this scope preview?')
    education_ids = {cid for service in request.services for cid in (
        *[p.claim_id for p in service.participants], *[p.claim_id for p in service.staff],
        *service.supply_claim_ids)}
    order = request.work.claim_order
    education_first = [c for c in order if c in education_ids] + [c for c in order if c not in education_ids]
    alternatives = [EducationAlternative(claim_order=queue,
        definition=definition(QUESTION + '/' + key, 'option', QUESTION, text).model_copy(update={
            'modeling': 'procedural', 'mechanism_refs': [MODEL]}))
        for key, queue, text in (
            ('declared', list(order), 'Retain every claim in the explicit host queue. '
             'No education priority is inferred.'),
            ('education-first', education_first, 'Move declared education claims before other work, '
             'preserving relative order within each group. Care, employment and '
             'participation may lose capacity; no prerequisite, facility queue or budget changes.'))]
    return EducationInterview(baseline_digest=baseline(request, graph=graph, mechanisms=mechanisms, units=units),
        scope_id=scope_id, question=question, alternatives=alternatives,
        selected_option_id=None, limits=LIMITS)


def report(request, *, graph, mechanisms, units):
    request = detached(request)
    evaluation = evaluate_education(request, graph=graph, mechanisms=mechanisms, units=units)
    return EducationReport(contract_version=1, adapter_version=VERSION,
        coverage_status='partial', evidence_status='hypothetical',
        baseline_digest=baseline(request, graph=graph, mechanisms=mechanisms, units=units), evaluation=evaluation)


def preview(request, *, graph, mechanisms, units, edit):
    request = detached(request)
    edit = EducationEdit.model_validate_json(edit.model_dump_json())
    if edit.baseline_digest != baseline(request, graph=graph, mechanisms=mechanisms, units=units):
        fail('stale_education_preview')
    card = interview(request, graph=graph, mechanisms=mechanisms, units=units, scope_id=edit.scope_id)
    option = next((o for o in card.alternatives if o.definition.id == edit.option_id), None)
    if option is None:
        fail('unknown_education_option')
    candidate = request.model_copy(update=dict(work=request.work.model_copy(
        update=dict(claim_order=option.claim_order))))
    result = report(candidate, graph=graph, mechanisms=mechanisms, units=units)
    return EducationPreview(contract_version=1, edit=edit,
        candidate_digest=result.baseline_digest, report=result)
