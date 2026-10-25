"""Read-only revision-pinned uncertainty reports and explicit variant previews."""
from fractions import Fraction
from poliscope_engine.contracts.uncertainty import (
    UncertaintyQuery, UncertaintyReport, SensitivityQuery, SensitivityReport,
    CapacityQuery, CapacityReport)
from poliscope_engine.contracts.revisions import PreviewRequest
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.numeric import NumericError, RUNTIME_ID
from poliscope_engine.uncertainty import (UncertaintyError, number, decimal, unique, validate, propagate, scenarios)


def _record(service, context):
    record = service.read(context)
    if record.inputs.versions.numeric_runtime_id != RUNTIME_ID:
        raise UncertaintyError('historical_runtime_unavailable')
    return record


def _references(record, sources, assumptions, local=()):
    source_ids = {r.id for r in record.inputs.references if r.kind == 'source'}
    assumption_ids = {r.id for r in record.inputs.references if r.kind == 'assumption'} | {a.id for a in record.inputs.assumptions}
    if not set(sources) <= source_ids or not set(assumptions) <= assumption_ids | set(local):
        raise UncertaintyError('unresolved_provenance')
    if len(sources) > 100 or len(assumptions) > 100:
        raise UncertaintyError('reference_limit')


def _model(record, model):
    model = validate(model)
    values = {v.id: v for v in record.inputs.values}
    sources = sorted({r for p in model.parameters for r in p.source_refs})
    assumptions = sorted(set(model.assumption_refs) | {r for p in model.parameters for r in p.assumption_refs}
        | {r for f in model.factors for r in f.assumption_refs})
    _references(record, sources, assumptions, (a.id for a in model.assumptions))
    for parameter in model.parameters:
        if parameter.value_id not in values or values[parameter.value_id].value.kind != 'quantity':
            raise UncertaintyError('quantity_parameter_required')
        value = values[parameter.value_id]
        if value.partition not in ('conditions', 'assumptions', 'design'):
            raise UncertaintyError('parameter_partition_not_supported')
        if value.effective_time != record.inputs.design.effective_time:
            raise UncertaintyError('parameter_time_mismatch')
    # This exact affine method has dimensionless coefficients and no implicit
    # unit, spatial, denominator or time conversion.
    for expression in model.expressions:
        metadata = {_metadata(values[p.value_id]) for p in model.parameters
            if any(t.variable_id == p.id for t in expression.terms)}
        if len(metadata) > 1:
            raise UncertaintyError('expression_type_scope_time_mismatch')
    return model, values, sources, assumptions


def _metadata(row):
    value = row.value
    return value.unit_id, row.scope_id, value.time_basis_id, value.denominator_scope_id


def analyze(service, data):
    query = UncertaintyQuery.model_validate(data)
    record = _record(service, query.context)
    model, values, sources, assumptions = _model(record, query.model)
    try:
        rows = propagate(model)
    except NumericError as exc:
        rows = [dict(expression_id=e.id,status='solver_failure',reason=str(exc),low=None,high=None,
            probability=None,diagnostic='unavailable') for e in model.expressions]
    parameters = {p.id: p for p in model.parameters}
    for row, expression in zip(rows, model.expressions, strict=True):
        metadata = _metadata(values[parameters[expression.terms[0].variable_id].value_id]) if expression.terms else (None,)*4
        row.update(zip(('unit_id','scope_id','time_basis_id','denominator_scope_id'), metadata, strict=True))
    payload = dict(query=query,effective_time=record.inputs.design.effective_time,input_digest=digest(record.inputs),
        method=model.method,observations=rows,assumptions=assumptions,sources=sources)
    return UncertaintyReport.model_validate(dict(payload,report_digest=digest(payload)))


