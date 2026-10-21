"""Pure economy exploration; canonical accounts remain the only quantity authority."""
from poliscope_engine.accounts import AccountBook, fail, index
from poliscope_engine.contracts.economy import (
    EconomyRequest, EconomyAlternative, EconomyInterview, EconomyEdit,
    EconomyBudgetIndicator, EconomyClaimIndicator, EconomyReport, EconomyPreview,
)
from poliscope_engine.evaluation import EVALUATOR_ID
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.interviews import definition
from poliscope_engine.numeric import RUNTIME_ID
from . import evaluate_economy

VERSION = 'economy-exploration-v1'
MODEL = 'authored:economy-access-work-v1'
LIMITS = ('Hypothetical finite access and time assignment only. Declared holders and terms '
          'are host inputs, not validated property law. Paid work creates no wages. '
          'No option or claim order is selected by default. Shared supply is not a '
          'per-claim promise. No prices, employment, skills or behavioral effects are '
          'inferred. Preview does not publish accepted history or settle transactions.')


def detached(request):
    return EconomyRequest.model_validate_json(request.model_dump_json())


def baseline(request, units):
    return digest(dict(version=VERSION, runtime=RUNTIME_ID, evaluator=EVALUATOR_ID,
                       request=request, units=units))


def scoped_claims(request, scope_id):
    accounts = index(request.batch.accounts)
    scopes = {accounts[c.account_id].scope_id for c in request.batch.claims}
    # Procedure/order belongs to the whole allocator invocation. A local edit
    # must never silently reorder another scope's competing claims.
    if scopes != {scope_id}:
        fail('incompatible_economy_scope')
    return [c.id for c in request.batch.claims]


def interview(request, units, scope_id):
    request = detached(request)
    evaluate_economy(request, units)
    claims = scoped_claims(request, scope_id)
    qid = 'authored:economy/procedure'
    question = definition(qid, 'question', None,
        'How should this scope assign finite goods access and shared work time under the declared holders and terms?')
    alternatives = [EconomyAlternative(procedure=procedure,
        definition=definition(qid + '/' + procedure, 'option', qid, text).model_copy(update={
            'modeling': 'procedural', 'mechanism_refs': [MODEL]}))
        for procedure, text in (
            ('priority', 'Serve claims in the supplied order, allowing partial fulfillment. '
             'Earlier goods or work claims can exhaust shared stock, rights, funding or time.'),
            ('all_or_nothing', 'Serve a claim only when its complete remaining amount fits, '
             'in the supplied order. A later smaller claim can be served after a larger claim is skipped.'))]
    return EconomyInterview(baseline_digest=baseline(request, units), scope_id=scope_id,
        question=question, alternatives=alternatives, claim_ids=claims,
        selected_option_id=None, limits=LIMITS)


def report(request, units):
    request = detached(request)
    evaluation = evaluate_economy(request, units)
    accounts = index(request.batch.accounts)
    before = AccountBook(request.batch, units).evaluate()
    opening = {a.account_id: a for a in before.accounts}
    prior = {c.claim_id: c for c in before.claims}
    after = {a.account_id: a for a in evaluation.allocation.accounts.accounts}
    actuals = {c.claim_id: c for c in evaluation.allocation.actuals}
    activities = {a.claim_id: a for a in request.activities}
    holders = {h.account_id: h for h in request.holders}
    resolved = evaluation.status == 'resolved'
    indicators = []
    for claim in request.batch.claims:
        activity = activities[claim.id]
        account = accounts[claim.account_id]
        requirements = [(t.account_id, t.per_unit) for t in activity.requirements]
        if activity.kind != 'goods':
            requirements.insert(0, (account.id, '1'))
        budgets = [EconomyBudgetIndicator(account_id=aid,
            holder_id=holders[aid].holder_id, role=holders[aid].role, per_unit=rate,
            scope_id=accounts[aid].scope_id, period_id=accounts[aid].period_id,
            unit_id=accounts[aid].unit_id, available_before=opening[aid].available,
            available_after=after[aid].available if resolved else None)
            for aid, rate in requirements]
        indicators.append(EconomyClaimIndicator(claim_id=claim.id,
            claimant_id=claim.claimant_id, kind=activity.kind, account_id=account.id,
            scope_id=account.scope_id, period_id=account.period_id, unit_id=account.unit_id,
            requested=claim.requested, actual_before=prior[claim.id].actual,
            actual=actuals[claim.id].allocated if resolved else None,
            unmet=actuals[claim.id].unmet if resolved else None,
            available_before=opening[account.id].available,
            eligibility=activity.eligibility, access_limit=activity.access_limit,
            terms_known=activity.terms_known, budgets=budgets,
            posting_ids=[p.id for p in evaluation.allocation.batch.postings if p.claim_id == claim.id],
            source_refs=list(dict.fromkeys([*claim.source_refs, *activity.source_refs, *request.source_refs]))))
    return EconomyReport(contract_version=1, adapter_version=VERSION,
        coverage_status='partial', evidence_status='hypothetical',
        baseline_digest=baseline(request, units), status=evaluation.status,
        indicators=indicators, evaluation=evaluation)


def preview(request, units, edit):
    request = detached(request)
    edit = EconomyEdit.model_validate_json(edit.model_dump_json())
    if edit.baseline_digest != baseline(request, units):
        fail('stale_economy_preview')
    card = interview(request, units, edit.scope_id)
    option = next((o for o in card.alternatives if o.definition.id == edit.option_id), None)
    if option is None:
        fail('unknown_economy_option')
    if len(edit.claim_order) != len(set(edit.claim_order)) or set(edit.claim_order) != set(card.claim_ids):
        fail('invalid_claim_order')
    candidate = request.model_copy(update=dict(procedure=option.procedure, claim_order=list(edit.claim_order)))
    result = report(candidate, units)
    return EconomyPreview(contract_version=1, edit=edit,
        candidate_digest=result.baseline_digest, report=result)
