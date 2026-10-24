"""Private explicit legal participation prerequisites; no rights or attendance inference."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .packs import Digest
from .accounts import AccountBatch
from .law_conflict import AdjudicationRequest, AdjudicationEvaluation
from .meaning_identity import ParticipationRequest, ParticipationEvaluation


class ParticipationLegalPrerequisite(Contract):
    claim_id: Identifier
    case_id: Identifier | None


class AdjudicationParticipationRequest(Contract):
    contract_version: Literal[1]
    adjudication: AdjudicationRequest
    participation: ParticipationRequest
    prerequisites: Annotated[list[ParticipationLegalPrerequisite], Field(min_length=1, max_length=1000)]


class AdjudicationParticipationCandidate(Contract):
    administration: AccountBatch
    participation: AccountBatch


class AdjudicationParticipationEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['adjudication-participation-v1']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    status: Literal['resolved', 'unresolved']
    request: AdjudicationParticipationRequest
    adjudication: AdjudicationEvaluation
    # Original-term preflight remains inspectable when a case is unresolved.
    # Its independent preview allocations are never staged or published.
    preflight: ParticipationEvaluation
    participation: ParticipationEvaluation | None
    candidate: AdjudicationParticipationCandidate | None
