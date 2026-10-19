"""Explicit host-selected precondition semantics; descriptions are not code."""
from poliscope_engine.contracts.evaluation import ConditionRule
from poliscope_engine.numeric import parse
from poliscope_engine.dependencies import DependencyError


def validate_conditions(rules, dependencies, registry, world):
    result = {}
    instances = {i.id: i for i in dependencies.instances}
    for raw in rules:
        rule = ConditionRule.model_validate_json(raw.model_dump_json())
        key = rule.instance_id, rule.precondition_id
        if key in result or rule.instance_id not in instances:
            raise DependencyError('invalid_condition_binding')
        instance = instances[rule.instance_id]
        definition = registry.definition(instance.mechanism_id, instance.mechanism_version)
        condition = next((c for c in definition.preconditions if c.id == rule.precondition_id), None)
        if condition is None or condition.input_refs != [rule.input_id]:
            raise DependencyError('unsupported_condition_inputs')
        port = next(p for p in definition.inputs if p.id == rule.input_id)
        if rule.operation == 'known':
            if rule.value is not None:
                raise DependencyError('unexpected_condition_value')
        else:
            if rule.value is None or rule.value.kind == 'unknown':
                raise DependencyError('missing_condition_value')
            registry.validate_value(port.value_type, rule.value, world)
            if rule.operation not in ('eq', 'ne') and port.value_type.kind != 'quantity':
                raise DependencyError('nonquantity_condition_order')
        result[key] = rule
    return result


def check_conditions(instance_id, definition, rules, state):
    for condition in definition.preconditions:
        rule = rules.get((instance_id, condition.id))
        if rule is None:
            return 'precondition_evaluation_required'
        value = state.get(('input', instance_id, rule.input_id))
        if value is None or value.kind == 'unknown':
            return 'missing_input'
        if rule.operation == 'known':
            continue
        other = rule.value
        if value.kind == 'quantity':
            left, right = parse(value.value), parse(other.value)
        else:
            left, right = value.model_dump(), other.model_dump()
        passed = (left == right if rule.operation == 'eq' else
                  left != right if rule.operation == 'ne' else
                  left < right if rule.operation == 'lt' else
                  left <= right if rule.operation == 'le' else
                  left > right if rule.operation == 'gt' else left >= right)
        if not passed:
            return condition.failure_behavior
    return None
