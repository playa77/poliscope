"""Canonical beneficiary obligations and economy share one pure allocation."""
from poliscope_engine.accounts import fail
from poliscope_engine.contracts.economy_care import EconomyCareRequest, EconomyCareEvaluation
from poliscope_engine.domains.social_organization import evaluate_care
from ..provisioning.context import binding as context_binding
from . import evaluate_economy

MODEL = ('authored:economy-care', 'v1')


def binding(request, graph, units):
    return context_binding(request, graph, units, adapter='economy-care-v1', model=MODEL)


def validate_context(request, graph, units):
    if request.care.work != request.economy:
        fail('care_counterpart_work_mismatch')
    entities = {e.id: e.entity_kind for e in graph.registry.entities}
    scopes = {s.id: s.scope_kind for s in graph.registry.scopes}
    work = request.economy
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
    for holder in work.holders:
        if entities.get(holder.holder_id) != 'population_cohort':
            fail('counterpart_holder_identity')
    for claim in work.batch.claims:
        if entities.get(claim.claimant_id) != 'population_cohort':
            fail('counterpart_claimant_identity')


def evaluate_pair(request, *, graph, units):
    request = EconomyCareRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    care = evaluate_care(request.care, graph=graph, units=units)
    economy = None
    if care.status == 'resolved':
        # Pure recomputation from the original book, never from care's output.
        economy = evaluate_economy(request.economy, units)
        if economy != care.work.evaluation:
            fail('care_counterpart_staging_mismatch')
    resolved = economy is not None and economy.status == 'resolved'
    return EconomyCareEvaluation(contract_version=1, adapter_version='economy-care-v1',
        baseline_digest=binding(request, graph, units), evidence_status='hypothetical',
        status='resolved' if resolved else 'unresolved', request=request, care=care,
        economy=economy, batch=economy.batch if resolved else None)