def sensitivity(service, data):
    query = SensitivityQuery.model_validate(data)
    record = _record(service, query.context)
    model, values, sources, assumptions = _model(record, query.model)
    if service.evidence(query.context).report is None:
        raise UncertaintyError('historical_evidence_unavailable')
    unique(query.variants)
    parameters = {p.id: p for p in model.parameters}
    joint = scenarios(model) if model.method == 'finite-factorization-v1' else None
    results = []
    for variant in query.variants:
        unique(variant.values, lambda v: v.variable_id)
        # All varying parameters must be explicitly selected, never filled by a
        # midpoint, source distribution or marginal mean.
        if {v.variable_id for v in variant.values} != set(parameters):
            raise UncertaintyError('explicit_complete_variant_required')
        if joint is not None and not any(all(state[v.variable_id] == number(v.value) for v in variant.values) for state, weight in joint):
            raise UncertaintyError('variant_outside_joint_support')
        changes = []
        for selected in variant.values:
            parameter, chosen = parameters[selected.variable_id], number(selected.value)
            if parameter.form == 'point' and chosen != number(parameter.point):
                raise UncertaintyError('variant_outside_declared_point')
            if parameter.form == 'bounded_range' and not number(parameter.low) <= chosen <= number(parameter.high):
                raise UncertaintyError('variant_outside_declared_range')
            if parameter.form == 'qualitative':
                raise UncertaintyError('qualitative_variant_unsupported')
            if parameter.form == 'distribution':
                support = {number(o.values[parameter.id]) for f in model.factors if parameter.id in f.variables for r in f.rows for o in r.outcomes
                    if int(o.probability.numerator) > 0}
                if chosen not in support:
                    raise UncertaintyError('variant_outside_declared_support')
            row = values[parameter.value_id]
            owner = next((o for o in record.inputs.owners if (o.entity_id,o.property_id,o.partition) == (row.entity_id,row.property_id,row.partition)), None)
            if owner is None:
                raise UncertaintyError('missing_parameter_owner')
            updated = row.model_dump()
            updated['value']['value'] = decimal(chosen)
            updated['provenance']['origin'] = 'player_input'
            updated['provenance']['source_refs'] = parameter.source_refs
            # Local method assumptions belong to this report; preview world
            # provenance keeps only existing revision-owned descriptors.
            existing = {r.id for r in record.inputs.references if r.kind == 'assumption'}
            updated['provenance']['assumption_refs'] = [r for r in parameter.assumption_refs if r in existing]
            changes.append(dict(kind='set_values',writer_id=owner.writer_id,partition=row.partition,values=[updated]))
        preview = service.preview(PreviewRequest.model_validate(dict(revision_contract=1,context=query.context,
            changes=changes,decision=dict(alternatives=[],selected_id=None,rationale_ref=None))))
        results.append(dict(id=variant.id,selected=variant,physical_digest=preview.report.physical_output_digest,report=preview.report))
    payload = dict(query=query,baseline=service.evidence(query.context).report,variants=results,assumptions=assumptions,sources=sources)
    return SensitivityReport.model_validate(dict(payload,report_digest=digest(payload)))


