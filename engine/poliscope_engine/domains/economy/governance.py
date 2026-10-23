"""Actual institutional decision restricts economy over one staged finite book."""
from poliscope_engine.accounts import AccountBook, fail, index, quantity
from poliscope_engine.contracts.economy_governance import (
    EconomyGovernanceRequest, EconomyGovernanceEvaluation,
)
from poliscope_engine.contracts.economy import EconomyRequest
from poliscope_engine.domains.governance import evaluate_governance
from . import evaluate_economy
from ..provisioning.context import binding as context_binding, digest, policy_evidence

MODEL = ('authored:economy-governance', 'v1')


def binding(request, graph, units, mechanisms):
    return digest(dict(context=context_binding(request, graph, units,
        adapter='economy-governance-v1', model=MODEL), policy=policy_evidence(mechanisms)))


def closed(activity):
    return (activity.eligibility == 'denied' and quantity(activity.access_limit) == 0
            and activity.terms_known and not activity.requirements)


def validate_context(request, graph, units):
    admin, economy = request.governance.administration, request.economy
    if admin.batch != economy.batch or admin.holders != economy.holders:
        fail('governance_counterpart_book_mismatch')
    if admin.period_id != economy.period_id:
        fail('governance_counterpart_period_mismatch')
    book = AccountBook(admin.batch, units)
    claims = index(book.batch.claims)
    economic, governed = set(request.economic_claim_ids), set(request.governed_claim_ids)
    if (len(economic) != len(request.economic_claim_ids)
            or len(governed) != len(request.governed_claim_ids)
            or not governed <= economic or not economic <= claims.keys()
            or economic & set(request.governance.administrative_claim_ids)):
        fail('invalid_governance_counterpart_claims')
    entities = {e.id: e.entity_kind for e in graph.registry.entities}
    scopes = {s.id for s in graph.registry.scopes}
    for account in book.batch.accounts:
        if entities.get(account.id) != 'account' or account.scope_id not in scopes:
            fail('governance_counterpart_account_identity')
        if account.period_id is not None and account.period_id != economy.period_id:
            fail('governance_counterpart_period_mismatch')
    if any(entities.get(c.claimant_id) not in ('population_cohort', 'institution')
           for c in claims.values()):
        fail('governance_counterpart_claimant_identity')
    if any(entities.get(h.holder_id) != 'population_cohort' for h in economy.holders):
        fail('governance_counterpart_holder_identity')
    time_ids = {a.id for a in book.batch.accounts
                if units.unit(a.unit_id).dimension == (('time', 1),)}
    if time_ids != {h.account_id for h in economy.holders if h.role == 'time'}:
        fail('governance_counterpart_time_holders')
    proposals = [b for b in request.governance.bindings
                 if b.id == request.governance.proposal_binding_id]
    if len(proposals) != 1:
        fail('invalid_governance_proposal')
    proposal = proposals[0]
    # Explicit affected-account evidence is essential: an unrelated decision
    # cannot grant permission to use any account merely by being approved.
    accounts = index(book.batch.accounts)
    if any(claims[c].account_id not in proposal.account_refs
           or accounts[claims[c].account_id].scope_id != request.governance.scope_id
           for c in governed):
        fail('governance_counterpart_affected_account')
    for phase, closed_ids in ((admin, economic), (economy, set(claims) - economic)):
        activities = {a.claim_id: a for a in phase.activities}
        if len(activities) != len(phase.activities) or set(activities) != set(claims):
            fail('invalid_economy_activities')
        if any(not closed(activities[c]) for c in closed_ids):
            fail('governance_counterpart_open_phase_claim')
        # Detached preflight validates the declared terms; its allocations are
        # discarded. The candidate uses only the actual staged administration book.
        from poliscope_engine.domains.economy import compile_choices
        compile_choices(phase, units)


def evaluate_pair(request, *, graph, units, mechanisms):
    request = EconomyGovernanceRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    if mechanisms.units != units:
        fail('governance_counterpart_policy_units')
    governance = evaluate_governance(request.governance, graph=graph,
        mechanisms=mechanisms, units=units)
    economy = None
    if governance.status == 'resolved':
        data = request.economy.model_dump()
        data['batch'] = governance.administration.batch.model_dump()
        if governance.outcome != 'approved':
            for activity in data['activities']:
                if activity['claim_id'] in request.governed_claim_ids and activity['eligibility'] != 'unknown':
                    activity['eligibility'] = 'denied'
        economy = evaluate_economy(EconomyRequest.model_validate(data), units)
    resolved = economy is not None and economy.status == 'resolved'
    return EconomyGovernanceEvaluation(contract_version=1,
        adapter_version='economy-governance-v1', evidence_status='hypothetical',
        baseline_digest=binding(request, graph, units, mechanisms),
        status='resolved' if resolved else 'unresolved', request=request,
        governance=governance, economy=economy, batch=economy.batch if resolved else None)
