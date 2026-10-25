"""Exact affine boxes and finite factor tables. No sampling or hidden approximation."""
from fractions import Fraction
from poliscope_engine.contracts.uncertainty import UncertaintyModel, ExactRatio
from poliscope_engine.numeric import parse, exact, canonical, NumericError


class UncertaintyError(ValueError):
    pass


class UnsupportedPropagation(UncertaintyError):
    pass


def number(value):
    return Fraction(parse(value))


def decimal(value):
    return canonical(exact(value))


def ratio(value):
    if value.numerator.bit_length() > 840 or value.denominator.bit_length() > 840:
        raise UnsupportedPropagation('exact_probability_precision_limit')
    return ExactRatio(numerator=str(value.numerator), denominator=str(value.denominator))


def unique(rows, key=lambda r: r.id):
    result = {key(r): r for r in rows}
    if len(result) != len(rows):
        raise UncertaintyError('duplicate_identity')
    return result


def validate(model):
    model = UncertaintyModel.model_validate_json(model.model_dump_json())
    parameters = unique(model.parameters)
    assumptions = unique(model.assumptions)
    required = set(model.assumption_refs) | {r for p in model.parameters for r in p.assumption_refs} | {r for f in model.factors for r in f.assumption_refs}
    if not required <= assumptions.keys():
        raise UncertaintyError('unresolved_model_assumption')
    unique(model.expressions)
    unique(model.parameters, lambda p: p.value_id)
    for p in parameters.values():
        if p.form == 'point':
            if p.point is None or p.low is not None or p.high is not None:
                raise UncertaintyError('point_requires_only_point')
            number(p.point)
        elif p.form == 'bounded_range':
            if p.point is not None or p.low is None or p.high is None or number(p.low) > number(p.high):
                raise UncertaintyError('range_requires_ordered_bounds')
        elif any(v is not None for v in (p.point, p.low, p.high)):
            raise UncertaintyError('no_implicit_distribution_or_point')
    for expression in model.expressions:
        number(expression.constant)
        if expression.threshold is not None:
            number(expression.threshold)
        for term in expression.terms:
            number(term.coefficient)
            if term.variable_id not in parameters:
                raise UncertaintyError('unknown_variable')
    # Validate probability declarations even for a method we cannot execute.
    factors = unique(model.factors)
    owned = set()
    for factor in factors.values():
        variables, parents = set(factor.variables), set(factor.parents)
        if (len(variables) != len(factor.variables) or len(parents) != len(factor.parents)
                or variables & parents or owned & variables or not variables <= parameters.keys()
                or not parents <= parameters.keys()):
            raise UncertaintyError('invalid_factor_variables')
        if any(parameters[v].form != 'distribution' for v in variables | parents):
            raise UncertaintyError('factor_requires_distribution_variables')
        owned |= variables
        given_seen = set()
        for row in factor.rows:
            if set(row.given) != parents:
                raise UncertaintyError('conditional_parent_mismatch')
            given = tuple(sorted((k, number(v)) for k, v in row.given.items()))
            if given in given_seen:
                raise UncertaintyError('duplicate_conditional_row')
            given_seen.add(given)
            probability, outcomes_seen = Fraction(), set()
            for outcome in row.outcomes:
                if set(outcome.values) != variables:
                    raise UncertaintyError('joint_variable_mismatch')
                state = tuple(sorted((k, number(v)) for k, v in outcome.values.items()))
                if state in outcomes_seen:
                    raise UncertaintyError('duplicate_joint_outcome')
                outcomes_seen.add(state)
                weight = Fraction(int(outcome.probability.numerator), int(outcome.probability.denominator))
                if weight < 0 or weight > 1:
                    raise UncertaintyError('invalid_probability')
                probability += weight
            if probability != 1:
                raise UncertaintyError('probabilities_must_sum_to_one')
    if model.method == 'finite-factorization-v1' and owned != {p.id for p in parameters.values() if p.form == 'distribution'}:
        raise UncertaintyError('unbound_distribution')
    return model


def coefficients(expression):
    # Repeated references share a symbol, including exact cancellation.
    values = {}
    for term in expression.terms:
        values[term.variable_id] = values.get(term.variable_id, Fraction()) + number(term.coefficient)
    return {k: v for k, v in values.items() if v}


def _test(operation, value, threshold):
    return dict(lt=value < threshold, le=value <= threshold, eq=value == threshold,
                ne=value != threshold, ge=value >= threshold, gt=value > threshold)[operation]


