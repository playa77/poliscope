"""Pure bounded static phases over one canonical stock/capacity book.

Host-selected data is not model activation permission. No clock, IO or publication.
"""
from poliscope_engine.accounts import AccountBook, fail, index, quantity
from poliscope_engine.allocations import allocate
from poliscope_engine.contracts.accounts import AccountBatch
from poliscope_engine.contracts.allocations import AllocationChoice, AllocationRequest
from poliscope_engine.contracts.logistics import LogisticsRequest
from poliscope_engine.contracts.provisioning import (
    ProvisioningRequest, ProvisioningEvaluation, PhaseEvaluation,
)
from .logistics import transport


def closed_choice(claim_id, phase):
    return AllocationChoice(claim_id=claim_id, access='denied', access_limit='0',
        funding_known=True, requirements=[], outputs=[], loss_per_unit='0',
        mechanism_ref=phase.mechanism_ref, source_refs=phase.source_refs)


def evaluate_chain(request, units):
    request = ProvisioningRequest.model_validate_json(request.model_dump_json())
    batch = AccountBook(request.batch, units).batch
    definitions = index(batch.accounts)
    resources = {r.account_id: r.resource_id for r in request.resources}
    stocks = {a.id for a in definitions.values() if a.kind == 'stock' and a.invariant == 'physical'}
    if len(resources) != len(request.resources) or set(resources) != stocks:
        fail('invalid_resource_bindings')
    if len({p.id for p in request.phases}) != len(request.phases):
        fail('duplicate_phase')
    phases = []
    for phase in request.phases:
        closed = [c.id for c in batch.claims]
        current = index(phase.claims)
        # Order names only this phase, so stale claims cannot accidentally retry.
        if (len(phase.claim_order) != len(set(phase.claim_order))
                or (phase.claim_order and set(phase.claim_order) != set(current))
                or (phase.procedure is not None and set(phase.claim_order) != set(current))):
            fail('invalid_claim_order')
        candidate = AccountBatch.model_validate(batch.model_dump() | {
            'claims': [*batch.claims, *phase.claims],
            'reservations': [*batch.reservations, *phase.reservations],
        })
        # Catch collisions and invalid holds before selecting arithmetic.
        AccountBook(candidate, units)
        for claim in phase.claims:
            if claim.account_id not in stocks or definitions[claim.account_id].period_id is not None:
                fail('invalid_provisioning_stock')
        order = [*closed, *phase.claim_order] if phase.claim_order else []
        if phase.kind == 'freight':
            evidence = transport(LogisticsRequest(contract_version=1, batch=candidate,
                period_id=request.period_id, resources=request.resources,
                routes=phase.routes, closed_claim_ids=closed, procedure=phase.procedure,
                claim_order=order, mechanism_ref=phase.mechanism_ref,
                source_refs=phase.source_refs), units)
            status = evidence.allocation.status
        else:
            choices = {c.claim_id: c for c in phase.choices}
            if len(choices) != len(phase.choices) or set(choices) != set(current):
                fail('invalid_choices')
            for cid, choice in choices.items():
                source = definitions[current[cid].account_id]
                for requirement in choice.requirements:
                    account = definitions.get(requirement.account_id)
                    if account is None:
                        fail('unknown_account')
                    if account.period_id != request.period_id:
                        fail('incompatible_provisioning_period')
                if phase.kind == 'production' and not (choice.outputs or quantity(choice.loss_per_unit)):
                    fail('missing_production_yields')
                if phase.kind == 'use' and (choice.outputs or quantity(choice.loss_per_unit)):
                    fail('invalid_use_outputs')
                if phase.kind == 'storage':
                    # Explicit finite handling, not invented time-dependent loss.
                    if not choice.outputs or quantity(choice.loss_per_unit):
                        fail('invalid_storage_outputs')
                    for output in choice.outputs:
                        target = definitions.get(output.account_id)
                        if (target is None or output.role != 'product'
                                or resources.get(target.id) != resources[source.id]
                                or target.unit_id != source.unit_id):
                            fail('incompatible_storage_resource')
            evidence = allocate(AllocationRequest(contract_version=1, batch=candidate,
                procedure=phase.procedure, claim_order=order,
                choices=[*[closed_choice(cid, phase) for cid in closed], *phase.choices],
                mechanism_ref=phase.mechanism_ref, source_refs=phase.source_refs), units)
            status = evidence.status
        phases.append(PhaseEvaluation(phase_id=phase.id, kind=phase.kind, evidence=evidence))
        if status == 'unresolved':
            return ProvisioningEvaluation(contract_version=1, status=status, request=request,
                phases=phases, blocked_phase_id=phase.id, batch=None, accounts=None)
        batch = evidence.batch
    return ProvisioningEvaluation(contract_version=1, status='resolved', request=request,
        phases=phases, blocked_phase_id=None, batch=batch, accounts=AccountBook(batch, units).evaluate())
