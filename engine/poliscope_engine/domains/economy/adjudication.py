"""Actual legal prerequisites restrict economy over one staged finite book."""
from poliscope_engine.accounts import AccountBook, fail, index, quantity
from poliscope_engine.contracts.economy_adjudication import (
    EconomyAdjudicationRequest, EconomyAdjudicationEvaluation,
)
from poliscope_engine.contracts.economy import EconomyRequest
from poliscope_engine.domains.law_conflict import evaluate_adjudication
from . import evaluate_economy
from ..provisioning.context import binding as context_binding, digest, policy_evidence

MODEL = ('authored:economy-adjudication', 'v1')


def binding(request, graph, units, mechanisms):
    return digest(dict(context=context_binding(request, graph, units,
        adapter='economy-adjudication-v1', model=MODEL), policy=policy_evidence(mechanisms)))


def closed(activity):
    return (activity.eligibility == 'denied' and quantity(activity.access_limit) == 0
            and activity.terms_known and not activity.requirements)


def validate_context(request, graph, units):
    admin, economy = request.adjudication.administration, request.economy
    if admin.batch != economy.batch or admin.holders != economy.holders:
        fail('adjudication_counterpart_book_mismatch')
    if admin.period_id != economy.period_id:
        fail('adjudication_counterpart_period_mismatch')
    book = AccountBook(admin.batch, units)
    claims = index(book.batch.claims)
    economic = set(request.economic_claim_ids)
    cases = {c.id: c for c in request.adjudication.cases}
    work = {cid for c in cases.values() for cid in c.work_claim_ids}
    mapped = [p.claim_id for p in request.prerequisites]
    if (len(cases) != len(request.adjudication.cases)
            or len(economic) != len(request.economic_claim_ids)
            or len(set(mapped)) != len(mapped) or not set(mapped) <= economic
            or not economic <= claims.keys() or economic & work):
        fail('invalid_adjudication_counterpart_claims')
    entities = {e.id: e.entity_kind for e in graph.registry.entities}
    scopes = {s.id for s in graph.registry.scopes}
    for account in book.batch.accounts:
        if entities.get(account.id) != 'account' or account.scope_id not in scopes:
            fail('adjudication_counterpart_account_identity')
        if account.period_id is not None and account.period_id != economy.period_id:
            fail('adjudication_counterpart_period_mismatch')
    if any(entities.get(c.claimant_id) not in ('population_cohort', 'institution')
           for c in claims.values()):
        fail('adjudication_counterpart_claimant_identity')
    if any(entities.get(h.holder_id) != 'population_cohort' for h in economy.holders):
        fail('adjudication_counterpart_holder_identity')
    time_ids = {a.id for a in book.batch.accounts
                if units.unit(a.unit_id).dimension == (('time', 1),)}
    if time_ids != {h.account_id for h in economy.holders if h.role == 'time'}:
        fail('adjudication_counterpart_time_holders')
    accounts = index(book.batch.accounts)
    activities = {a.claim_id: a for a in economy.activities}
    for prerequisite in request.prerequisites:
        case = cases.get(prerequisite.case_id)
        claim = claims[prerequisite.claim_id]
        activity = activities.get(claim.id)
        entitlement = accounts.get(prerequisite.entitlement_account_id)
        bindings = [b for b in request.adjudication.bindings
                    if case is not None and b.id == case.binding_id]
        if (case is None or case.claimant_id != claim.claimant_id
                or len(bindings) != 1 or activity is None or activity.kind != 'goods'
                or entitlement is None or entitlement.scope_id != request.adjudication.scope_id
                or accounts[claim.account_id].scope_id != request.adjudication.scope_id
                or not {claim.account_id, entitlement.id} <= set(bindings[0].account_refs)
                or not any(t.kind == 'entitlement' and t.account_id == entitlement.id
                           and quantity(t.per_unit) > 0 for t in activity.requirements)):
            fail('adjudication_counterpart_right_mapping')
    for phase, closed_ids in ((admin, economic), (economy, set(claims) - economic)):
        activities = {a.claim_id: a for a in phase.activities}
        if len(activities) != len(phase.activities) or set(activities) != set(claims):
            fail('invalid_economy_activities')
        if any(not closed(activities[c]) for c in closed_ids):
            fail('adjudication_counterpart_open_phase_claim')
        # Detached preflight validates the declared terms; its allocations are
        # discarded. The candidate uses only the actual staged administration book.
        from poliscope_engine.domains.economy import compile_choices
        compile_choices(phase, units)


def evaluate_pair(request, *, graph, units, mechanisms):
    request = EconomyAdjudicationRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    if mechanisms.units != units:
        fail('adjudication_counterpart_policy_units')
    adjudication = evaluate_adjudication(request.adjudication, graph=graph,
        mechanisms=mechanisms, units=units)
    economy = None
    if adjudication.status == 'resolved':
        data = request.economy.model_dump()
        data['batch'] = adjudication.administration.evaluation.batch.model_dump()
        outcomes = {r.case_id: r.outcome for r in adjudication.results}
        blocked = {p.claim_id for p in request.prerequisites if outcomes[p.case_id] != 'upheld'}
        for activity in data['activities']:
            if activity['claim_id'] in blocked and activity['eligibility'] != 'unknown':
                activity['eligibility'] = 'denied'
        economy = evaluate_economy(EconomyRequest.model_validate(data), units)
    resolved = economy is not None and economy.status == 'resolved'
    return EconomyAdjudicationEvaluation(contract_version=1,
        adapter_version='economy-adjudication-v1', evidence_status='hypothetical',
        baseline_digest=binding(request, graph, units, mechanisms),
        status='resolved' if resolved else 'unresolved', request=request,
        adjudication=adjudication, economy=economy, batch=economy.batch if resolved else None)
