"""Actual case work gates declared finite response access without predicting safety."""
from poliscope_engine.accounts import AccountBook, fail, index
from poliscope_engine.contracts.adjudication_continuity import (
    AdjudicationContinuityRequest, AdjudicationContinuityEvaluation,
    AdjudicationContinuityCandidate,
)
from poliscope_engine.contracts.security_risk import ContinuityRequest
from poliscope_engine.domains.economy import compile_choices
from poliscope_engine.domains.law_conflict import evaluate_adjudication
from poliscope_engine.domains.security_risk import evaluate_continuity
from ..provisioning.context import binding as context_binding, digest, policy_evidence

MODEL = ('authored:adjudication-continuity', 'v1')


def binding(request, graph, units, mechanisms):
    return digest(dict(context=context_binding(request, graph, units,
        adapter='adjudication-continuity-v1', model=MODEL), policy=policy_evidence(mechanisms)))


def validate_context(request, graph, units):
    legal, continuity = request.adjudication, request.continuity
    work = legal.administration
    if work.period_id != continuity.period_id:
        fail('adjudication_continuity_period_mismatch')
    if legal.scope_id != continuity.scope_id:
        fail('adjudication_continuity_scope_mismatch')
    # Continuity slots are disjoint from dated legal administration work.
    # Staff time and operating costs are not declared by DOM-12.
    first, second = work, continuity
    accounts = [*first.batch.accounts, *second.batch.accounts]
    if ({a.id for a in first.batch.accounts} & {a.id for a in second.batch.accounts}
            or {c.id for c in first.batch.claims} & {c.id for c in second.batch.claims}
            or {s.id for s in first.batch.subtotals} & {s.id for s in second.batch.subtotals}):
        fail('adjudication_continuity_overlapping_books')
    entities = {e.id: e.entity_kind for e in graph.registry.entities}
    scopes = {s.id for s in graph.registry.scopes}
    for account in accounts:
        if entities.get(account.id) != 'account' or account.scope_id not in scopes:
            fail('adjudication_continuity_account_identity')
        if account.period_id is not None and account.period_id != work.period_id:
            fail('adjudication_continuity_period_mismatch')
    if any(entities.get(c.claimant_id) != 'population_cohort' for c in first.batch.claims):
        fail('adjudication_continuity_claimant_identity')
    if any(entities.get(h.holder_id) != 'population_cohort' for h in work.holders):
        fail('adjudication_continuity_holder_identity')
    time_ids = {a.id for a in first.batch.accounts
                if units.unit(a.unit_id).dimension == (('time', 1),)}
    if time_ids != {h.account_id for h in work.holders if h.role == 'time'}:
        fail('adjudication_continuity_time_holders')
    AccountBook(first.batch, units)
    AccountBook(second.batch, units)
    compile_choices(work, units)
    claims = index(second.batch.claims)
    demands = {d.claim_id: d for d in continuity.demands}
    mappings = [p.claim_id for p in request.prerequisites]
    if (len(demands) != len(continuity.demands) or set(demands) != set(claims)
            or len(set(mappings)) != len(mappings) or set(mappings) != set(demands)):
        fail('invalid_adjudication_continuity_mapping')
    cases = index(legal.cases)
    facilities = {f.asset_id: f for f in continuity.facilities}
    for prerequisite in request.prerequisites:
        if prerequisite.case_id is None:
            continue
        demand = demands[prerequisite.claim_id]
        case = cases.get(prerequisite.case_id)
        facility = facilities.get(demand.facility_asset_id)
        bindings = [b for b in legal.bindings if case is not None and b.id == case.binding_id]
        affected = {claims[demand.claim_id].account_id}
        if (case is None or facility is None or len(bindings) != 1
                or case.claimant_id != demand.group_id
                or case.authority_id != facility.institution_id
                or case.target_id != demand.facility_asset_id
                or not demand.obligation_refs
                or not set(demand.obligation_refs) <= set(case.obligation_refs)
                or not affected <= set(bindings[0].account_refs)):
            fail('adjudication_continuity_affected_mapping')


def evaluate_pair(request, *, graph, units, mechanisms):
    request = AdjudicationContinuityRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    if mechanisms.units != units:
        fail('adjudication_continuity_policy_units')
    # Validate original inputs before restrictions, even for unresolved cases.
    # Keep this evidence distinct from the candidate and never reuse allocations.
    preflight = evaluate_continuity(request.continuity, graph=graph, units=units)
    adjudication = evaluate_adjudication(request.adjudication, graph=graph, units=units,
        mechanisms=mechanisms)
    continuity = None
    if adjudication.status == 'resolved':
        data = request.continuity.model_dump()
        outcomes = {r.case_id: r.outcome for r in adjudication.results}
        blocked = {p.claim_id for p in request.prerequisites
                   if p.case_id is not None and outcomes[p.case_id] != 'upheld'}
        if blocked:
            for demand in data['demands']:
                # Restrict only dependent new access; never change voluntary
                # participation, eligibility, obligations or unknown declarations.
                if demand['claim_id'] in blocked and demand['access'] != 'unknown':
                    demand['access'] = 'denied'
        continuity = evaluate_continuity(ContinuityRequest.model_validate(data),
            graph=graph, units=units)
    resolved = (continuity is not None and continuity.status == 'resolved'
                and preflight.status == 'resolved')
    candidate = None
    if resolved:
        candidate = AdjudicationContinuityCandidate(
            administration=adjudication.administration.evaluation.batch.model_dump(),
            continuity=continuity.allocation.batch.model_dump())
    return AdjudicationContinuityEvaluation(contract_version=1,
        adapter_version='adjudication-continuity-v1', evidence_status='hypothetical',
        baseline_digest=binding(request, graph, units, mechanisms),
        status='resolved' if resolved else 'unresolved', request=request,
        adjudication=adjudication, preflight=preflight, continuity=continuity,
        candidate=candidate)
