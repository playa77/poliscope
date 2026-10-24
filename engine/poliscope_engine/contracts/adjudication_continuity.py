"""Private explicit legal continuity prerequisites; no rights or safety inference."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .packs import Digest
from .accounts import AccountBatch
from .law_conflict import AdjudicationRequest, AdjudicationEvaluation
from .security_risk import ContinuityRequest, ContinuityEvaluation


class ContinuityLegalPrerequisite(Contract):
    claim_id: Identifier
    case_id: Identifier | None


class AdjudicationContinuityRequest(Contract):
    contract_version: Literal[1]
    adjudication: AdjudicationRequest
    continuity: ContinuityRequest
    prerequisites: Annotated[list[ContinuityLegalPrerequisite], Field(min_length=1, max_length=1000)]


class AdjudicationContinuityCandidate(Contract):
    administration: AccountBatch
    continuity: AccountBatch


class AdjudicationContinuityEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['adjudication-continuity-v1']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    status: Literal['resolved', 'unresolved']
    request: AdjudicationContinuityRequest
    adjudication: AdjudicationEvaluation
    # Original-term preflight remains inspectable when a case is unresolved.
    # Its independent preview allocations are never staged or published.
    preflight: ContinuityEvaluation
    continuity: ContinuityEvaluation | None
    candidate: AdjudicationContinuityCandidate | None
