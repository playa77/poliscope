"""Pure prerequisite inspection over shared time, goods, facilities and authority."""
from poliscope_engine.accounts import fail, index
from poliscope_engine.allocations import allocate
from poliscope_engine.contracts.knowledge_culture import EducationRequest, EducationEvaluation, EducationResult
from poliscope_engine.domains.economy.exploration import report
from poliscope_engine.numeric import parse
from poliscope_engine.policies import resolve


def evaluate_education(request, *, graph, mechanisms, units):
    request = EducationRequest.model_validate_json(request.model_dump_json())
    entities = {e.id: e for e in graph.registry.entities}
    scopes = {s.id: s for s in graph.registry.scopes}
    if request.scope_id not in scopes or scopes[request.scope_id].scope_kind not in ('settlement', 'region'):
        fail('invalid_education_scope')
    index(request.services)
    work, facility = request.work, request.facility_allocation
    # A resource may belong to only one pool, and every claim retains its identity.
    def ids(batch):
        return {x.id for group in (batch.accounts, batch.claims) for x in group}
    if ids(work.batch) & ids(facility.batch):
        fail('overlapping_education_pools')
    accounts, claims = index(work.batch.accounts), index(work.batch.claims)
    activities = {a.claim_id: a for a in work.activities}
    f_accounts, f_claims = index(facility.batch.accounts), index(facility.batch.claims)
    assets, mapped = set(), set()
    for item in request.facilities:
        asset, account = entities.get(item.asset_id), f_accounts.get(item.account_id)
        if item.asset_id in assets or item.account_id in mapped:
            fail('duplicate_education_facility')
        assets.add(item.asset_id); mapped.add(item.account_id)
        if (asset is None or asset.entity_kind != 'asset' or account is None
                or account.kind != 'capacity' or account.invariant != 'budget'
                or units.unit(account.unit_id).dimension != (('facility_slot', 1),)):
            fail('invalid_education_facility')
    if mapped != set(f_accounts):
        fail('unmapped_education_facility')
    for account in [*accounts.values(), *f_accounts.values()]:
        if account.scope_id != request.scope_id or (account.period_id is not None and account.period_id != work.period_id):
            fail('incompatible_education_scope_period')
    for claim in [*claims.values(), *f_claims.values()]:
        entity = entities.get(claim.claimant_id)
        if entity is None or entity.entity_kind != 'population_cohort':
            fail('invalid_education_cohort')
    # A facility pool may only spend its own capacity, with no hidden conversion,
    # funding, time or physical resource pool competing in a second invocation.
    for choice in facility.choices:
        if choice.requirements or choice.outputs or parse(choice.loss_per_unit) != 0:
            fail('invalid_education_facility_choice')
    used = set()

    def require(cid, pool, cohort=None, kinds=None):
        if cid in used:
            fail('duplicate_education_requirement')
        used.add(cid)
        claim = pool.get(cid)
        if claim is None or parse(claim.requested) <= 0:
            fail('invalid_education_requirement')
        if cohort is not None and claim.claimant_id != cohort:
            fail('invalid_education_claimant')
        if kinds is not None and (cid not in activities or activities[cid].kind not in kinds):
            fail('invalid_education_activity')

    for service in request.services:
        authority = entities.get(service.authority_id)
        if authority is None or authority.entity_kind != 'institution' or not any(
                r.relationship_kind == 'jurisdiction' and r.from_id == service.authority_id
                and r.to_id in (request.scope_id, service.target_id) for r in graph.relationships):
            fail('invalid_education_authority')
        bindings = [b for b in request.bindings if b.id == service.binding_id]
        if (len(bindings) != 1 or bindings[0].authority_id != service.authority_id
                or bindings[0].scope_id != request.scope_id or bindings[0].parameter_id != service.parameter_id):
            fail('invalid_education_binding')
        for person in service.participants:
            require(person.claim_id, claims, person.cohort_id, ('training',))
        for person in service.staff:
            require(person.claim_id, claims, person.cohort_id, ('paid_work', 'unpaid_work'))
            if person.qualification == 'declared' and not person.qualification_refs:
                fail('missing_education_qualification_reference')
        for cid in service.supply_claim_ids:
            require(cid, claims, kinds=('goods',))
        participant_ids = {p.cohort_id for p in service.participants}
        for cid in service.facility_claim_ids:
            require(cid, f_claims)
            if f_claims[cid].claimant_id not in participant_ids:
                fail('invalid_education_facility_claimant')
    policies = resolve(request.bindings, graph=graph, mechanisms=mechanisms, rules=request.rules)
    work_report, facilities = report(work, units), allocate(facility, units)
    work_rows = {i.claim_id: i for i in work_report.indicators}
    facility_rows = {i.claim_id: i for i in facilities.actuals}
    results = []
    for service in request.services:
        matching = [p for p in policies.results if p.entity_id == service.target_id
                    and p.parameter_id == service.parameter_id]
        if len(matching) != 1 or service.binding_id not in matching[0].participant_ids:
            fail('missing_education_policy_target')
        policy, findings = matching[0], []
        if policy.status != 'known':
            findings.append('institutional_conflict' if policy.status == 'conflict' else 'missing_policy_input')
        elif policy.rule is not None and (policy.rule.operation != 'select' or policy.rule.selected_id != service.binding_id):
            findings.append('education_binding_not_selected')
        if service.eligibility == 'unknown':
            findings.append('unknown_education_eligibility')
        if any(s.qualification == 'unknown' for s in service.staff):
            findings.append('unknown_staff_qualification')
        if work_report.status != 'resolved':
            findings.append('unknown_work_capacity')
        if facilities.status != 'resolved':
            findings.append('unknown_facility_capacity')
        work_ids = [p.claim_id for p in [*service.participants, *service.staff]] + service.supply_claim_ids
        unmet = [c for c in work_ids if work_rows[c].unmet is not None and parse(work_rows[c].unmet) > 0]
        if facilities.status == 'resolved':
            unmet += [c for c in service.facility_claim_ids if parse(facility_rows[c].unmet) > 0]
        outcome = None
        if not findings:
            outcome = ('ineligible' if service.eligibility == 'denied' else
                       'unqualified' if any(s.qualification == 'not_qualified' for s in service.staff) else
                       'capacity_blocked' if unmet else 'capacity_ready')
        results.append(EducationResult(service_id=service.id, status='unresolved' if findings else 'resolved',
            outcome=outcome, findings=findings, unmet_claim_ids=unmet))
    return EducationEvaluation(contract_version=1, status='unresolved' if any(r.status == 'unresolved' for r in results) else 'resolved',
        evidence_status='hypothetical', request=request, results=results, policies=policies,
        work=work_report, facility_allocation=facilities)
