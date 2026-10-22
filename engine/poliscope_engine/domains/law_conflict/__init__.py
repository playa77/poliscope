"""Pure hypothetical adjudication over shared authority and dated time accounts."""
from poliscope_engine.accounts import fail, index
from poliscope_engine.contracts.law_conflict import (
    AdjudicationRequest, AdjudicationEvaluation, CaseResult,
)
from poliscope_engine.domains.economy.exploration import report
from poliscope_engine.numeric import parse
from poliscope_engine.policies import resolve


def evaluate_adjudication(request, *, graph, mechanisms, units):
    request = AdjudicationRequest.model_validate_json(request.model_dump_json())
    entities = {e.id: e for e in graph.registry.entities}
    scopes = {s.id: s for s in graph.registry.scopes}
    if (request.scope_id not in scopes
            or scopes[request.scope_id].scope_kind not in ('settlement', 'region')):
        fail('invalid_adjudication_scope')
    if len({c.id for c in request.cases}) != len(request.cases):
        fail('duplicate_legal_case')
    claims = index(request.administration.batch.claims)
    accounts = index(request.administration.batch.accounts)
    activities = {a.claim_id: a for a in request.administration.activities}
    work_ids = set()
    for case in request.cases:
        claimant, authority = entities.get(case.claimant_id), entities.get(case.authority_id)
        if claimant is None or claimant.entity_kind != 'population_cohort':
            fail('invalid_legal_claimant')
        if authority is None or authority.entity_kind != 'institution':
            fail('invalid_adjudication_authority')
        if not any(e.relationship_kind == 'jurisdiction' and e.from_id == case.authority_id
                   and e.to_id in (request.scope_id, case.target_id) for e in graph.relationships):
            fail('missing_adjudication_jurisdiction')
        bindings = [b for b in request.bindings if b.id == case.binding_id]
        if (len(bindings) != 1 or bindings[0].authority_id != case.authority_id
                or bindings[0].scope_id != request.scope_id
                or bindings[0].parameter_id != case.parameter_id):
            fail('invalid_adjudication_binding')
        for cid in case.work_claim_ids:
            if cid in work_ids:
                fail('duplicate_case_work')
            work_ids.add(cid)
            claim, activity = claims.get(cid), activities.get(cid)
            account = accounts.get(claim.account_id) if claim is not None else None
            worker = entities.get(claim.claimant_id) if claim is not None else None
            if (claim is None or activity is None or activity.kind != 'participation'
                    or account is None or account.scope_id != request.scope_id
                    or worker is None or worker.entity_kind != 'population_cohort'
                    or parse(claim.requested) <= 0):
                fail('invalid_case_work')
    policies = resolve(request.bindings, graph=graph, mechanisms=mechanisms, rules=request.rules)
    administration = report(request.administration, units)
    indicators = {i.claim_id: i for i in administration.indicators}
    results = []
    for case in request.cases:
        matching = [r for r in policies.results if r.entity_id == case.target_id
                    and r.parameter_id == case.parameter_id]
        if len(matching) != 1 or case.binding_id not in matching[0].participant_ids:
            fail('missing_adjudication_target')
        policy = matching[0]
        findings = []
        if policy.status != 'known':
            findings.append('institutional_conflict' if policy.status == 'conflict' else 'missing_policy_input')
        elif policy.rule is not None and (policy.rule.operation != 'select'
                or policy.rule.selected_id != case.binding_id):
            findings.append('adjudication_binding_not_selected')
        if case.eligibility == 'unknown':
            findings.append('unknown_legal_eligibility')
        if case.incompatible_right_refs:
            findings.append('incompatible_rights')
        if case.disposition is None or case.rationale is None:
            findings.append('missing_disposition')
        if administration.status != 'resolved':
            findings.append('unknown_case_capacity')
        outcome = None
        if not findings:
            if case.eligibility == 'ineligible':
                outcome = 'ineligible'
            elif any(parse(indicators[c].unmet) > 0 for c in case.work_claim_ids):
                outcome = 'capacity_blocked'
            else:
                outcome = case.disposition
        results.append(CaseResult(case_id=case.id, status='unresolved' if findings else 'resolved',
            outcome=outcome, findings=findings, proposed_obligation_refs=case.obligation_refs))
    return AdjudicationEvaluation(contract_version=1,
        status='unresolved' if any(r.status == 'unresolved' for r in results) else 'resolved',
        evidence_status='hypothetical', request=request, results=results,
        policies=policies, administration=administration)
