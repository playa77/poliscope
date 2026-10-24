"""Private explicit legal health prerequisites; no rights or treatment inference."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .packs import Digest
from .accounts import AccountBatch
from .law_conflict import AdjudicationRequest, AdjudicationEvaluation
from .health import HealthRequest, HealthEvaluation


class HealthLegalPrerequisite(Contract):
    service_id: Identifier
    case_id: Identifier | None


class AdjudicationHealthRequest(Contract):
    contract_version: Literal[1]
    adjudication: AdjudicationRequest
    health: HealthRequest
    prerequisites: Annotated[list[HealthLegalPrerequisite], Field(min_length=1, max_length=100)]


class AdjudicationHealthEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['adjudication-health-v1']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    status: Literal['resolved', 'unresolved']
    request: AdjudicationHealthRequest
    adjudication: AdjudicationEvaluation
    preflight: HealthEvaluation
    health: HealthEvaluation | None
    batch: AccountBatch | None
