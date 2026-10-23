"""Canonical care obligations and provisioning share one dated work allocation."""
from poliscope_engine.accounts import fail
from poliscope_engine.contracts.provisioning_care import (
    ProvisioningCareRequest, ProvisioningCareEvaluation,
)
from poliscope_engine.domains.social_organization import evaluate_care
from .economy import evaluate_pair as evaluate_economy_pair, validate_context as validate_economy_context
from .context import binding as context_binding

MODEL = ('authored:provisioning-care', 'v1')


def binding(request, graph, units):
    return context_binding(request, graph, units, adapter='provisioning-care-v1', model=MODEL)


def validate_context(request, graph, units):
    if request.care.work != request.provisioning.work:
        fail('care_counterpart_work_mismatch')
    validate_economy_context(request.provisioning, graph, units)


def evaluate_pair(request, *, graph, units):
    request = ProvisioningCareRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    care = evaluate_care(request.care, graph=graph, units=units)
    provisioning = None
    if care.status == 'resolved':
        # Both pure services recompute the identical shared allocation. It is
        # never applied twice: provisioning starts from the original book.
        provisioning = evaluate_economy_pair(request.provisioning, graph=graph, units=units)
        if provisioning.work != care.work.evaluation:
            fail('care_counterpart_staging_mismatch')
    resolved = provisioning is not None and provisioning.status == 'resolved'
    return ProvisioningCareEvaluation(contract_version=1, adapter_version='provisioning-care-v1',
        baseline_digest=binding(request, graph, units), evidence_status='hypothetical',
        status='resolved' if resolved else 'unresolved', request=request, care=care,
        provisioning=provisioning, batch=provisioning.batch if resolved else None)
