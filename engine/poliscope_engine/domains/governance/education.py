"""Actual decisions and education prerequisites share one finite dated work book."""
from poliscope_engine.accounts import AccountBook, fail, index
from poliscope_engine.contracts.governance_education import (
    GovernanceEducationRequest, GovernanceEducationEvaluation,
)
from poliscope_engine.contracts.knowledge_culture import EducationRequest
from poliscope_engine.domains.economy import compile_choices
from poliscope_engine.domains.economy.governance import closed
from poliscope_engine.domains.governance import evaluate_governance
from poliscope_engine.domains.knowledge_culture import evaluate_education
from ..provisioning.context import binding as context_binding, digest, policy_evidence

MODEL = ('authored:governance-education', 'v1')


def binding(request, graph, units, mechanisms):
    return digest(dict(context=context_binding(request, graph, units,
        adapter='governance-education-v1', model=MODEL), policy=policy_evidence(mechanisms)))


def service_work(service):
    return [p.claim_id for p in [*service.participants, *service.staff]] + service.supply_claim_ids


def validate_context(request, graph, units):
    gov, education = request.governance, request.education
    first, second = gov.administration, education.work
    if first.batch != second.batch or first.holders != second.holders:
        fail('decision_education_book_mismatch')
    if first.period_id != second.period_id:
        fail('decision_education_period_mismatch')
    if gov.scope_id != education.scope_id:
        fail('decision_education_scope_mismatch')
    book = AccountBook(first.batch, units)
    claims, accounts = index(book.batch.claims), index(book.batch.accounts)
    entities = {e.id: e.entity_kind for e in graph.registry.entities}
    scopes = {s.id for s in graph.registry.scopes}
    for account in [*accounts.values(), *education.facility_allocation.batch.accounts]:
        if entities.get(account.id) != 'account' or account.scope_id not in scopes:
            fail('decision_education_account_identity')
        if account.period_id is not None and account.period_id != first.period_id:
            fail('decision_education_period_mismatch')
    if any(entities.get(c.claimant_id) != 'population_cohort' for c in claims.values()):
        fail('decision_education_claimant_identity')
    if any(entities.get(h.holder_id) != 'population_cohort' for h in first.holders):
        fail('decision_education_holder_identity')
    time_ids = {a.id for a in accounts.values()
                if units.unit(a.unit_id).dimension == (('time', 1),)}
    if time_ids != {h.account_id for h in first.holders if h.role == 'time'}:
        fail('decision_education_time_holders')
    services = {s.id: s for s in education.services}
    mappings = [p.service_id for p in request.prerequisites]
    decision_work = set(gov.administrative_claim_ids)
    education_work = [cid for s in education.services for cid in service_work(s)]
    if (len(services) != len(education.services) or len(set(mappings)) != len(mappings)
            or set(mappings) != set(services) or len(set(education_work)) != len(education_work)
            or decision_work & set(education_work) or not set(education_work) <= claims.keys()
            or len(decision_work) != len(gov.administrative_claim_ids)
            or not decision_work <= claims.keys()):
        fail('invalid_decision_education_mapping')
    proposals = [b for b in gov.bindings if b.id == gov.proposal_binding_id]
    if len(proposals) != 1:
        fail('invalid_governance_proposal')
    fclaims = index(education.facility_allocation.batch.claims)
    for prerequisite in request.prerequisites:
        service = services[prerequisite.service_id]
        if prerequisite.requires_approval and (
                service.target_id != gov.target_id
                or not {claims[c].account_id for c in service_work(service)} <= set(proposals[0].account_refs)
                or any(c not in fclaims for c in service.facility_claim_ids)
                or not {fclaims[c].account_id for c in service.facility_claim_ids} <= set(proposals[0].account_refs)):
            fail('decision_education_affected_mapping')
    for phase, closed_ids in ((first, set(education_work)), (second, decision_work)):
        activities = {a.claim_id: a for a in phase.activities}
        if len(activities) != len(phase.activities) or set(activities) != set(claims):
            fail('invalid_economy_activities')
        if any(not closed(activities[c]) for c in closed_ids):
            fail('decision_education_open_phase_claim')
        compile_choices(phase, units)


def evaluate_pair(request, *, graph, units, mechanisms):
    request = GovernanceEducationRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    if mechanisms.units != units:
        fail('decision_education_policy_units')
    # Detached original-term preflight validates facilities, bindings and service
    # identities even when an unresolved decision prevents the staged invocation.
    evaluate_education(request.education, graph=graph, units=units, mechanisms=mechanisms)
    governance = evaluate_governance(request.governance, graph=graph, units=units,
        mechanisms=mechanisms)
    education = None
    if governance.status == 'resolved':
        data = request.education.model_dump()
        data['work']['batch'] = governance.administration.batch.model_dump()
        if governance.outcome != 'approved':
            blocked = {p.service_id for p in request.prerequisites if p.requires_approval}
            blocked_work = {cid for s in request.education.services if s.id in blocked for cid in service_work(s)}
            blocked_slots = {cid for s in request.education.services if s.id in blocked for cid in s.facility_claim_ids}
            for service in data['services']:
                if service['id'] in blocked and service['eligibility'] != 'unknown':
                    service['eligibility'] = 'denied'
            for activity in data['work']['activities']:
                if activity['claim_id'] in blocked_work and activity['eligibility'] != 'unknown':
                    activity['eligibility'] = 'denied'
            for choice in data['facility_allocation']['choices']:
                if choice['claim_id'] in blocked_slots and choice['access'] != 'unknown':
                    choice['access'] = 'denied'
        education = evaluate_education(EducationRequest.model_validate(data),
            graph=graph, units=units, mechanisms=mechanisms)
    resolved = education is not None and education.status == 'resolved'
    return GovernanceEducationEvaluation(contract_version=1,
        adapter_version='governance-education-v1', evidence_status='hypothetical',
        baseline_digest=binding(request, graph, units, mechanisms),
        status='resolved' if resolved else 'unresolved', request=request,
        governance=governance, education=education,
        batch=education.work.evaluation.batch if resolved else None)
