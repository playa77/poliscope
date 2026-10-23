"""Private legal prerequisites; no rights creation or durable enforcement."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .packs import Digest
from .accounts import AccountBatch
from .economy import EconomyRequest, EconomyEvaluation
from .law_conflict import AdjudicationRequest, AdjudicationEvaluation


class LegalPrerequisite(Contract):
    claim_id: Identifier
    case_id: Identifier
    entitlement_account_id: Identifier


class EconomyAdjudicationRequest(Contract):
    contract_version: Literal[1]
    adjudication: AdjudicationRequest
    economy: EconomyRequest
    economic_claim_ids: Annotated[list[Identifier], Field(min_length=1, max_length=1000)]
    prerequisites: Annotated[list[LegalPrerequisite], Field(min_length=1, max_length=1000)]


class EconomyAdjudicationEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['economy-adjudication-v1']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    status: Literal['resolved', 'unresolved']
    request: EconomyAdjudicationRequest
    adjudication: AdjudicationEvaluation
    economy: EconomyEvaluation | None
    batch: AccountBatch | None
