"""Education prerequisites and economy share one pure allocation."""
from poliscope_engine.accounts import fail
from poliscope_engine.contracts.economy_education import EconomyEducationRequest, EconomyEducationEvaluation
from poliscope_engine.domains.knowledge_culture import evaluate_education
from ..provisioning.context import binding as context_binding, digest, policy_evidence
from . import evaluate_economy

MODEL = ('authored:economy-education', 'v1')


def binding(request, graph, units, mechanisms):
    return digest(dict(context=context_binding(request, graph, units,
        adapter='economy-education-v1', model=MODEL), policy=policy_evidence(mechanisms)))


def validate_context(request, graph, units):
    if request.education.work != request.economy:
        fail('education_counterpart_work_mismatch')
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
    request = EconomyEducationRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    if mechanisms.units != units:
        fail('education_counterpart_policy_units')
    education = evaluate_education(request.education, graph=graph, units=units, mechanisms=mechanisms)
    economy = None
    if education.status == 'resolved':
        # Pure recomputation from the original book, never from education's output.
        economy = evaluate_economy(request.economy, units)
        if economy != education.work.evaluation:
            fail('education_counterpart_staging_mismatch')
    resolved = economy is not None and economy.status == 'resolved'
    return EconomyEducationEvaluation(contract_version=1, adapter_version='economy-education-v1',
        baseline_digest=binding(request, graph, units, mechanisms), evidence_status='hypothetical',
        status='resolved' if resolved else 'unresolved', request=request, education=education,
        economy=economy, batch=economy.batch if resolved else None)
