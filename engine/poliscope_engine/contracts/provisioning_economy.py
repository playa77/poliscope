"""Host-only DOM-01/02 integration; no public execution or write grant."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .economy import EconomyRequest, EconomyEvaluation, EconomyActivity
from .provisioning import ProvisioningRequest, ProvisioningEvaluation
from .accounts import AccountBatch
from .evaluation import Digest


class UseTerms(Contract):
    phase_id: Identifier
    activities: Annotated[list[EconomyActivity], Field(min_length=1, max_length=1000)]


class ProvisioningEconomyRequest(Contract):
    contract_version: Literal[1]
    work: EconomyRequest
    # Initial books must match exactly. Only the work result supplies the chain.
    chain: ProvisioningRequest
    # Use phases start with no choices; validated economy terms supply them.
    use_terms: Annotated[list[UseTerms], Field(min_length=1, max_length=32)]


class ProvisioningEconomyEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['provisioning-economy-v1']
    baseline_digest: Digest
    evidence_status: Literal['hypothetical']
    status: Literal['resolved', 'unresolved']
    request: ProvisioningEconomyRequest
    work: EconomyEvaluation
    provisioning: ProvisioningEvaluation | None
    batch: AccountBatch | None
