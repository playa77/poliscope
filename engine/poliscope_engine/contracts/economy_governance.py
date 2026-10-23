"""Private single-decision prerequisite for actual canonical economy claims."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .packs import Digest
from .accounts import AccountBatch
from .economy import EconomyRequest, EconomyEvaluation
from .governance import GovernanceRequest, GovernanceEvaluation


class EconomyGovernanceRequest(Contract):
    contract_version: Literal[1]
    governance: GovernanceRequest
    economy: EconomyRequest
    economic_claim_ids: Annotated[list[Identifier], Field(min_length=1, max_length=1000)]
    governed_claim_ids: Annotated[list[Identifier], Field(min_length=1, max_length=1000)]


class EconomyGovernanceEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['economy-governance-v1']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    status: Literal['resolved', 'unresolved']
    request: EconomyGovernanceRequest
    governance: GovernanceEvaluation
    economy: EconomyEvaluation | None
    batch: AccountBatch | None
