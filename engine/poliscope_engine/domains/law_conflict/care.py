"""Actual case work precedes care on one finite canonical dated work book."""
from poliscope_engine.accounts import AccountBook, fail, index
from poliscope_engine.contracts.adjudication_care import (
    AdjudicationCareRequest, AdjudicationCareEvaluation,
)
from poliscope_engine.contracts.social_organization import CareRequest
from poliscope_engine.domains.economy import compile_choices
from poliscope_engine.domains.economy.adjudication import closed
from poliscope_engine.domains.law_conflict import evaluate_adjudication
from poliscope_engine.domains.social_organization import evaluate_care
from ..provisioning.context import binding as context_binding, digest, policy_evidence

MODEL = ('authored:adjudication-care', 'v1')


def binding(request, graph, units, mechanisms):
    return digest(dict(context=context_binding(request, graph, units,
        adapter='adjudication-care-v1', model=MODEL), policy=policy_evidence(mechanisms)))


def validate_context(request, graph, units):
    legal, care = request.adjudication, request.care
    admin, work = legal.administration, care.work
    if admin.batch != work.batch or admin.holders != work.holders:
        fail('adjudication_care_book_mismatch')
    if admin.period_id != work.period_id:
        fail('adjudication_care_period_mismatch')
    if legal.scope_id != care.scope_id:
        fail('adjudication_care_scope_mismatch')
    book = AccountBook(work.batch, units)
    claims = index(book.batch.claims)
    duties, cases = index(care.obligations), index(legal.cases)
    mapped = [p.obligation_id for p in request.prerequisites]
    if len(set(mapped)) != len(mapped) or set(mapped) != set(duties):
        fail('invalid_adjudication_care_mapping')
    case_work = {c for case in cases.values() for c in case.work_claim_ids}
    care_work = {d.claim_id for d in duties.values()}
    if not case_work <= claims.keys() or case_work & care_work:
        fail('adjudication_care_phase_overlap')
    entities = {e.id: e.entity_kind for e in graph.registry.entities}
    scopes = {s.id for s in graph.registry.scopes}
    for account in book.batch.accounts:
        if entities.get(account.id) != 'account' or account.scope_id not in scopes:
            fail('adjudication_care_account_identity')
        if account.period_id is not None and account.period_id != work.period_id:
            fail('adjudication_care_period_mismatch')
    if any(entities.get(c.claimant_id) != 'population_cohort' for c in claims.values()):
        fail('adjudication_care_claimant_identity')
    if any(entities.get(h.holder_id) != 'population_cohort' for h in work.holders):
        fail('adjudication_care_holder_identity')
    time_ids = {a.id for a in book.batch.accounts
                if units.unit(a.unit_id).dimension == (('time', 1),)}
    if time_ids != {h.account_id for h in work.holders if h.role == 'time'}:
        fail('adjudication_care_time_holders')
    for prerequisite in request.prerequisites:
        if prerequisite.case_id is None:
            continue
        duty = duties[prerequisite.obligation_id]
        case = cases.get(prerequisite.case_id)
        bindings = [b for b in legal.bindings if case is not None and b.id == case.binding_id]
        claim = claims.get(duty.claim_id)
        if (case is None or claim is None or case.claimant_id != duty.beneficiary_id
                or case.target_id != duty.beneficiary_id
                or case.authority_id != duty.authority_id
                or duty.obligation_ref not in case.obligation_refs
                or len(bindings) != 1 or claim.account_id not in bindings[0].account_refs):
            fail('adjudication_care_obligation_mapping')
    # Case work is the only open first-phase work. The second phase cannot
    # repeat it. Other original care/work/goods declarations remain untouched.
    for phase, closed_ids in ((admin, set(claims) - case_work), (work, case_work)):
        activities = {a.claim_id: a for a in phase.activities}
        if len(activities) != len(phase.activities) or set(activities) != set(claims):
            fail('invalid_economy_activities')
        if any(not closed(activities[c]) for c in closed_ids):
            fail('adjudication_care_open_phase_claim')
        compile_choices(phase, units)


def evaluate_pair(request, *, graph, units, mechanisms):
    request = AdjudicationCareRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    if mechanisms.units != units:
        fail('adjudication_care_policy_units')
    # Validate canonical membership, original eligibility and resource terms even
    # when legal inputs are unresolved. These hypothetical allocations are discarded.
    preflight = evaluate_care(request.care, graph=graph, units=units)
    adjudication = evaluate_adjudication(request.adjudication, graph=graph,
        mechanisms=mechanisms, units=units)
    care = None
    if adjudication.status == 'resolved':
        data = request.care.model_dump()
        data['work']['batch'] = adjudication.administration.evaluation.batch.model_dump()
        outcomes = {r.case_id: r.outcome for r in adjudication.results}
        duties = index(request.care.obligations)
        blocked = {duties[p.obligation_id].claim_id for p in request.prerequisites
                   if p.case_id is not None and outcomes[p.case_id] != 'upheld'}
        for activity in data['work']['activities']:
            if activity['claim_id'] in blocked and activity['eligibility'] != 'unknown':
                activity['eligibility'] = 'denied'
        care = evaluate_care(CareRequest.model_validate(data), graph=graph, units=units)
    resolved = care is not None and care.status == 'resolved'
    return AdjudicationCareEvaluation(contract_version=1,
        adapter_version='adjudication-care-v1', evidence_status='hypothetical',
        baseline_digest=binding(request, graph, units, mechanisms),
        status='resolved' if resolved else 'unresolved', request=request,
        adjudication=adjudication, preflight=preflight, care=care,
        batch=care.work.evaluation.batch.model_dump() if resolved else None)
