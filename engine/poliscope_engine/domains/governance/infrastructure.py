"""Actual scoped decisions restrict explicitly dependent finite facility/path access."""
from poliscope_engine.accounts import AccountBook, fail, index
from poliscope_engine.contracts.governance_infrastructure import (
    GovernanceInfrastructureRequest, GovernanceInfrastructureEvaluation,
    GovernanceInfrastructureCandidate,
)
from poliscope_engine.contracts.infrastructure import InfrastructureRequest
from poliscope_engine.domains.economy import compile_choices
from poliscope_engine.domains.governance import evaluate_governance
from poliscope_engine.domains.infrastructure import evaluate_infrastructure
from ..provisioning.context import binding as context_binding, digest, policy_evidence

MODEL = ('authored:governance-infrastructure', 'v1')


def binding(request, graph, units, mechanisms):
    return digest(dict(context=context_binding(request, graph, units,
        adapter='governance-infrastructure-v1', model=MODEL), policy=policy_evidence(mechanisms)))


def validate_context(request, graph, units):
    gov, infrastructure = request.governance, request.infrastructure
    work = gov.administration
    if work.period_id != infrastructure.period_id:
        fail('decision_infrastructure_period_mismatch')
    if gov.scope_id != infrastructure.scope_id:
        fail('decision_infrastructure_scope_mismatch')
    # DOM-08 declares facility slots, not maintenance time or operating costs.
    # Administration retains its own canonical DOM-02 time/resource book.
    first, second = work, infrastructure
    accounts = [*first.batch.accounts, *second.batch.accounts]
    if ({a.id for a in first.batch.accounts} & {a.id for a in second.batch.accounts}
            or {c.id for c in first.batch.claims} & {c.id for c in second.batch.claims}
            or {s.id for s in first.batch.subtotals} & {s.id for s in second.batch.subtotals}):
        fail('decision_infrastructure_overlapping_books')
    entities = {e.id: e.entity_kind for e in graph.registry.entities}
    scopes = {s.id for s in graph.registry.scopes}
    for account in accounts:
        if entities.get(account.id) != 'account' or account.scope_id not in scopes:
            fail('decision_infrastructure_account_identity')
        if account.period_id is not None and account.period_id != work.period_id:
            fail('decision_infrastructure_period_mismatch')
    if any(entities.get(c.claimant_id) != 'population_cohort' for c in first.batch.claims):
        fail('decision_infrastructure_claimant_identity')
    if any(entities.get(h.holder_id) != 'population_cohort' for h in work.holders):
        fail('decision_infrastructure_holder_identity')
    time_ids = {a.id for a in first.batch.accounts
                if units.unit(a.unit_id).dimension == (('time', 1),)}
    if time_ids != {h.account_id for h in work.holders if h.role == 'time'}:
        fail('decision_infrastructure_time_holders')
    AccountBook(first.batch, units)
    AccountBook(second.batch, units)
    compile_choices(work, units)
    claims = index(second.batch.claims)
    demands = {d.claim_id: d for d in infrastructure.demands}
    mappings = [p.claim_id for p in request.prerequisites]
    if (len(demands) != len(infrastructure.demands) or set(demands) != set(claims)
            or len(set(mappings)) != len(mappings) or set(mappings) != set(demands)):
        fail('invalid_decision_infrastructure_mapping')
    proposals = [b for b in gov.bindings if b.id == gov.proposal_binding_id]
    if len(proposals) != 1:
        fail('invalid_governance_proposal')
    for prerequisite in request.prerequisites:
        demand = demands[prerequisite.claim_id]
        affected = {claims[demand.claim_id].account_id}
        links = {link.asset_id: link for link in infrastructure.links}
        affected.update(links[lid].account_id for lid in demand.path if lid in links)
        if prerequisite.requires_approval:
            if (prerequisite.decision_target_id != gov.target_id
                    or not affected <= set(proposals[0].account_refs)):
                fail('decision_infrastructure_affected_mapping')
        elif prerequisite.decision_target_id is not None:
            fail('decision_infrastructure_independent_target')


def evaluate_pair(request, *, graph, units, mechanisms):
    request = GovernanceInfrastructureRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    if mechanisms.units != units:
        fail('decision_infrastructure_policy_units')
    # Validate original inputs before restrictions, even for unresolved decisions.
    # Keep this evidence distinct from the candidate and never reuse allocations.
    preflight = evaluate_infrastructure(request.infrastructure, graph=graph, units=units)
    governance = evaluate_governance(request.governance, graph=graph, units=units,
        mechanisms=mechanisms)
    infrastructure = None
    if governance.status == 'resolved':
        data = request.infrastructure.model_dump()
        if governance.outcome != 'approved':
            blocked = {p.claim_id for p in request.prerequisites if p.requires_approval}
            for demand in data['demands']:
                # Denial only narrows new access; topology, availability, limits,
                # prior commitments and unknown inputs retain their original meaning.
                if demand['claim_id'] in blocked and demand['access'] != 'unknown':
                    demand['access'] = 'denied'
        infrastructure = evaluate_infrastructure(InfrastructureRequest.model_validate(data),
            graph=graph, units=units)
    resolved = infrastructure is not None and infrastructure.status == 'resolved'
    candidate = None
    if resolved:
        candidate = GovernanceInfrastructureCandidate(
            administration=governance.administration.batch.model_dump(),
            infrastructure=infrastructure.allocation.batch.model_dump())
    return GovernanceInfrastructureEvaluation(contract_version=1,
        adapter_version='governance-infrastructure-v1', evidence_status='hypothetical',
        baseline_digest=binding(request, graph, units, mechanisms),
        status='resolved' if resolved else 'unresolved', request=request,
        governance=governance, preflight=preflight, infrastructure=infrastructure,
        candidate=candidate)
