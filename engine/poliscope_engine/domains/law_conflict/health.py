"""Actual case work and health share finite canonical dated resources."""
from poliscope_engine.accounts import AccountBook, fail, index
from poliscope_engine.contracts.adjudication_health import (
    AdjudicationHealthRequest, AdjudicationHealthEvaluation,
)
from poliscope_engine.contracts.health import HealthRequest
from poliscope_engine.domains.economy import compile_choices
from poliscope_engine.domains.economy.adjudication import closed
from poliscope_engine.domains.law_conflict import evaluate_adjudication
from poliscope_engine.domains.health import evaluate_health
from ..provisioning.context import binding as context_binding, digest, policy_evidence

MODEL = ('authored:adjudication-health', 'v1')


def binding(request, graph, units, mechanisms):
    return digest(dict(context=context_binding(request, graph, units,
        adapter='adjudication-health-v1', model=MODEL), policy=policy_evidence(mechanisms)))


def service_work(service):
    return [p.claim_id for p in [*service.participants, *service.staff]] + service.supply_claim_ids


def validate_context(request, graph, units):
    legal, health = request.adjudication, request.health
    first, second = legal.administration, health.work
    if first.batch != second.batch or first.holders != second.holders:
        fail('adjudication_health_book_mismatch')
    if first.period_id != second.period_id:
        fail('adjudication_health_period_mismatch')
    if legal.scope_id != health.scope_id:
        fail('adjudication_health_scope_mismatch')
    book = AccountBook(first.batch, units)
    claims, accounts = index(book.batch.claims), index(book.batch.accounts)
    entities = {e.id: e.entity_kind for e in graph.registry.entities}
    scopes = {s.id for s in graph.registry.scopes}
    for account in [*accounts.values(), *health.facility_allocation.batch.accounts]:
        if entities.get(account.id) != 'account' or account.scope_id not in scopes:
            fail('adjudication_health_account_identity')
        if account.period_id is not None and account.period_id != first.period_id:
            fail('adjudication_health_period_mismatch')
    if any(entities.get(c.claimant_id) != 'population_cohort' for c in claims.values()):
        fail('adjudication_health_claimant_identity')
    if any(entities.get(h.holder_id) != 'population_cohort' for h in first.holders):
        fail('adjudication_health_holder_identity')
    time_ids = {a.id for a in accounts.values()
                if units.unit(a.unit_id).dimension == (('time', 1),)}
    if time_ids != {h.account_id for h in first.holders if h.role == 'time'}:
        fail('adjudication_health_time_holders')
    services, cases = index(health.services), index(legal.cases)
    mappings = [p.service_id for p in request.prerequisites]
    case_work = {cid for case in legal.cases for cid in case.work_claim_ids}
    health_work = [cid for s in health.services for cid in service_work(s)]
    if (len(set(mappings)) != len(mappings) or set(mappings) != set(services)
            or len(set(health_work)) != len(health_work)
            or case_work & set(health_work) or not set(health_work) <= claims.keys()
            or not case_work <= claims.keys()):
        fail('invalid_adjudication_health_mapping')
    fclaims = index(health.facility_allocation.batch.claims)
    activities = {a.claim_id: a for a in second.activities}
    if len(activities) != len(second.activities) or set(activities) != set(claims):
        fail('invalid_economy_activities')
    for prerequisite in request.prerequisites:
        if prerequisite.case_id is None:
            continue
        service = services[prerequisite.service_id]
        case = cases.get(prerequisite.case_id)
        bindings = [b for b in legal.bindings if case is not None and b.id == case.binding_id]
        # A legal claimant must be a participant in the declared service. A case
        # authorizes no new terms: it only gates this explicit target/obligation.
        if (case is None or case.claimant_id not in {p.cohort_id for p in service.participants}
                or case.target_id != service.target_id or case.authority_id != service.authority_id
                or not service.obligation_refs or not set(service.obligation_refs) <= set(case.obligation_refs)
                or len(bindings) != 1
                or not {claims[c].account_id for c in service_work(service)} <= set(bindings[0].account_refs)
                or not {r.account_id for c in service_work(service) for r in activities[c].requirements} <= set(bindings[0].account_refs)
                or any(c not in fclaims for c in service.facility_claim_ids)
                or not {fclaims[c].account_id for c in service.facility_claim_ids} <= set(bindings[0].account_refs)):
            fail('adjudication_health_affected_mapping')
    # All non-case work is explicitly closed in phase one. Phase two cannot
    # repeat case work, including after a dismissal or a prior partial posting.
    for phase, closed_ids in ((first, set(claims) - case_work), (second, case_work)):
        activities = {a.claim_id: a for a in phase.activities}
        if len(activities) != len(phase.activities) or set(activities) != set(claims):
            fail('invalid_economy_activities')
        if any(not closed(activities[c]) for c in closed_ids):
            fail('adjudication_health_open_phase_claim')
        compile_choices(phase, units)


def evaluate_pair(request, *, graph, units, mechanisms):
    request = AdjudicationHealthRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    if mechanisms.units != units:
        fail('adjudication_health_policy_units')
    preflight = evaluate_health(request.health, graph=graph, units=units, mechanisms=mechanisms)
    adjudication = evaluate_adjudication(request.adjudication, graph=graph, units=units, mechanisms=mechanisms)
    health = None
    if adjudication.status == 'resolved':
        data = request.health.model_dump()
        data['work']['batch'] = adjudication.administration.evaluation.batch.model_dump()
        outcomes = {r.case_id: r.outcome for r in adjudication.results}
        blocked = {p.service_id for p in request.prerequisites
                   if p.case_id is not None and outcomes[p.case_id] != 'upheld'}
        blocked_work = {cid for s in request.health.services if s.id in blocked for cid in service_work(s)}
        blocked_slots = {cid for s in request.health.services if s.id in blocked for cid in s.facility_claim_ids}
        for service in data['services']:
            if service['id'] in blocked and service['eligibility'] != 'unknown':
                service['eligibility'] = 'denied'
        for activity in data['work']['activities']:
            if activity['claim_id'] in blocked_work and activity['eligibility'] != 'unknown':
                activity['eligibility'] = 'denied'
        for choice in data['facility_allocation']['choices']:
            if choice['claim_id'] in blocked_slots and choice['access'] != 'unknown':
                choice['access'] = 'denied'
        health = evaluate_health(HealthRequest.model_validate(data), graph=graph, units=units, mechanisms=mechanisms)
    resolved = health is not None and health.status == 'resolved' and preflight.status == 'resolved'
    return AdjudicationHealthEvaluation(contract_version=1,
        adapter_version='adjudication-health-v1', evidence_status='hypothetical',
        baseline_digest=binding(request, graph, units, mechanisms),
        status='resolved' if resolved else 'unresolved', request=request,
        adjudication=adjudication, preflight=preflight, health=health,
        batch=health.work.evaluation.batch.model_dump() if resolved else None)
