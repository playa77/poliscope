"""Actual scoped decisions and legal case work share one finite dated book."""
from poliscope_engine.accounts import AccountBook, fail, index
from poliscope_engine.contracts.governance_adjudication import (
    GovernanceAdjudicationRequest, GovernanceAdjudicationEvaluation,
)
from poliscope_engine.contracts.law_conflict import AdjudicationRequest
from poliscope_engine.domains.economy import compile_choices
from poliscope_engine.domains.economy.governance import closed
from poliscope_engine.domains.governance import evaluate_governance
from poliscope_engine.domains.law_conflict import evaluate_adjudication
from ..provisioning.context import binding as context_binding, digest, policy_evidence

MODEL = ('authored:governance-adjudication', 'v1')


def binding(request, graph, units, mechanisms):
    return digest(dict(context=context_binding(request, graph, units,
        adapter='governance-adjudication-v1', model=MODEL), policy=policy_evidence(mechanisms)))


def validate_context(request, graph, units):
    gov, law = request.governance, request.adjudication
    first, second = gov.administration, law.administration
    if first.batch != second.batch or first.holders != second.holders:
        fail('decision_case_book_mismatch')
    if first.period_id != second.period_id:
        fail('decision_case_period_mismatch')
    if gov.scope_id != law.scope_id:
        fail('decision_case_scope_mismatch')
    book = AccountBook(first.batch, units)
    claims, accounts = index(book.batch.claims), index(book.batch.accounts)
    entities = {e.id: e.entity_kind for e in graph.registry.entities}
    scopes = {s.id for s in graph.registry.scopes}
    for account in accounts.values():
        if entities.get(account.id) != 'account' or account.scope_id not in scopes:
            fail('decision_case_account_identity')
        if account.period_id is not None and account.period_id != first.period_id:
            fail('decision_case_period_mismatch')
    if any(entities.get(c.claimant_id) not in ('population_cohort', 'institution')
           for c in claims.values()):
        fail('decision_case_claimant_identity')
    if any(entities.get(h.holder_id) != 'population_cohort' for h in first.holders):
        fail('decision_case_holder_identity')
    time_ids = {a.id for a in accounts.values()
                if units.unit(a.unit_id).dimension == (('time', 1),)}
    if time_ids != {h.account_id for h in first.holders if h.role == 'time'}:
        fail('decision_case_time_holders')
    cases = {c.id: c for c in law.cases}
    mappings = [p.case_id for p in request.prerequisites]
    decision_work = set(gov.administrative_claim_ids)
    case_work = [cid for c in law.cases for cid in c.work_claim_ids]
    if (len(cases) != len(law.cases) or len(set(mappings)) != len(mappings)
            or set(mappings) != set(cases) or len(set(case_work)) != len(case_work)
            or decision_work & set(case_work) or not set(case_work) <= claims.keys()
            or len(decision_work) != len(gov.administrative_claim_ids)
            or not decision_work <= claims.keys()):
        fail('invalid_decision_case_mapping')
    proposals = [b for b in gov.bindings if b.id == gov.proposal_binding_id]
    if len(proposals) != 1:
        fail('invalid_governance_proposal')
    for prerequisite in request.prerequisites:
        case = cases[prerequisite.case_id]
        if prerequisite.requires_approval and (
                case.target_id != gov.target_id
                or not {claims[c].account_id for c in case.work_claim_ids} <= set(proposals[0].account_refs)
                or any(accounts[claims[c].account_id].scope_id != gov.scope_id for c in case.work_claim_ids)):
            fail('decision_case_affected_mapping')
    for phase, closed_ids in ((first, set(case_work)), (second, decision_work)):
        activities = {a.claim_id: a for a in phase.activities}
        if len(activities) != len(phase.activities) or set(activities) != set(claims):
            fail('invalid_economy_activities')
        if any(not closed(activities[c]) for c in closed_ids):
            fail('decision_case_open_phase_claim')
        # Validate original terms before either phase can hide invalid inputs.
        compile_choices(phase, units)


def evaluate_pair(request, *, graph, units, mechanisms):
    request = GovernanceAdjudicationRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    if mechanisms.units != units:
        fail('decision_case_policy_units')
    governance = evaluate_governance(request.governance, graph=graph, units=units,
        mechanisms=mechanisms)
    adjudication = None
    if governance.status == 'resolved':
        data = request.adjudication.model_dump()
        data['administration']['batch'] = governance.administration.batch.model_dump()
        if governance.outcome != 'approved':
            blocked_cases = {p.case_id for p in request.prerequisites if p.requires_approval}
            blocked_work = {cid for c in request.adjudication.cases if c.id in blocked_cases
                            for cid in c.work_claim_ids}
            for activity in data['administration']['activities']:
                if activity['claim_id'] in blocked_work and activity['eligibility'] != 'unknown':
                    activity['eligibility'] = 'denied'
        adjudication = evaluate_adjudication(AdjudicationRequest.model_validate(data),
            graph=graph, units=units, mechanisms=mechanisms)
    resolved = adjudication is not None and adjudication.status == 'resolved'
    return GovernanceAdjudicationEvaluation(contract_version=1,
        adapter_version='governance-adjudication-v1', evidence_status='hypothetical',
        baseline_digest=binding(request, graph, units, mechanisms),
        status='resolved' if resolved else 'unresolved', request=request,
        governance=governance, adjudication=adjudication,
        batch=adjudication.administration.evaluation.batch if resolved else None)
