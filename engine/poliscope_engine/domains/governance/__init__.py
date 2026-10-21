"""Pure scoped ballots over shared authority resolution and economy accounts."""
from poliscope_engine.accounts import fail, index
from poliscope_engine.contracts.governance import GovernanceRequest, GovernanceEvaluation
from poliscope_engine.domains.economy import evaluate_economy
from poliscope_engine.numeric import parse
from poliscope_engine.policies import resolve


def evaluate_governance(request, *, graph, mechanisms, units):
    request = GovernanceRequest.model_validate_json(request.model_dump_json())
    entities = {e.id: e for e in graph.registry.entities}
    scopes = {s.id for s in graph.registry.scopes}
    authority = entities.get(request.authority_id)
    if authority is None or authority.entity_kind != 'institution' or request.scope_id not in scopes:
        fail('invalid_governance_authority')
    if not any(e.relationship_kind == 'jurisdiction' and e.from_id == request.authority_id
               and e.to_id in (request.scope_id, request.target_id) for e in graph.relationships):
        fail('missing_governance_jurisdiction')
    members = request.eligible_member_ids
    if len(set(members)) != len(members) or any(
            m not in entities or entities[m].entity_kind not in ('population_cohort', 'institution')
            for m in members):
        fail('invalid_governance_electorate')
    if request.quorum > len(members):
        fail('invalid_governance_quorum')
    voters = [b.member_id for b in request.ballots]
    if len(set(voters)) != len(voters) or not set(voters) <= set(members):
        fail('invalid_governance_ballots')
    proposals = [b for b in request.bindings if b.id == request.proposal_binding_id]
    if (len(proposals) != 1 or proposals[0].authority_id != request.authority_id
            or proposals[0].scope_id != request.scope_id
            or proposals[0].parameter_id != request.parameter_id):
        fail('invalid_governance_proposal')
    policies = resolve(request.bindings, graph=graph, mechanisms=mechanisms, rules=request.rules)
    results = [r for r in policies.results if r.entity_id == request.target_id
               and r.parameter_id == request.parameter_id]
    findings = []
    if len(results) != 1 or request.proposal_binding_id not in results[0].participant_ids:
        fail('missing_governance_target')
    policy = results[0]
    if policy.status != 'known':
        findings.append('institutional_conflict' if policy.status == 'conflict' else 'missing_policy_input')
    elif (policy.rule is not None and (policy.rule.operation != 'select'
            or policy.rule.selected_id != request.proposal_binding_id)):
        findings.append('proposal_not_selected')
    admin = request.administration
    claims = index(admin.batch.claims)
    activities = {a.claim_id: a for a in admin.activities}
    selected = request.administrative_claim_ids
    accounts = index(admin.batch.accounts)
    if len(set(selected)) != len(selected) or not set(selected) <= claims.keys():
        fail('invalid_governance_claims')
    for cid in selected:
        claim = claims[cid]
        account = accounts.get(claim.account_id)
        if (cid not in activities or activities[cid].kind != 'participation'
                or account is None or account.scope_id != request.scope_id
                or claim.claimant_id not in entities
                or entities[claim.claimant_id].entity_kind != 'population_cohort'
                or parse(claim.requested) <= 0):
            fail('invalid_governance_administration')
    administration = evaluate_economy(admin, units)
    if administration.status != 'resolved':
        findings.append('unknown_administration')
    if request.approval is None:
        findings.append('missing_approval_rule')
    if any(b.vote == 'unknown' for b in request.ballots):
        findings.append('unknown_ballot')
    outcome = None
    if not findings:
        actuals = {a.claim_id: a for a in administration.allocation.actuals}
        # Include prior fulfillment: a retained completed claim is not spent twice.
        if any(parse(actuals[c].unmet) > 0 for c in selected):
            outcome = 'capacity_blocked'
        elif len(request.ballots) < request.quorum:
            outcome = 'no_quorum'
        else:
            yes = sum(b.vote == 'yes' for b in request.ballots)
            approved = (yes * 2 > len(request.ballots) if request.approval == 'strict_majority'
                        else yes == len(request.ballots))
            outcome = 'approved' if approved else 'rejected'
    return GovernanceEvaluation(contract_version=1, status='unresolved' if findings else 'resolved',
        outcome=outcome, findings=findings, request=request, policies=policies,
        administration=administration, evidence_status='hypothetical')
