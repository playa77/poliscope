"""Pure host-only case-work exploration; selection never adjudicates durably."""
from dataclasses import asdict
from poliscope_engine.accounts import fail, index
from poliscope_engine.contracts.law_conflict import (
    AdjudicationRequest, AdjudicationAlternative, AdjudicationInterview, AdjudicationEdit,
    AdjudicationReport, AdjudicationPreview,
)
from poliscope_engine.domains.economy.exploration import report as economy_report
from poliscope_engine.evaluation import EVALUATOR_ID
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.interviews import definition
from poliscope_engine.numeric import RUNTIME_ID
from . import evaluate_adjudication

VERSION = 'adjudication-exploration-v1'
MODEL = 'authored:law-adjudication-v1'
LIMITS = ('Hypothetical procedural capacity only. Preserve the host-declared queue or reverse '
          'only case-work positions, keeping care and other work in their declared slots. '
          'No default, merits, rights, duties, eligibility or authority is inferred. '
          'Host assertions remain unvalidated; no enforcement, agreement compliance, '
          'durable queue, spending or publication follows from a preview.')


def detached(request):
    return AdjudicationRequest.model_validate_json(request.model_dump_json())


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
    # A local case-work choice must not appear to govern another scope's work.
    if request.scope_id != scope_id or any(
            accounts[c.account_id].scope_id != scope_id
            for c in request.administration.batch.claims):
        fail('incompatible_adjudication_scope')


def interview(request, *, graph, mechanisms, units, scope_id):
    request = detached(request)
    evaluate_adjudication(request, graph=graph, mechanisms=mechanisms, units=units)
    scoped(request, scope_id)
    qid = 'authored:adjudication/queue'
    question = definition(qid, 'question', None,
        'Which explicit case-work precedence should this scope preview?')
    order = request.administration.claim_order
    case_work = {cid for case in request.cases for cid in case.work_claim_ids}
    reversed_work = iter(reversed([cid for cid in order if cid in case_work]))
    reverse_order = [next(reversed_work) if cid in case_work else cid for cid in order]
    alternatives = [AdjudicationAlternative(claim_order=queue,
        definition=definition(qid + '/' + key, 'option', qid, text).model_copy(update={
            'modeling': 'procedural', 'mechanism_refs': [MODEL]}))
        for key, queue, text in (
            ('declared', list(order), 'Retain every claim in the explicit host queue. No legal priority is inferred.'),
            ('reverse', reverse_order, 'Reverse the explicit case-work claims within their existing slots. '
             'Care and other work keep their positions; all rights, rulings and costs stay unchanged.'))]
    return AdjudicationInterview(baseline_digest=baseline(request, graph=graph,
        mechanisms=mechanisms, units=units), scope_id=scope_id, question=question,
        alternatives=alternatives, selected_option_id=None, limits=LIMITS)


def report(request, *, graph, mechanisms, units):
    request = detached(request)
    evaluation = evaluate_adjudication(request, graph=graph, mechanisms=mechanisms, units=units)
    return AdjudicationReport(contract_version=1, adapter_version=VERSION,
        coverage_status='partial', evidence_status='hypothetical',
        baseline_digest=baseline(request, graph=graph, mechanisms=mechanisms, units=units),
        evaluation=evaluation, administration=economy_report(request.administration, units))


def preview(request, *, graph, mechanisms, units, edit):
    request = detached(request)
    edit = AdjudicationEdit.model_validate_json(edit.model_dump_json())
    if edit.baseline_digest != baseline(request, graph=graph, mechanisms=mechanisms, units=units):
        fail('stale_adjudication_preview')
    card = interview(request, graph=graph, mechanisms=mechanisms, units=units, scope_id=edit.scope_id)
    option = next((o for o in card.alternatives if o.definition.id == edit.option_id), None)
    if option is None:
        fail('unknown_adjudication_option')
    candidate = request.model_copy(update=dict(administration=request.administration.model_copy(
        update=dict(claim_order=option.claim_order))))
    result = report(candidate, graph=graph, mechanisms=mechanisms, units=units)
    return AdjudicationPreview(contract_version=1, edit=edit,
        candidate_digest=result.baseline_digest, report=result)
