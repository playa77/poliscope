"""Real DOM-02 work/access -> DOM-01 phases, over one private staged book."""
from poliscope_engine.accounts import fail, index
from poliscope_engine.contracts.economy import EconomyRequest, EconomyActivity
from poliscope_engine.contracts.provisioning import ProvisioningRequest, ProvisioningEvaluation
from poliscope_engine.contracts.provisioning_economy import (
    ProvisioningEconomyRequest, ProvisioningEconomyEvaluation,
)
from poliscope_engine.domains.economy import evaluate_economy, compile_choices
from .chain import evaluate_chain
from .context import binding


def validate_context(request, graph, units, *, work_only=True):
    if request.work.batch != request.chain.batch:
        fail('counterpart_batch_mismatch')
    if request.work.period_id != request.chain.period_id:
        fail('counterpart_period_mismatch')
    entities = {e.id: e.entity_kind for e in graph.registry.entities}
    scopes = {s.id: s.scope_kind for s in graph.registry.scopes}
    batch = request.work.batch
    accounts = index(batch.accounts)
    time_accounts = {a.id for a in batch.accounts
                     if units.unit(a.unit_id).dimension == (('time', 1),)}
    if time_accounts != {h.account_id for h in request.work.holders if h.role == 'time'}:
        fail('counterpart_time_holders')
    for account in batch.accounts:
        if entities.get(account.id) != 'account':
            fail('counterpart_account_identity')
        if scopes.get(account.scope_id) not in ('settlement', 'region'):
            fail('counterpart_scope_identity')
        if account.period_id is not None and account.period_id != request.work.period_id:
            fail('counterpart_period_mismatch')
    for resource in request.chain.resources:
        if entities.get(resource.resource_id) != 'resource':
            fail('counterpart_resource_identity')
    for holder in request.work.holders:
        if entities.get(holder.holder_id) != 'population_cohort':
            fail('counterpart_holder_identity')
    for claim in [*batch.claims, *(c for p in request.chain.phases for c in p.claims)]:
        if entities.get(claim.claimant_id) not in ('population_cohort', 'institution'):
            fail('counterpart_claimant_identity')
    if work_only and any(a.kind == 'goods' for a in request.work.activities):
        fail('counterpart_work_only')
    for claim in batch.claims:
        if claim.account_id not in accounts:
            fail('unknown_account')
    terms = {t.phase_id: t for t in request.use_terms}
    uses = {p.id: p for p in request.chain.phases if p.kind == 'use'}
    if len(terms) != len(request.use_terms) or set(terms) != set(uses):
        fail('counterpart_use_terms')
    if len({p.id for p in request.chain.phases}) != len(request.chain.phases):
        fail('duplicate_phase')
    for pid, phase in uses.items():
        activities = terms[pid].activities
        if (phase.choices or any(a.kind != 'goods' for a in activities)
                or len({a.claim_id for a in activities}) != len(activities)
                or {a.claim_id for a in activities} != {c.id for c in phase.claims}):
            fail('counterpart_use_terms')


def evaluate_pair(request, *, graph, units):
    request = ProvisioningEconomyRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    work = evaluate_economy(request.work, units)
    def report(provisioning):
        resolved = provisioning is not None and provisioning.status == 'resolved'
        return ProvisioningEconomyEvaluation(contract_version=1, evidence_status='hypothetical',
            adapter_version='provisioning-economy-v1', baseline_digest=binding(request, graph, units),
            status='resolved' if resolved else 'unresolved', request=request, work=work,
            provisioning=provisioning, batch=provisioning.batch if resolved else None)
    if work.batch is None:
        return report(None)
    return report(evaluate_staged_chain(request, work.batch, units))


def evaluate_staged_chain(request, batch, units):
    """Continue a validated pair from an already allocated private input book.

    Earlier claims are closed in every phase; input commitments are never retried.
    The caller owns prerequisite evaluation and validates the original context.
    """
    initial = batch
    evidence, compiled = [], []
    terms = {t.phase_id: t for t in request.use_terms}
    for phase in request.chain.phases:
        if phase.kind == 'use':
            accounts = index(batch.accounts)
            # Prior claims are explicitly closed. Recompilation validates terms
            # against actual staged quantities; no earlier claim is retried.
            closed = [EconomyActivity(claim_id=c.id,
                kind='goods' if accounts[c.account_id].kind == 'stock' else 'care',
                eligibility='denied', access_limit='0', terms_known=True,
                requirements=[], mechanism_ref=phase.mechanism_ref,
                source_refs=phase.source_refs) for c in batch.claims]
            economy = EconomyRequest(contract_version=1, period_id=request.work.period_id,
                batch=batch.model_copy(update={'claims': [*batch.claims, *phase.claims]}),
                holders=request.work.holders, activities=[*closed, *terms[phase.id].activities],
                procedure=phase.procedure,
                claim_order=[*[c.id for c in batch.claims], *phase.claim_order]
                    if phase.claim_order else [],
                mechanism_ref=phase.mechanism_ref, source_refs=phase.source_refs)
            choices = compile_choices(economy, units)
            ids = {c.id for c in phase.claims}
            phase = phase.model_copy(update={'choices': [c for c in choices if c.claim_id in ids]})
        compiled.append(phase)
        result = evaluate_chain(ProvisioningRequest(contract_version=1,
            period_id=request.chain.period_id, batch=batch,
            resources=request.chain.resources, phases=[phase]), units)
        evidence.extend(result.phases)
        if result.batch is None:
            break
        batch = result.batch
    provisioning = ProvisioningEvaluation(contract_version=1, status=result.status,
        request=request.chain.model_copy(update={'batch': initial, 'phases': compiled}),
        phases=evidence, blocked_phase_id=result.blocked_phase_id,
        batch=result.batch, accounts=result.accounts)
    return provisioning
