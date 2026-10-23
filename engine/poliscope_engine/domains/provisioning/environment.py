"""One finite extraction/transformation book; residual mass consumes sink budget."""
from fractions import Fraction
from poliscope_engine.accounts import fail, index, quantity
from poliscope_engine.contracts.allocations import FundingRequirement
from poliscope_engine.contracts.environment import EnvironmentRequest
from poliscope_engine.contracts.provisioning import PhaseEvaluation
from poliscope_engine.contracts.provisioning_environment import (
    ProvisioningEnvironmentRequest, ProvisioningEnvironmentEvaluation,
)
from poliscope_engine.domains.economy import evaluate_economy
from poliscope_engine.domains.environment import evaluate_production
from .economy import validate_context as validate_economy_context, evaluate_staged_chain
from .context import binding as context_binding

MODEL = ('authored:provisioning-environment', 'v1')


def binding(request, graph, units):
    return context_binding(request, graph, units,
        adapter='provisioning-environment-v1', model=MODEL)


def validate_context(request, graph, units):
    p = request.provisioning
    validate_economy_context(p, graph, units)
    chain = p.chain
    # This bounded child couples one production stage before downstream phases.
    if len(chain.phases) < 2 or chain.phases[0].kind != 'production' or any(x.kind == 'production' for x in chain.phases[1:]):
        fail('environment_counterpart_production_plan')
    phase = chain.phases[0]
    if (len(set(phase.claim_order)) != len(phase.claim_order)
            or (phase.claim_order and set(phase.claim_order) != {c.id for c in phase.claims})
            or (phase.procedure is not None and set(phase.claim_order) != {c.id for c in phase.claims})):
        fail('invalid_claim_order')
    accounts = index(chain.batch.accounts)
    resources = {r.account_id: r.resource_id for r in chain.resources}
    if (len(resources) != len(chain.resources) or set(resources) !=
            {a.id for a in accounts.values() if a.kind == 'stock' and a.invariant == 'physical'}):
        fail('invalid_resource_bindings')
    boundaries = {b.account_id: b for b in request.boundaries}
    claims = index(phase.claims)
    demands = {d.claim_id: d for d in request.demands}
    sinks = {s.claim_id: s for s in request.sinks}
    choices = {c.claim_id: c for c in phase.choices}
    if (len(boundaries) != len(request.boundaries)
            or len(demands) != len(request.demands) or set(demands) != set(claims)
            or len(sinks) != len(request.sinks) or set(sinks) != set(claims)
            or len(choices) != len(phase.choices) or set(choices) != set(claims)):
        fail('invalid_environment_counterpart_mapping')
    extraction = {b.account_id for b in request.boundaries if b.role == 'extraction_stock'}
    sink_ids = set(boundaries) - extraction
    if (extraction != {c.account_id for c in phase.claims}
            or sink_ids != {s.account_id for s in request.sinks}
            or not set(boundaries) <= set(accounts)):
        fail('invalid_environment_counterpart_accounts')
    if any(resources.get(a) != boundaries[a].resource_id for a in extraction):
        fail('environment_counterpart_resource_mismatch')
    relationships = {r.id: r for r in graph.relationships}
    for cid, sink in sinks.items():
        source = accounts[claims[cid].account_id]
        target = accounts[sink.account_id]
        rel = relationships.get(sink.scope_relationship_id)
        if (rel is None or rel.relationship_kind != 'access'
                or rel.from_id != boundaries[sink.account_id].resource_id
                or rel.to_id != demands[cid].scope_id):
            fail('invalid_environment_sink_scope_reference')
        su, tu = units.unit(source.unit_id), units.unit(target.unit_id)
        if su.dimension != tu.dimension or source.scope_id != target.scope_id:
            fail('environment_counterpart_sink_units_scope')
        choice = choices[cid]
        if source.kind != 'stock' or source.invariant != 'physical' or source.period_id is not None:
            fail('invalid_provisioning_stock')
        if not choice.outputs and not quantity(choice.loss_per_unit):
            fail('missing_production_yields')
        if any(r.account_id not in accounts for r in choice.requirements) or any(o.account_id not in accounts for o in choice.outputs):
            fail('unknown_account')
        if any(accounts[r.account_id].period_id != chain.period_id for r in choice.requirements):
            fail('incompatible_provisioning_period')
        if any(r.account_id in boundaries for r in choice.requirements):
            fail('duplicate_environment_counterpart_requirement')
        residual = quantity(choice.loss_per_unit)
        for output in choice.outputs:
            if output.account_id in extraction:
                fail('environment_counterpart_extraction_replenishment')
            if output.role == 'residual':
                unit = units.unit(accounts[output.account_id].unit_id)
                if unit.dimension != su.dimension:
                    fail('environment_counterpart_residual_units')
                residual += quantity(output.per_unit) * Fraction(unit.scale) / Fraction(su.scale)
        if residual <= 0 or quantity(sink.per_unit) != residual * Fraction(su.scale) / Fraction(tu.scale):
            fail('environment_counterpart_residual_conservation')
    # All later phases keep material stocks distinct from ecological boundaries;
    # they cannot extract again, replenish stocks or spend sink budget unchecked.
    for phase in chain.phases[1:]:
        if any(c.account_id in boundaries for c in phase.claims):
            fail('environment_counterpart_downstream_boundary')
        for choice in (phase.routes if phase.kind == 'freight' else phase.choices):
            if phase.kind == 'freight':
                if choice.destination_id in boundaries or choice.capacity_id in boundaries:
                    fail('environment_counterpart_downstream_boundary')
            elif any(o.account_id in boundaries for o in choice.outputs):
                fail('environment_counterpart_downstream_boundary')
            if any(r.account_id in boundaries for r in choice.requirements):
                fail('environment_counterpart_downstream_boundary')
    for term in p.use_terms:
        if any(r.account_id in boundaries for a in term.activities for r in a.requirements):
            fail('environment_counterpart_downstream_boundary')
    if (any(c.account_id in boundaries for c in p.work.batch.claims)
            or any(r.account_id in boundaries for a in p.work.activities for r in a.requirements)):
        fail('environment_counterpart_work_boundary')
    # Validate ecological roles, canonical references and original postings before
    # work can run. No mutations: the actual staging pass below uses the work book.
    _production(request, chain.batch, graph, units, validate_only=True)


