"""Actual beneficiary care and education compete for the same finite work."""
from poliscope_engine.accounts import fail
from poliscope_engine.contracts.care_education import CareEducationRequest, CareEducationEvaluation
from poliscope_engine.domains.social_organization import evaluate_care
from poliscope_engine.domains.knowledge_culture import evaluate_education
from ..provisioning.context import binding as context_binding, digest, policy_evidence

MODEL = ('authored:care-education', 'v1')


def binding(request, graph, units, mechanisms):
    return digest(dict(context=context_binding(request, graph, units,
        adapter='care-education-v1', model=MODEL), policy=policy_evidence(mechanisms)))


def validate_context(request, graph, units):
    # Equality includes claims, prior postings, holds, subtotals, holders,
    # access/requirements, procedure and queue. Neither domain gets a new budget.
    if request.care.work != request.education.work:
        fail('care_education_work_mismatch')
    if request.care.scope_id != request.education.scope_id:
        fail('care_education_scope_mismatch')
    entities = {e.id: e.entity_kind for e in graph.registry.entities}
    scopes = {s.id: s.scope_kind for s in graph.registry.scopes}
    work = request.care.work
    time_accounts = {a.id for a in work.batch.accounts
                     if units.unit(a.unit_id).dimension == (('time', 1),)}
    if time_accounts != {h.account_id for h in work.holders if h.role == 'time'}:
        fail('counterpart_time_holders')
    for account in work.batch.accounts:
        if entities.get(account.id) != 'account':
            fail('counterpart_account_identity')
        if scopes.get(account.scope_id) not in ('settlement', 'region'):
            fail('counterpart_scope_identity')
        if account.period_id is not None and account.period_id != work.period_id:
            fail('counterpart_period_mismatch')
    for account in request.education.facility_allocation.batch.accounts:
        if entities.get(account.id) != 'account':
            fail('counterpart_facility_account_identity')
    for holder in work.holders:
        if entities.get(holder.holder_id) != 'population_cohort':
            fail('counterpart_holder_identity')
    for claim in work.batch.claims:
        if entities.get(claim.claimant_id) != 'population_cohort':
            fail('counterpart_claimant_identity')



def evaluate_pair(request, *, graph, units, mechanisms):
    request = CareEducationRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    if mechanisms.units != units:
        fail('care_education_policy_units')
    # Both original declarations validate even if the other domain is unknown.
    # Service inputs are independent commitments, not all-or-nothing delivery.
    care = evaluate_care(request.care, graph=graph, units=units)
    education = evaluate_education(request.education, graph=graph, units=units, mechanisms=mechanisms)
    if care.work != education.work:
        fail('care_education_allocation_mismatch')
    resolved = care.status == education.status == 'resolved'
    return CareEducationEvaluation(contract_version=1, adapter_version='care-education-v1',
        baseline_digest=binding(request, graph, units, mechanisms), evidence_status='hypothetical',
        status='resolved' if resolved else 'unresolved', request=request, care=care,
        education=education, batch=care.work.evaluation.batch if resolved else None)
