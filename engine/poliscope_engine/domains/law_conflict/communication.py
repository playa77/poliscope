"""Actual case work preserves finite message budgets and original disclosure."""
from poliscope_engine.accounts import AccountBook, fail, index
from poliscope_engine.contracts.adjudication_communication import (
    AdjudicationCommunicationRequest, AdjudicationCommunicationEvaluation,
    AdjudicationCommunicationCandidate,
)
from poliscope_engine.contracts.communication import CommunicationRequest
from poliscope_engine.domains.economy import compile_choices
from poliscope_engine.domains.law_conflict import evaluate_adjudication
from poliscope_engine.domains.communication import evaluate_communication
from ..provisioning.context import binding as context_binding, digest, policy_evidence

MODEL = ('authored:adjudication-communication', 'v1')


def binding(request, graph, units, mechanisms):
    return digest(dict(context=context_binding(request, graph, units,
        adapter='adjudication-communication-v1', model=MODEL), policy=policy_evidence(mechanisms)))


def validate_context(request, graph, units):
    legal, communication = request.adjudication, request.communication
    work = legal.administration
    if work.period_id != communication.period_id:
        fail('adjudication_communication_period_mismatch')
    if legal.scope_id != communication.scope_id:
        fail('adjudication_communication_scope_mismatch')
    # DOM-09 has no time/material operating interface. Its finite message and
    # verification slots are disjoint from DOM-02 administration resources.
    first, second = work, communication
    accounts = [*first.batch.accounts, *second.batch.accounts]
    if ({a.id for a in first.batch.accounts} & {a.id for a in second.batch.accounts}
            or {c.id for c in first.batch.claims} & {c.id for c in second.batch.claims}
            or {s.id for s in first.batch.subtotals} & {s.id for s in second.batch.subtotals}):
        fail('adjudication_communication_overlapping_books')
    entities = {e.id: e.entity_kind for e in graph.registry.entities}
    scopes = {s.id for s in graph.registry.scopes}
    for account in accounts:
        if entities.get(account.id) != 'account' or account.scope_id not in scopes:
            fail('adjudication_communication_account_identity')
        if account.period_id is not None and account.period_id != work.period_id:
            fail('adjudication_communication_period_mismatch')
    if any(entities.get(c.claimant_id) != 'population_cohort' for c in first.batch.claims):
        fail('adjudication_communication_claimant_identity')
    if any(entities.get(h.holder_id) != 'population_cohort' for h in work.holders):
        fail('adjudication_communication_holder_identity')
    time_ids = {a.id for a in first.batch.accounts
                if units.unit(a.unit_id).dimension == (('time', 1),)}
    if time_ids != {h.account_id for h in work.holders if h.role == 'time'}:
        fail('adjudication_communication_time_holders')
    AccountBook(first.batch, units)
    AccountBook(second.batch, units)
    compile_choices(work, units)
    claims = index(second.batch.claims)
    demands = {d.claim_id: d for d in communication.demands}
    mappings = [p.claim_id for p in request.prerequisites]
    if (len(demands) != len(communication.demands) or set(demands) != set(claims)
            or len(set(mappings)) != len(mappings) or set(mappings) != set(demands)):
        fail('invalid_adjudication_communication_mapping')
    cases = index(legal.cases)
    channels = {c.asset_id: c for c in communication.channels}
    for prerequisite in request.prerequisites:
        if prerequisite.case_id is None:
            continue
        demand = demands[prerequisite.claim_id]
        case = cases.get(prerequisite.case_id)
        channel = channels.get(demand.channel_asset_id)
        bindings = [b for b in legal.bindings if case is not None and b.id == case.binding_id]
        affected = {claims[demand.claim_id].account_id}
        if demand.verification_account_id is not None:
            affected.add(demand.verification_account_id)
        if (case is None or channel is None or len(bindings) != 1
                or case.claimant_id != demand.recipient_id
                or case.authority_id != channel.controller_id
                or case.target_id != demand.channel_asset_id
                or not demand.obligation_refs
                or not set(demand.obligation_refs) <= set(case.obligation_refs)
                or not affected <= set(bindings[0].account_refs)):
            fail('adjudication_communication_affected_mapping')


def evaluate_pair(request, *, graph, units, mechanisms):
    request = AdjudicationCommunicationRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    if mechanisms.units != units:
        fail('adjudication_communication_policy_units')
    # Validate original inputs before restrictions, even for unresolved cases.
    # Keep this evidence distinct from the candidate and never reuse allocations.
    preflight = evaluate_communication(request.communication, graph=graph, units=units)
    adjudication = evaluate_adjudication(request.adjudication, graph=graph, units=units,
        mechanisms=mechanisms)
    communication = None
    if adjudication.status == 'resolved':
        data = request.communication.model_dump()
        outcomes = {r.case_id: r.outcome for r in adjudication.results}
        blocked = {p.claim_id for p in request.prerequisites
                   if p.case_id is not None and outcomes[p.case_id] != 'upheld'}
        if blocked:
            for demand in data['demands']:
                # Denial only narrows publication prerequisites; every other
                # recorded/access/disclosure/reach/delay unknown stays unknown.
                if demand['claim_id'] in blocked and demand['publish_access'] != 'unknown':
                    demand['publish_access'] = 'denied'
        communication = evaluate_communication(CommunicationRequest.model_validate(data),
            graph=graph, units=units)
    resolved = (communication is not None and communication.status == 'resolved'
                and preflight.status == 'resolved')
    candidate = None
    if resolved:
        candidate = AdjudicationCommunicationCandidate(
            administration=adjudication.administration.evaluation.batch.model_dump(),
            communication=communication.allocation.batch.model_dump())
    return AdjudicationCommunicationEvaluation(contract_version=1,
        adapter_version='adjudication-communication-v1', evidence_status='hypothetical',
        baseline_digest=binding(request, graph, units, mechanisms),
        status='resolved' if resolved else 'unresolved', request=request,
        adjudication=adjudication, preflight=preflight, communication=communication,
        candidate=candidate)
