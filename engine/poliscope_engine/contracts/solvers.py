"""Host-selected numerical execution plans; no imported executable authority."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import DecimalString
from .dependencies import DependencyRequest
from .accounts import AccountBatch
from .allocations import AllocationChoice

NodeKey = Annotated[list[Identifier], Field(min_length=2, max_length=3)]


class Term(Contract):
    node: NodeKey
    coefficient: DecimalString


class Equation(Contract):
    node: NodeKey
    constant: DecimalString
    terms: Annotated[list[Term], Field(max_length=100)]


class StartingValue(Contract):
    node: NodeKey
    value: DecimalString


class SolverPlan(Contract):
    id: Identifier
    kind: Literal['linear', 'iterative']
    nodes: Annotated[list[NodeKey], Field(min_length=1, max_length=100)]
    equations: Annotated[list[Equation], Field(max_length=100)]
    starting_state: Annotated[list[StartingValue], Field(max_length=100)]
    update_order: Annotated[list[NodeKey], Field(max_length=100)]
    update_mode: Literal['simultaneous', 'sequential']
    criterion: Literal['absolute_residual']
    tolerance: DecimalString
    iteration_limit: Annotated[int, Field(ge=1, le=10000)]


class RuntimeClaim(Contract):
    instance_id: Identifier
    claim_id: Identifier
    account_claim_id: Identifier


class FinitePlan(Contract):
    id: Identifier
    procedure: Literal['priority', 'all_or_nothing'] | None
    claim_order: Annotated[list[Identifier], Field(max_length=1000)]
    choices: Annotated[list[AllocationChoice], Field(max_length=1000)]
    mechanism_ref: Identifier


class ExecutionRequest(Contract):
    contract_version: Literal[1]
    dependencies: DependencyRequest
    batch: AccountBatch | None
    claims: Annotated[list[RuntimeClaim], Field(max_length=1000)]
    allocations: Annotated[list[FinitePlan], Field(max_length=1000)]
    solvers: Annotated[list[SolverPlan], Field(max_length=100)]
    operation_limit: Annotated[int, Field(ge=1, le=1000000)]
