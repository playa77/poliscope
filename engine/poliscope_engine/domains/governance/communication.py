"""Actual approval prerequisites preserve finite message budgets and disclosure."""
from poliscope_engine.accounts import AccountBook, fail, index
from poliscope_engine.contracts.governance_communication import (
    GovernanceCommunicationRequest, GovernanceCommunicationEvaluation,
    GovernanceCommunicationCandidate,
)
from poliscope_engine.contracts.communication import CommunicationRequest
from poliscope_engine.domains.economy import compile_choices
from poliscope_engine.domains.governance import evaluate_governance
from poliscope_engine.domains.communication import evaluate_communication
from ..provisioning.context import binding as context_binding, digest, policy_evidence

MODEL = ('authored:governance-communication', 'v1')


def binding(request, graph, units, mechanisms):
    return digest(dict(context=context_binding(request, graph, units,
        adapter='governance-communication-v1', model=MODEL), policy=policy_evidence(mechanisms)))


def validate_context(request, graph, units):
    gov, communication = request.governance, request.communication
    work = gov.administration
    if work.period_id != communication.period_id:
        fail('decision_communication_period_mismatch')
    if gov.scope_id != communication.scope_id:
        fail('decision_communication_scope_mismatch')
    # DOM-09 has no time/material operating interface. Its finite message and
    # verification slots are disjoint from DOM-02 administration resources.
    first, second = work, communication
    accounts = [*first.batch.accounts, *second.batch.accounts]
    if ({a.id for a in first.batch.accounts} & {a.id for a in second.batch.accounts}
            or {c.id for c in first.batch.claims} & {c.id for c in second.batch.claims}
            or {s.id for s in first.batch.subtotals} & {s.id for s in second.batch.subtotals}):
        fail('decision_communication_overlapping_books')
    entities = {e.id: e.entity_kind for e in graph.registry.entities}
    scopes = {s.id for s in graph.registry.scopes}
    for account in accounts:
        if entities.get(account.id) != 'account' or account.scope_id not in scopes:
            fail('decision_communication_account_identity')
        if account.period_id is not None and account.period_id != work.period_id:
            fail('decision_communication_period_mismatch')
    if any(entities.get(c.claimant_id) != 'population_cohort' for c in first.batch.claims):
        fail('decision_communication_claimant_identity')
    if any(entities.get(h.holder_id) != 'population_cohort' for h in work.holders):
        fail('decision_communication_holder_identity')
    time_ids = {a.id for a in first.batch.accounts
                if units.unit(a.unit_id).dimension == (('time', 1),)}
    if time_ids != {h.account_id for h in work.holders if h.role == 'time'}:
        fail('decision_communication_time_holders')
    AccountBook(first.batch, units)
    AccountBook(second.batch, units)
    compile_choices(work, units)
    claims = index(second.batch.claims)
    demands = {d.claim_id: d for d in communication.demands}
    mappings = [p.claim_id for p in request.prerequisites]
    if (len(demands) != len(communication.demands) or set(demands) != set(claims)
            or len(set(mappings)) != len(mappings) or set(mappings) != set(demands)):
        fail('invalid_decision_communication_mapping')
    proposals = [b for b in gov.bindings if b.id == gov.proposal_binding_id]
    if len(proposals) != 1:
        fail('invalid_governance_proposal')
    for prerequisite in request.prerequisites:
        demand = demands[prerequisite.claim_id]
        affected = {claims[demand.claim_id].account_id}
        if demand.verification_account_id is not None:
            affected.add(demand.verification_account_id)
        if prerequisite.requires_approval:
            if (prerequisite.decision_target_id != gov.target_id
                    or not affected <= set(proposals[0].account_refs)):
                fail('decision_communication_affected_mapping')
        elif prerequisite.decision_target_id is not None:
            fail('decision_communication_independent_target')


def evaluate_pair(request, *, graph, units, mechanisms):
    request = GovernanceCommunicationRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    if mechanisms.units != units:
        fail('decision_communication_policy_units')
    # Validate original inputs before restrictions, even for unresolved decisions.
    # Keep this evidence distinct from the candidate and never reuse allocations.
    preflight = evaluate_communication(request.communication, graph=graph, units=units)
    governance = evaluate_governance(request.governance, graph=graph, units=units,
        mechanisms=mechanisms)
    communication = None
    if governance.status == 'resolved':
        data = request.communication.model_dump()
        if governance.outcome != 'approved':
            blocked = {p.claim_id for p in request.prerequisites if p.requires_approval}
            for demand in data['demands']:
                # Denial only narrows publication prerequisites; every other
                # recorded/access/disclosure/reach/delay unknown stays unknown.
                if demand['claim_id'] in blocked and demand['publish_access'] != 'unknown':
                    demand['publish_access'] = 'denied'
        communication = evaluate_communication(CommunicationRequest.model_validate(data),
            graph=graph, units=units)
    resolved = communication is not None and communication.status == 'resolved'
    candidate = None
    if resolved:
        candidate = GovernanceCommunicationCandidate(
            administration=governance.administration.batch.model_dump(),
            communication=communication.allocation.batch.model_dump())
    return GovernanceCommunicationEvaluation(contract_version=1,
        adapter_version='governance-communication-v1', evidence_status='hypothetical',
        baseline_digest=binding(request, graph, units, mechanisms),
        status='resolved' if resolved else 'unresolved', request=request,
        governance=governance, preflight=preflight, communication=communication,
        candidate=candidate)