def capacity(service, data):
    query = CapacityQuery.model_validate(data)
    record = _record(service, query.context)
    unique(query.constraints)
    values = {v.id: v for v in record.inputs.values}
    if query.solved_entity_id not in {e.id for e in record.inputs.entities}:
        raise UncertaintyError('unknown_solved_entity')
    populations = [p for p in record.inputs.populations if p.entity_id == query.solved_entity_id]
    if populations and (len(populations) != 1 or populations[0].role != 'solved_capacity_bound'):
        raise UncertaintyError('population_role_conflict')
    if query.scope_id not in {s.id for s in record.inputs.scopes}:
        raise UncertaintyError('unknown_scope')
    if service.registry is None:
        raise UncertaintyError('capacity_unit_registry_unavailable')
    solved_unit = service.registry.units.unit(query.solved_unit_id)
    if populations and solved_unit.dimension != (('people', 1),):
        raise UncertaintyError('population_unit_mismatch')
    if solved_unit.kind != 'stock':
        raise UncertaintyError('solved_unit_must_be_stock')
    # The solved entity is not also a fixed/evolving input in this calculation.
    if any(v.entity_id == query.solved_entity_id and v.value.kind == 'quantity' for v in record.inputs.values):
        raise UncertaintyError('solved_variable_also_fixed_or_evolving')
    lower, upper, quantum = map(number, (query.lower,query.upper,query.quantum))
    if lower < 0 or upper < lower or quantum <= 0 or (lower/quantum).denominator != 1 or (upper/quantum).denominator != 1:
        raise UncertaintyError('invalid_capacity_grid')
    sources = sorted({r for c in query.constraints for r in c.source_refs})
    assumptions = sorted({r for c in query.constraints for r in c.assumption_refs})
    unique(query.assumptions)
    _references(record,sources,assumptions,(a.id for a in query.assumptions))
    constraints = []
    missing = False
    for constraint in query.constraints:
        value = values.get(constraint.available_value_id)
        if value is None or value.entity_id == query.solved_entity_id:
            raise UncertaintyError('invalid_fixed_input')
        if value.scope_id != query.scope_id or value.effective_time != record.inputs.design.effective_time:
            raise UncertaintyError('capacity_scope_time_mismatch')
        fixed, coefficient = number(constraint.fixed_demand), number(constraint.demand_per_unit)
        if fixed < 0 or coefficient < 0 or constraint.solved_unit_id != query.solved_unit_id:
            raise UncertaintyError('nonmonotone_or_incompatible_constraint')
        if value.value.kind == 'unknown':
            missing = True
            continue
        if value.value.kind != 'quantity' or (value.value.unit_id,value.value.time_basis_id,value.value.denominator_scope_id) != (constraint.resource_unit_id,query.time_basis_id,None):
            raise UncertaintyError('capacity_resource_type_mismatch')
        available = number(value.value.value)
        if available < 0:
            raise UncertaintyError('negative_capacity')
        constraints.append((constraint,value.value,available,fixed,coefficient))
    if len({c.available_value_id for c in query.constraints}) != len(query.constraints):
        raise UncertaintyError('duplicate_resource_budget')
    iterations, feasible, infeasible = 0, None, None
    def fits(count):
        return all(fixed + coefficient*count <= available for _,_,available,fixed,coefficient in constraints)
    if missing:
        status, reason = 'unmodeled','missing_fixed_resource'
    elif not fits(lower):
        status, reason, infeasible = 'infeasible','lower_boundary_infeasible',lower
    elif fits(upper):
        status, reason, feasible = 'upper_feasible','no_infeasible_boundary_in_selected_interval',upper
    else:
        a,b = int(lower/quantum),int(upper/quantum)
        while b-a > 1 and iterations < query.iteration_limit:
            middle = (a+b)//2
            if fits(middle*quantum):
                a = middle
            else:
                b = middle
            iterations += 1
        feasible,infeasible = a*quantum,b*quantum
        status,reason = ('bounded','exact_adjacent_grid_boundary') if b-a == 1 else ('solver_failure','iteration_limit_exceeded')
    try:
        witnesses = [dict(constraint_id=c.id,available=value,
            demand_at_feasible=None if feasible is None else decimal(fixed+coefficient*feasible),
            demand_at_infeasible=None if infeasible is None else decimal(fixed+coefficient*infeasible)) for c,value,_,fixed,coefficient in constraints]
        feasible = None if feasible is None else decimal(feasible)
        infeasible = None if infeasible is None else decimal(infeasible)
    except NumericError:
        status,reason,feasible,infeasible,witnesses='solver_failure','precision_unsupported',None,None,[]
    payload=dict(query=query,effective_time=record.inputs.design.effective_time,input_digest=digest(record.inputs),status=status,reason=reason,
        feasible=feasible,infeasible=infeasible,iterations=iterations,stopping_rule='adjacent_quantum_grid_points',witnesses=witnesses,
        assumptions=assumptions,sources=sources)
    return CapacityReport.model_validate(dict(payload,report_digest=digest(payload)))
