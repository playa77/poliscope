"""Actual education input commitments feed the finite provisioning chain once."""
from poliscope_engine.accounts import fail
from poliscope_engine.contracts.provisioning_education import (
    ProvisioningEducationRequest, ProvisioningEducationEvaluation,
)
from poliscope_engine.domains.knowledge_culture import evaluate_education
from .economy import evaluate_staged_chain, validate_context as validate_economy_context
from .context import binding as context_binding, digest, policy_evidence

MODEL = ('authored:provisioning-education', 'v1')


def binding(request, graph, units, mechanisms):
    # Policy resolution executes no callbacks. Bind its complete immutable registry
    # evidence as well as the request/world/units so another review or declaration
    # cannot reuse the authored context token.
    return digest(dict(context=context_binding(request, graph, units,
        adapter='provisioning-education-v1', model=MODEL),
        policy=policy_evidence(mechanisms)))


def validate_context(request, graph, units):
    local_ids = {a.id for a in request.provisioning.work.batch.accounts
                 if a.scope_id == request.education.scope_id}
    local_work = request.provisioning.work.model_copy(update={'holders': [h for h in
        request.provisioning.work.holders if h.account_id in local_ids], 'batch':
        request.provisioning.work.batch.model_copy(update={'accounts': [a for a in
            request.provisioning.work.batch.accounts if a.scope_id == request.education.scope_id]})})
    if request.education.work != local_work:
        fail('education_counterpart_work_mismatch')
    validate_economy_context(request.provisioning, graph, units, work_only=False)
    # The independent facility pool must not reappear in production/freight/use.
    facility = request.education.facility_allocation.batch
    facility_ids = {x.id for group in (facility.accounts, facility.claims) for x in group}
    chain_ids = {x.id for group in (request.provisioning.chain.batch.accounts,
        request.provisioning.chain.batch.claims) for x in group}
    chain_ids.update(c.id for p in request.provisioning.chain.phases for c in p.claims)
    if facility_ids & chain_ids:
        fail('education_counterpart_pool_collision')


def evaluate_pair(request, *, graph, units, mechanisms):
    request = ProvisioningEducationRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    if mechanisms.units != units:
        fail('education_counterpart_policy_units')
    education = evaluate_education(request.education, graph=graph, units=units, mechanisms=mechanisms)
    provisioning = None
    if education.status == 'resolved':
        # Independent input commitments survive even when a service is blocked,
        # ineligible or unqualified. They do not imply attendance or delivery.
        # Remote stocks are untouched by the local service evaluator. The exact
        # initial projection above ensures every original claim/posting/hold is
        # retained; only the new local postings are added to the whole book.
        from poliscope_engine.contracts.accounts import AccountBatch
        staged = AccountBatch.model_validate(request.provisioning.work.batch.model_dump() |
            {'postings': education.work.evaluation.batch.model_dump()['postings']})
        provisioning = evaluate_staged_chain(request.provisioning, staged, units)
    resolved = provisioning is not None and provisioning.status == 'resolved'
    return ProvisioningEducationEvaluation(contract_version=1, adapter_version='provisioning-education-v1',
        baseline_digest=binding(request, graph, units, mechanisms), evidence_status='hypothetical',
        status='resolved' if resolved else 'unresolved', request=request, education=education,
        provisioning=provisioning, batch=provisioning.batch if resolved else None)
