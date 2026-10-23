"""Pure extraction/sink allowance prerequisites over canonical finite accounts."""
from fractions import Fraction
from poliscope_engine.accounts import AccountBook, fail, index, quantity
from poliscope_engine.allocations import allocate, encoded
from poliscope_engine.contracts.allocations import AllocationChoice, AllocationRequest
from poliscope_engine.contracts.environment import (
    EnvironmentRequest, EnvironmentEvaluation, EnvironmentalReadiness, EcologicalBoundaryResult,
)


def evaluate_environment(request, *, graph, units):
    return _evaluate(request, graph=graph, units=units)


def evaluate_production(request, *, choices, closed_claim_ids, graph, units):
    """Trusted composition: transform extraction once in the complete shared book.

    Boundaries may be a subset of this book; demands name exactly new extraction
    claims. Previously evaluated claims are closed, never retried. The caller
    validates residual/sink coefficients and supplies actual production choices.
    Environmental access can only restrict those choices.
    """
    from poliscope_engine.contracts.allocations import AllocationChoice
    choices = [AllocationChoice.model_validate_json(c.model_dump_json()) for c in choices]
    return _evaluate(request, graph=graph, units=units,
                     production_choices=choices, closed_claim_ids=tuple(closed_claim_ids))


def _evaluate(request, *, graph, units, production_choices=None, closed_claim_ids=()):
    request = EnvironmentRequest.model_validate_json(request.model_dump_json())
    entities = {e.id: e for e in graph.registry.entities}
    scopes = {s.id: s for s in graph.registry.scopes}
    relationships = {r.id: r for r in graph.relationships}

    def scope(sid):
        if sid not in scopes or scopes[sid].scope_kind not in ('settlement', 'region'):
            fail('invalid_environment_scope')

    scope(request.scope_id)
    accounts, claims = index(request.batch.accounts), index(request.batch.claims)
    boundaries = {b.account_id: b for b in request.boundaries}
    demands = {d.claim_id: d for d in request.demands}
    if (len(boundaries) != len(request.boundaries)
            or (set(boundaries) != set(accounts) if production_choices is None
                else not set(boundaries) <= set(accounts))
            or len({(b.resource_id, b.role) for b in request.boundaries}) != len(boundaries)):
        fail('duplicate_or_unmapped_ecological_boundary')
    if (len(demands) != len(request.demands)
            or len(set(closed_claim_ids)) != len(closed_claim_ids)
            or set(demands) & set(closed_claim_ids)
            or set(demands) | set(closed_claim_ids) != set(claims)):
        fail('invalid_environment_demands')
    for boundary in request.boundaries:
        resource = entities.get(boundary.resource_id)
        if resource is None or resource.entity_kind != 'resource':
            fail('invalid_environment_resource')
        account = accounts[boundary.account_id]
        scope(account.scope_id)
        expected = ('stock', 'physical', None) if boundary.role == 'extraction_stock' else (
            'capacity', 'budget', request.period_id)
        if (account.kind, account.invariant, account.period_id) != expected:
            fail('invalid_environment_account')
        if not units.unit(account.unit_id).dimension:
            fail('dimensionless_environment_account')
        if boundary.selected_limit is not None:
            quantity(boundary.selected_limit)
            if boundary.policy_ref is None:
                fail('missing_environment_policy_reference')

    choices, findings_by_claim = [], {}
    for demand in request.demands:
        scope(demand.scope_id)
        claim = claims[demand.claim_id]
        boundary = boundaries.get(claim.account_id)
        claimant = entities.get(claim.claimant_id)
        if (boundary is None or claimant is None
                or claimant.entity_kind not in ('institution', 'population_cohort')
                or quantity(claim.requested) <= 0):
            fail('invalid_environment_claim')
        rel = relationships.get(demand.scope_relationship_id)
        if (rel is None or rel.relationship_kind != 'access'
                or rel.from_id != boundary.resource_id or rel.to_id != demand.scope_id):
            fail('invalid_environment_scope_reference')
        findings = []
        if boundary.capacity_status == 'unknown':
            findings.append('unknown_physical_boundary')
        if demand.access != 'allowed':
            findings.append('access_' + demand.access)
        findings_by_claim[claim.id] = findings
        unknown = boundary.capacity_status == 'unknown' or demand.access == 'unknown'
        choices.append(AllocationChoice(claim_id=claim.id,
            access='unknown' if unknown else demand.access,
            access_limit=demand.access_limit, funding_known=True, requirements=[], outputs=[],
            loss_per_unit='0', mechanism_ref=request.mechanism_ref, source_refs=demand.source_refs))

    if production_choices is not None:
        authored = {c.claim_id: c for c in production_choices}
        if len(authored) != len(production_choices) or set(authored) != set(demands):
            fail('invalid_environment_production_choices')
        merged = []
        for environmental in choices:
            choice = authored[environmental.claim_id]
            access = ('unknown' if 'unknown' in (environmental.access, choice.access)
                      else 'denied' if 'denied' in (environmental.access, choice.access)
                      else 'allowed')
            merged.append(choice.model_copy(update=dict(access=access,
                access_limit=encoded(min(quantity(choice.access_limit),
                                         quantity(environmental.access_limit))))))
        choices = [AllocationChoice(claim_id=cid, access='denied', access_limit='0',
            funding_known=True, requirements=[], outputs=[], loss_per_unit='0',
            mechanism_ref=request.mechanism_ref, source_refs=request.source_refs)
            for cid in closed_claim_ids] + merged

    initial = AccountBook(request.batch, units).evaluate()
    prior = {r.claim_id: r.actual for r in initial.claims}
    remaining = {r.claim_id: quantity(r.unmet) for r in initial.claims}
    allocation = allocate(AllocationRequest(contract_version=1, batch=request.batch,
        procedure=request.procedure, claim_order=request.claim_order, choices=choices,
        mechanism_ref=request.mechanism_ref, source_refs=request.source_refs), units)
    unresolved = allocation.status == 'unresolved'
    actuals = {a.claim_id: a for a in allocation.actuals}
    results = []
    for demand in request.demands:
        actual = actuals[demand.claim_id]
        findings = list(findings_by_claim[demand.claim_id])
        if unresolved:
            findings.append('unknown_capacity_allocation')
        elif quantity(actual.unmet) > 0 and not findings and production_choices is not None:
            # Joint material, operating inputs and sink budgets may bind. Do not
            # attribute their shortfall to physical extraction stock alone.
            findings.append('production_access_denied' if actual.reason == 'denied'
                            else 'coupled_input_shortfall')
        elif quantity(actual.unmet) > 0 and not findings:
            if quantity(demand.access_limit) < remaining[demand.claim_id]:
                findings.append('access_limit_shortfall')
            if (quantity(actual.allocated) < min(remaining[demand.claim_id], quantity(demand.access_limit))
                    and not (request.procedure == 'all_or_nothing'
                             and quantity(demand.access_limit) < remaining[demand.claim_id])):
                findings.append('finite_boundary_shortfall')
        results.append(EnvironmentalReadiness(claim_id=demand.claim_id,
            outcome='unresolved' if unresolved else 'blocked' if findings else 'capacity_ready',
            findings=findings, prior=prior[demand.claim_id],
            additional=None if unresolved else actual.allocated, unmet=None if unresolved else actual.unmet))
    boundary_results = []
    for boundary in request.boundaries:
        gross = sum((quantity(p.amount) for p in allocation.batch.postings
                     if p.source_id == boundary.account_id), Fraction())
        status = ('not_selected' if boundary.policy_ref is None else 'unknown'
                  if boundary.selected_limit is None else 'limit_breached'
                  if gross > quantity(boundary.selected_limit) else 'within_limit')
        boundary_results.append(EcologicalBoundaryResult(account_id=boundary.account_id,
            gross_debit=encoded(gross), limit_status=status, candidate_complete=not unresolved))
    return EnvironmentEvaluation(contract_version=1, evidence_status='hypothetical',
        status=allocation.status, request=request, allocation=allocation,
        results=results, boundaries=boundary_results)
