"""Pure host exploration; no activation, persistence, ranking or implicit choice."""
from poliscope_engine.accounts import AccountBook, fail, index
from poliscope_engine.contracts.provisioning import (
    ProvisioningRequest, ProvisioningInterview, ProcedureAlternative, ProcedureEdit,
    CapacityIndicator, ClaimIndicator, ProvisioningReport, ProvisioningPreview,
)
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.interviews import definition
from poliscope_engine.numeric import RUNTIME_ID
from .chain import evaluate_chain

VERSION = 'provisioning-exploration-v1'
LIMITS = ('Authored hypothetical finite procedures, not historical source policies or empirical '
          'models. Supply is shared, not a per-claim promise. Choose a complete order explicitly. '
          'No option is selected by default. Preview is pure; publication requires model review '
          'and the normal revision service. Multi-scope phase edits require a joint procedure.')


def detached(request):
    return ProvisioningRequest.model_validate_json(request.model_dump_json())


def baseline(request, units):
    return digest(dict(version=VERSION, runtime=RUNTIME_ID, request=request, units=units))


def scoped_phase(request, phase_id, scope_id):
    accounts = index(request.batch.accounts)
    phase = next((p for p in request.phases if p.id == phase_id), None)
    if phase is None:
        fail('unknown_provisioning_phase')
    if any(c.account_id not in accounts for c in phase.claims):
        fail('unknown_account')
    scopes = {accounts[c.account_id].scope_id for c in phase.claims}
    if len(scopes) != 1 or scopes != {scope_id}:
        fail('incompatible_provisioning_scope')
    return phase


def interview(request, units, phase_id, scope_id):
    request = detached(request)
    # Use the same calculation boundary as previews; unresolved stages stay data.
    evaluate_chain(request, units)
    phase = scoped_phase(request, phase_id, scope_id)
    qid = 'authored:provisioning/procedure'
    question = definition(qid, 'question', None,
        'How should this scoped phase handle competing finite claims?')
    texts = [
        ('priority', 'Serve claims in the supplied order, allowing exact partial fulfillment. '
         'Earlier claims can exhaust shared stock, labor or rights before later claims.'),
        ('all_or_nothing', 'Serve a claim only if its full remaining amount fits, in the supplied '
         'order. A large unmet claim can be skipped while a later smaller claim is served.'),
    ]
    alternatives = [ProcedureAlternative(procedure=procedure,
        definition=definition(qid + '/' + procedure, 'option', qid, text).model_copy(update={
            'modeling': 'procedural', 'mechanism_refs': ['authored:provisioning-chain-v1']}))
        for procedure, text in texts]
    return ProvisioningInterview(baseline_digest=baseline(request, units), scope_id=scope_id,
        phase_id=phase_id, question=question, alternatives=alternatives,
        claim_ids=[c.id for c in phase.claims], selected_option_id=None, limits=LIMITS)


def report(request, units):
    request = detached(request)
    evaluation = evaluate_chain(request, units)
    definitions = index(request.batch.accounts)
    resources = {r.account_id: r.resource_id for r in request.resources}
    stages = {p.phase_id: p.evidence for p in evaluation.phases}
    indicators = []
    for phase in request.phases:
        evidence = stages.get(phase.id)
        allocation = evidence.allocation if evidence and phase.kind == 'freight' else evidence
        before = {a.account_id: a for a in AccountBook(allocation.request.batch, units).evaluate().accounts} if allocation else {}
        after = {a.account_id: a for a in allocation.accounts.accounts} if allocation else {}
        actuals = {c.claim_id: c for c in allocation.accounts.claims} if allocation else {}
        declared = phase.routes if phase.kind == 'freight' else phase.choices
        choices = {c.claim_id: c for c in declared}
        if (len(choices) != len(declared) or len(choices) != len(phase.claims)
                or set(choices) != {c.id for c in phase.claims}):
            fail('invalid_choices')
        for claim in phase.claims:
            if claim.account_id not in definitions:
                fail('unknown_account')
            account = definitions[claim.account_id]
            if account.id not in resources:
                fail('invalid_provisioning_stock')
            choice = choices[claim.id]
            status = allocation.status if allocation else 'not_evaluated'
            requirements = [(r.account_id, r.kind, r.per_unit) for r in choice.requirements]
            if phase.kind == 'freight':
                requirements.insert(0, (choice.capacity_id, 'transport', choice.capacity_per_unit))
            if any(aid not in definitions for aid, _, _ in requirements):
                fail('unknown_account')
            constraints = [CapacityIndicator(account_id=aid, kind=kind, per_unit=rate,
                unit_id=definitions[aid].unit_id, scope_id=definitions[aid].scope_id,
                period_id=definitions[aid].period_id, available_before=before[aid].available if allocation else None,
                available_after=after[aid].available if status == 'resolved' else None)
                for aid, kind, rate in requirements]
            resolved = status == 'resolved'
            indicators.append(ClaimIndicator(phase_id=phase.id, kind=phase.kind,
                claim_id=claim.id, claimant_id=claim.claimant_id, account_id=account.id,
                resource_id=resources[account.id], scope_id=account.scope_id,
                unit_id=account.unit_id, period_id=request.period_id, status=status,
                requested=claim.requested, available_before=before[account.id].available if allocation else None,
                actual=actuals[claim.id].actual if resolved else None,
                unmet=actuals[claim.id].unmet if resolved else None,
                access=choice.access, access_limit=choice.access_limit,
                missing=allocation.missing if allocation else [], constraints=constraints,
                posting_ids=[p.id for p in evidence.batch.postings if p.claim_id == claim.id] if resolved else [],
                source_refs=list(dict.fromkeys([*claim.source_refs, *choice.source_refs, *phase.source_refs]))))
    return ProvisioningReport(contract_version=1, adapter_version=VERSION,
        coverage_status='partial', evidence_status='hypothetical', baseline_digest=baseline(request, units),
        status=evaluation.status, indicators=indicators, evaluation=evaluation)


def preview(request, units, edit):
    request = detached(request)
    edit = ProcedureEdit.model_validate_json(edit.model_dump_json())
    if edit.baseline_digest != baseline(request, units):
        fail('stale_provisioning_preview')
    card = interview(request, units, edit.phase_id, edit.scope_id)
    option = next((o for o in card.alternatives if o.definition.id == edit.option_id), None)
    if option is None:
        fail('unknown_provisioning_option')
    phase = scoped_phase(request, edit.phase_id, edit.scope_id)
    if len(edit.claim_order) != len(set(edit.claim_order)) or set(edit.claim_order) != set(card.claim_ids):
        fail('invalid_claim_order')
    selected = phase.model_copy(update=dict(procedure=option.procedure, claim_order=list(edit.claim_order)))
    candidate = request.model_copy(update=dict(phases=[selected if p.id == phase.id else p for p in request.phases]))
    result = report(candidate, units)
    return ProvisioningPreview(contract_version=1, edit=edit,
        candidate_digest=result.baseline_digest, report=result)
