"""Explicit data-only uncertainty and registered feasibility methods, version 1."""
from typing import Annotated, Literal
from pydantic import Field, TypeAdapter
from .base import Contract, Identifier
from .world import DecimalString, References, RevisionContext, EffectiveTime, QuantityValue
from .evaluation import Digest
from .measurements import MeasurementReport

Rows = Field(max_length=100)
Text = Annotated[str, Field(min_length=1, max_length=4096)]
Integer = Annotated[str, Field(pattern=r'^-?(0|[1-9][0-9]*)$', max_length=256)]
Positive = Annotated[str, Field(pattern=r'^[1-9][0-9]*$', max_length=256)]


class ExactRatio(Contract):
    numerator: Integer
    denominator: Positive


class MethodAssumption(Contract):
    id: Identifier
    version: Identifier
    rationale: Text


class Parameter(Contract):
    id: Identifier
    version: Identifier
    value_id: Identifier
    form: Literal['point', 'bounded_range', 'distribution', 'qualitative']
    point: DecimalString | None
    low: DecimalString | None
    high: DecimalString | None
    interpretation: Text
    source_refs: References
    assumption_refs: Annotated[list[Identifier], Field(min_length=1, max_length=100)]


class AffineTerm(Contract):
    variable_id: Identifier
    coefficient: DecimalString


class AffineExpression(Contract):
    id: Identifier
    version: Identifier
    # Coefficients are dimensionless. All variables/constants share output units.
    constant: DecimalString
    terms: Annotated[list[AffineTerm], Field(max_length=100)]
    threshold: DecimalString | None
    operation: Literal['lt', 'le', 'eq', 'ne', 'ge', 'gt']
    interpretation: Text


class JointOutcome(Contract):
    values: Annotated[dict[Identifier, DecimalString], Field(min_length=1, max_length=100)]
    probability: ExactRatio


class ConditionalRow(Contract):
    given: Annotated[dict[Identifier, DecimalString], Field(max_length=100)]
    outcomes: Annotated[list[JointOutcome], Field(min_length=1, max_length=100)]


class ProbabilityFactor(Contract):
    id: Identifier
    version: Identifier
    variables: Annotated[list[Identifier], Field(min_length=1, max_length=100)]
    parents: References
    rows: Annotated[list[ConditionalRow], Field(min_length=1, max_length=100)]
    interpretation: Text
    assumption_refs: Annotated[list[Identifier], Field(min_length=1, max_length=100)]


class UncertaintyModel(Contract):
    id: Identifier
    version: Identifier
    method: Literal['affine-box-v1', 'finite-factorization-v1', 'unsupported']
    dependence: Literal['declared_box', 'declared_factorization', 'unresolved']
    parameters: Annotated[list[Parameter], Field(min_length=1, max_length=100)]
    expressions: Annotated[list[AffineExpression], Field(min_length=1, max_length=100)]
    factors: Annotated[list[ProbabilityFactor], Field(max_length=100)]
    assumption_refs: Annotated[list[Identifier], Field(min_length=1, max_length=100)]
    assumptions: Annotated[list[MethodAssumption], Field(min_length=1, max_length=100)]
    state_limit: Annotated[int, Field(ge=1, le=10000)]


class UncertaintyQuery(Contract):
    context: RevisionContext
    model: UncertaintyModel


class UncertainObservation(Contract):
    expression_id: Identifier
    status: Literal['known', 'unmodeled', 'solver_failure']
    reason: Text
    low: DecimalString | None
    high: DecimalString | None
    probability: ExactRatio | None
    diagnostic: Literal['always', 'never', 'overlap', 'unavailable', 'not_selected']
    unit_id: Identifier | None
    scope_id: Identifier | None
    time_basis_id: Identifier | None
    denominator_scope_id: Identifier | None


class UncertaintyReport(Contract):
    query: UncertaintyQuery
    effective_time: EffectiveTime
    input_digest: Digest
    method: Identifier
    observations: Annotated[list[UncertainObservation], Rows]
    assumptions: References
    sources: References
    report_digest: Digest


class VariantValue(Contract):
    variable_id: Identifier
    value: DecimalString
    # An explicit player/model decision; a range never selects this itself.
    selection_ref: Identifier


class SensitivityVariant(Contract):
    id: Identifier
    values: Annotated[list[VariantValue], Field(min_length=1, max_length=100)]


class SensitivityQuery(Contract):
    context: RevisionContext
    model: UncertaintyModel
    variants: Annotated[list[SensitivityVariant], Field(min_length=1, max_length=20)]


class SensitivityResult(Contract):
    id: Identifier
    selected: SensitivityVariant
    physical_digest: Digest
    report: MeasurementReport


class SensitivityReport(Contract):
    query: SensitivityQuery
    baseline: MeasurementReport
    variants: Annotated[list[SensitivityResult], Field(max_length=20)]
    assumptions: References
    sources: References
    report_digest: Digest


class CapacityConstraint(Contract):
    id: Identifier
    available_value_id: Identifier
    fixed_demand: DecimalString
    demand_per_unit: DecimalString
    resource_unit_id: Identifier
    solved_unit_id: Identifier
    interpretation: Text
    source_refs: References
    assumption_refs: Annotated[list[Identifier], Field(min_length=1, max_length=100)]


class CapacityQuery(Contract):
    context: RevisionContext
    method: Literal['linear-resource-capacity-v1']
    solved_entity_id: Identifier
    solved_unit_id: Identifier
    scope_id: Identifier
    time_basis_id: Identifier | None
    lower: DecimalString
    upper: DecimalString
    quantum: DecimalString
    iteration_limit: Annotated[int, Field(ge=1, le=1024)]
    assumptions: Annotated[list[MethodAssumption], Field(min_length=1, max_length=100)]
    constraints: Annotated[list[CapacityConstraint], Field(min_length=1, max_length=100)]


class CapacityWitness(Contract):
    constraint_id: Identifier
    available: QuantityValue
    demand_at_feasible: DecimalString | None
    demand_at_infeasible: DecimalString | None


class CapacityReport(Contract):
    query: CapacityQuery
    effective_time: EffectiveTime
    input_digest: Digest
    status: Literal['bounded', 'upper_feasible', 'infeasible', 'solver_failure', 'unmodeled']
    reason: Text
    feasible: DecimalString | None
    infeasible: DecimalString | None
    iterations: Annotated[int, Field(ge=0, le=1024)]
    stopping_rule: Literal['adjacent_quantum_grid_points']
    witnesses: Annotated[list[CapacityWitness], Rows]
    assumptions: References
    sources: References
    report_digest: Digest


uncertainty_adapter = TypeAdapter(UncertaintyQuery | UncertaintyReport | SensitivityQuery | SensitivityReport | CapacityQuery | CapacityReport)
