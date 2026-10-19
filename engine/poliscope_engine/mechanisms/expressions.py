"""Pure bounded graph validation/execution. No imports or callbacks from content."""
from hashlib import sha256
import json
from . import MechanismError
from poliscope_engine.contracts.expressions import ExpressionGraph
from poliscope_engine.contracts.world import QuantityValue
from poliscope_engine.numeric import parse, calculate, canonical

# Versioned runtime operators. Changing semantics requires a new operator/model.
OPERATORS = frozenset((name, 'v1') for name in
                      ('add', 'subtract', 'multiply', 'divide', 'minimum', 'maximum'))
MAX_DEPTH = 32


def snapshot(graph):
    return ExpressionGraph.model_validate_json(graph.model_dump_json())


def graph_digest(graph):
    return 'sha256:' + sha256(json.dumps(snapshot(graph).model_dump(mode='json'),
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def compile_graph(graph, definition, phase, registry, world):
    """Validate the entire DAG, including unused nodes, before doing arithmetic."""
    graph = snapshot(graph)
    nodes = {n.id: n for n in graph.nodes}
    if len(nodes) != len(graph.nodes):
        raise MechanismError('duplicate_node')
    inputs = {p.id: p for p in definition.inputs}
    types, dependencies, depths, order = {}, {}, {}, []
    remaining = set(nodes)
    while remaining:
        progressed = False
        for identity in sorted(remaining):
            node = nodes[identity]
            refs = node.arguments if node.kind == 'operator' else []
            if any(ref not in nodes for ref in refs):
                raise MechanismError('missing_node')
            if any(ref not in types for ref in refs):
                continue
            depth = 1 + max((depths[ref] for ref in refs), default=0)
            if depth > MAX_DEPTH:
                raise MechanismError('graph_depth_exceeded')
            if node.kind == 'input':
                if node.input_id not in inputs:
                    raise MechanismError('unknown_input')
                value_type = inputs[node.input_id].value_type
                deps = {node.input_id}
            elif node.kind == 'constant':
                value_type = node.value_type
                if value_type.kind != 'quantity':
                    raise MechanismError('constant_requires_quantity')
                parse(node.value)
                deps = set()
            else:
                if (node.operator.id, node.operator.version) not in OPERATORS:
                    raise MechanismError('unknown_operator')
                left, right = (types[ref] for ref in refs)
                if left.kind != 'quantity' or right.kind != 'quantity':
                    raise MechanismError('operator_requires_quantity')
                if node.operator.id in ('multiply', 'divide'):
                    # Explicit dimensionless factor only; no invented unit algebra.
                    unit = registry.units.unit(right.unit_id)
                    if (unit.dimension or unit.kind != 'indicator' or unit.scale != 1
                            or right.time_basis_id is not None or right.denominator_scope_id is not None):
                        raise MechanismError('dimensionless_factor_required')
                elif left != right:
                    raise MechanismError('incompatible_operator_units')
                value_type = left
                deps = set().union(*(dependencies[ref] for ref in refs))
            registry._type(value_type, world)
            types[identity], dependencies[identity], depths[identity] = value_type, deps, depth
            order.append(identity)
            remaining.remove(identity)
            progressed = True
        if not progressed:
            raise MechanismError('graph_cycle')
    outputs = {p.id: p for p in definition.outputs}
    states = {s.id: s for s in definition.owned_state}
    if set(graph.outputs) != set(outputs):
        raise MechanismError('graph_output_mismatch')
    expected_state = set(definition.write_state_refs) if phase == 'transition' else set()
    if set(graph.state) != expected_state:
        raise MechanismError('graph_state_mismatch')
    for key, ref in (*graph.outputs.items(), *graph.state.items()):
        if ref not in types:
            raise MechanismError('missing_node')
        expected = outputs[key] if key in graph.outputs else states[key]
        if types[ref] != expected.value_type:
            raise MechanismError('graph_result_type_mismatch')
        if key in graph.outputs and dependencies[ref] != set(expected.input_refs):
            raise MechanismError('graph_input_dependencies_mismatch')
    return graph, order


def evaluate_graph(graph, definition, phase, registry, world, inputs):
    """Local arithmetic only; None is unknown, never a zero/default/allocation.

    Caller must separately enforce mechanism preconditions, allocation and policy
    semantics. Returned state values are proposals, never a world mutation.
    """
    graph, order = compile_graph(graph, definition, phase, registry, world)
    ports = {p.id: p for p in definition.inputs}
    if set(inputs) - set(ports):
        raise MechanismError('unknown_input')
    # Snapshot even caller-supplied DTOs and validate all provided inputs.
    from pydantic import TypeAdapter
    from poliscope_engine.contracts.world import WorldValue
    adapter = TypeAdapter(WorldValue)
    values = {}
    for key, value in inputs.items():
        if value is not None:
            value = adapter.validate_json(value.model_dump_json())
            if value.kind == 'unknown':
                value = None
            else:
                registry.validate_value(ports[key].value_type, value, world)
        values[key] = value
    nodes = {n.id: n for n in graph.nodes}
    evaluated = {}
    for identity in order:
        node = nodes[identity]
        if node.kind == 'input':
            value = values.get(node.input_id)
        elif node.kind == 'constant':
            value = QuantityValue(kind='quantity', value=canonical(parse(node.value)),
                                  **node.value_type.model_dump(exclude={'kind'}))
        else:
            left, right = (evaluated[ref] for ref in node.arguments)
            if left is None or right is None:
                value = None
            else:
                a, b = parse(left.value), parse(right.value)
                operation = node.operator.id
                result = (min(a, b) if operation == 'minimum' else max(a, b)
                          if operation == 'maximum' else calculate(a, b, operation))
                value = left.model_copy(update={'value': canonical(result)})
        evaluated[identity] = value
    return ({key: evaluated[ref] for key, ref in graph.outputs.items()},
            {key: evaluated[ref] for key, ref in graph.state.items()})