def _production(request, batch, graph, units, *, validate_only=False):
    phase = request.provisioning.chain.phases[0]
    boundaries = {b.account_id: b for b in request.boundaries}
    sinks = {s.claim_id: s for s in request.sinks}
    choices = []
    for choice in phase.choices:
        sink = sinks[choice.claim_id]
        access = ('unknown' if sink.access == 'unknown' or boundaries[sink.account_id].capacity_status == 'unknown'
                  else sink.access)
        access = ('unknown' if 'unknown' in (access, choice.access)
                  else 'denied' if 'denied' in (access, choice.access) else 'allowed')
        choices.append(choice.model_copy(update=dict(access=access,
            requirements=[*choice.requirements, FundingRequirement(account_id=sink.account_id,
                per_unit=sink.per_unit, kind='entitlement')])))
    staged = batch.model_copy(update=dict(claims=[*batch.claims, *phase.claims],
        reservations=[*batch.reservations, *phase.reservations]))
    return evaluate_production(EnvironmentRequest(contract_version=1,
        scope_id=request.demands[0].scope_id, period_id=request.provisioning.chain.period_id,
        batch=staged, boundaries=request.boundaries, demands=request.demands,
        procedure=None if validate_only else phase.procedure,
        claim_order=[] if validate_only else [*[c.id for c in batch.claims], *phase.claim_order] if phase.claim_order else [],
        mechanism_ref=phase.mechanism_ref, source_refs=phase.source_refs),
        choices=choices, closed_claim_ids=[c.id for c in batch.claims], graph=graph, units=units)


def evaluate_pair(request, *, graph, units):
    request = ProvisioningEnvironmentRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    p = request.provisioning
    work = evaluate_economy(p.work, units)
    environment = provisioning = None
    if work.batch is not None:
        environment = _production(request, work.batch, graph, units)
        if environment.status == 'resolved':
            tail = p.model_copy(update={'chain': p.chain.model_copy(update={'phases': p.chain.phases[1:]})})
            provisioning = evaluate_staged_chain(tail, environment.allocation.batch, units)
            first = PhaseEvaluation(phase_id=p.chain.phases[0].id, kind='production', evidence=environment.allocation)
            provisioning = provisioning.model_copy(update=dict(
                phases=[first, *provisioning.phases],
                request=provisioning.request.model_copy(update=dict(batch=work.batch,
                    phases=[p.chain.phases[0], *provisioning.request.phases]))))
    resolved = provisioning is not None and provisioning.status == 'resolved'
    return ProvisioningEnvironmentEvaluation(contract_version=1,
        adapter_version='provisioning-environment-v1', baseline_digest=binding(request, graph, units),
        evidence_status='hypothetical', status='resolved' if resolved else 'unresolved',
        request=request, work=work, environment=environment, provisioning=provisioning,
        batch=provisioning.batch if resolved else None)