def diagnostic(expression, low, high):
    if expression.threshold is None:
        return 'not_selected'
    threshold, op = number(expression.threshold), expression.operation
    if op in ('eq', 'ne'):
        if low == high == threshold:
            return 'always' if op == 'eq' else 'never'
        if threshold < low or threshold > high:
            return 'never' if op == 'eq' else 'always'
        return 'overlap'
    left, right = _test(op, low, threshold), _test(op, high, threshold)
    return 'always' if left and right else 'never' if not left and not right else 'overlap'


def scenarios(model):
    if model.method != 'finite-factorization-v1' or model.dependence != 'declared_factorization':
        raise UnsupportedPropagation('explicit_factorization_required')
    if any(p.form not in ('point', 'distribution') for p in model.parameters):
        raise UnsupportedPropagation('mixed_range_probability_not_supported')
    states = [({p.id: number(p.point) for p in model.parameters if p.form == 'point'}, Fraction(1))]
    pending = sorted(model.factors, key=lambda f: f.id)
    known = set(states[0][0])
    while pending:
        factor = next((f for f in pending if set(f.parents) <= known), None)
        if factor is None:
            raise UnsupportedPropagation('cyclic_or_unresolved_dependence')
        expanded, used = [], set()
        for state, probability in states:
            matches = [i for i, row in enumerate(factor.rows) if all(state[k] == number(v) for k, v in row.given.items())]
            if len(matches) != 1:
                raise UncertaintyError('missing_conditional_row')
            index = matches[0]
            used.add(index)
            for outcome in factor.rows[index].outcomes:
                weight = Fraction(int(outcome.probability.numerator), int(outcome.probability.denominator))
                if weight:
                    combined = probability * weight
                    if combined.numerator.bit_length() > 840 or combined.denominator.bit_length() > 840:
                        raise UnsupportedPropagation('exact_probability_precision_limit')
                    expanded.append((state | {k: number(v) for k, v in outcome.values.items()}, combined))
                    if len(expanded) > model.state_limit:
                        raise UnsupportedPropagation('exact_state_limit_exceeded')
        if used != set(range(len(factor.rows))):
            raise UncertaintyError('unreachable_conditional_row')
        states = expanded
        known.update(factor.variables)
        pending.remove(factor)
    return states


def propagate(model):
    model = validate(model)
    rows = []
    try:
        finite = scenarios(model) if model.method == 'finite-factorization-v1' else None
        if model.method == 'unsupported':
            raise UnsupportedPropagation('unsupported_propagation_method')
        if model.method == 'affine-box-v1':
            if model.factors or any(p.form not in ('point', 'bounded_range') for p in model.parameters):
                raise UnsupportedPropagation('affine_requires_point_or_range')
            if model.dependence != 'declared_box':
                raise UnsupportedPropagation('explicit_admissible_box_required')
    except UnsupportedPropagation as exc:
        return [dict(expression_id=e.id,status='unmodeled',reason=str(exc),low=None,high=None,probability=None,diagnostic='unavailable') for e in model.expressions]
    parameters = {p.id: p for p in model.parameters}
    for expression in model.expressions:
        try:
            terms, constant = coefficients(expression), number(expression.constant)
            if finite is None:
                low = high = constant
                for identity, coefficient in terms.items():
                    p = parameters[identity]
                    a, b = (number(p.point), number(p.point)) if p.form == 'point' else (number(p.low), number(p.high))
                    x, y = coefficient*a, coefficient*b
                    low, high = low + min(x, y), high + max(x, y)
                probability = None
                status = diagnostic(expression, low, high)
            else:
                values = [(constant + sum((c*s[k] for k, c in terms.items()), Fraction()), weight) for s, weight in finite]
                low, high = min(v for v, _ in values), max(v for v, _ in values)
                probability = None if expression.threshold is None else sum((w for v,w in values if _test(expression.operation,v,number(expression.threshold))), Fraction())
                status = 'not_selected' if probability is None else 'always' if probability == 1 else 'never' if probability == 0 else 'overlap'
            rows.append(dict(expression_id=expression.id,status='known',reason='exact_supported_method',low=decimal(low),high=decimal(high),
                probability=None if probability is None else ratio(probability),diagnostic=status))
        except (NumericError, UnsupportedPropagation) as exc:
            rows.append(dict(expression_id=expression.id,status='solver_failure' if isinstance(exc,NumericError) else 'unmodeled',
                reason=str(exc),low=None,high=None,probability=None,diagnostic='unavailable'))
    return rows
