"""Pure, review-gated static dependency compiler; never executes a mechanism."""
from dataclasses import dataclass
from hashlib import sha256
from heapq import heapify, heappop, heappush
import json

from poliscope_engine.contracts.dependencies import DependencyRequest

# Tuple namespaces avoid collisions even when imported IDs contain punctuation.
Key = tuple[str, ...]


class DependencyError(ValueError):
    pass


@dataclass(frozen=True)
class Node:
    key: Key
    value_type_json: str | None


@dataclass(frozen=True)
class Component:
    nodes: tuple[Key, ...]
    cyclic: bool
    status: str  # ready, missing_input, solver_required, blocked


@dataclass(frozen=True)
class CompiledDependencies:
    request_json: str
    model: tuple[str, str]
    digest: str
    nodes: tuple[Node, ...]
    edges: tuple[tuple[Key, Key], ...]
    components: tuple[Component, ...]  # condensation DAG in stable topological order
    missing_inputs: tuple[Key, ...]
    context_edges: tuple[tuple[str, str, str, str], ...]


def _components(keys, edges, missing):
    """Iterative Kosaraju plus stable condensation ordering; no recursion limit."""
    forward = {k: [] for k in keys}
    reverse = {k: [] for k in keys}
    for a, b in sorted(edges):
        forward[a].append(b)
        reverse[b].append(a)
    seen, finished = set(), []
    for root in sorted(keys):
        if root in seen:
            continue
        seen.add(root)
        stack = [(root, iter(forward[root]))]
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                finished.append(node)
                stack.pop()
            elif child not in seen:
                seen.add(child)
                stack.append((child, iter(forward[child])))
    groups, seen = [], set()
    for root in reversed(finished):
        if root in seen:
            continue
        group, stack = [], [root]
        seen.add(root)
        while stack:
            node = stack.pop()
            group.append(node)
            for child in reverse[node]:
                if child not in seen:
                    seen.add(child)
                    stack.append(child)
        groups.append(tuple(sorted(group)))
    owner = {node: i for i, group in enumerate(groups) for node in group}
    parents, children = [set() for _ in groups], [set() for _ in groups]
    for a, b in edges:
        i, j = owner[a], owner[b]
        if i != j:
            parents[j].add(i)
            children[i].add(j)
    degree = [len(p) for p in parents]
    ready = [(groups[i], i) for i, count in enumerate(degree) if not count]
    heapify(ready)
    result, statuses = [], {}
    while ready:
        group, i = heappop(ready)
        cyclic = len(group) > 1 or (group[0], group[0]) in edges
        status = ('solver_required' if cyclic else
                  'missing_input' if any(n in missing for n in group) else
                  'blocked' if any(statuses[p] != 'ready' for p in parents[i]) else 'ready')
        statuses[i] = status
        result.append(Component(group, cyclic, status))
        for child in children[i]:
            degree[child] -= 1
            if degree[child] == 0:
                heappush(ready, (groups[child], child))
    return tuple(result)


def compile_dependencies(request, registry, world):
    """Validate and expand active ports/claims before SCC detection.

    Ready means structurally schedulable, not solved or scientifically supported.
    Allocation nodes still require a host-selected finite procedure at execution.
    Cyclic components remain explicitly unresolved until WP-014-solvers.
    """
    request = DependencyRequest.model_validate_json(request.model_dump_json())
    instances = {i.id: i for i in request.instances}
    if len(instances) != len(request.instances):
        raise DependencyError('duplicate_instance')
    definitions = {i.id: registry.activate(i.mechanism_id, i.mechanism_version,
        phase='static', world=world, scope_id=i.scope_id, entity_id=i.entity_id, allow_unmodeled=True)
        for i in request.instances}
    nodes, edges, missing, supplied = {}, set(), set(), set()
    inputs, outputs = {}, {}

    def add(key, value_type=None):
        encoded = value_type.model_dump_json() if value_type is not None else None
        if key in nodes and nodes[key] != encoded:
            raise DependencyError('incompatible_shared_node')
        nodes[key] = encoded
        return key

    for identity, definition in sorted(definitions.items()):
        for port in definition.inputs:
            key = add(('input', identity, port.id), port.value_type)
            inputs[key] = port
        for port in definition.outputs:
            key = add(('output', identity, port.id), port.value_type)
            outputs[key] = port
            edges.update((('input', identity, p), key) for p in port.input_refs)
            edges.update((('input', identity, p), key)
                         for condition in definition.preconditions for p in condition.input_refs)
        if len(nodes) > 25000 or len(edges) > 50000:
            raise DependencyError('dependency_budget_exhausted')

    def input_key(ref):
        key = ('input', ref.instance_id, ref.port_id)
        if key not in inputs:
            raise DependencyError('unknown_input')
        return key

    def supply(key):
        if key in supplied:
            raise DependencyError('multiple_input_producers')
        supplied.add(key)

    for binding in request.bindings:
        source = ('output', binding.producer.instance_id, binding.producer.port_id)
        target = input_key(binding.consumer)
        if source not in outputs:
            raise DependencyError('unknown_output')
        if nodes[source] != nodes[target]:
            raise DependencyError('incompatible_port')
        if instances[source[1]].scope_id != instances[target[1]].scope_id:
            raise DependencyError('cross_scope_requires_adapter')
        supply(target)
        edges.add((source, target))
    fixed = {}
    for item in request.fixed_inputs:
        target = input_key(item.consumer)
        supply(target)
        if item.value.kind == 'unknown':
            if inputs[target].missing_behavior == 'propagate':
                missing.add(target)
        else:
            registry.validate_value(inputs[target].value_type, item.value, world)
        fixed[target] = item.value

    declared = {(i, c.id): c for i, d in definitions.items() for c in d.claims}
    assigned, accounts, account_types = set(), {}, {}
    for binding in request.claims:
        identity = binding.instance_id, binding.claim_id
        if identity not in declared or identity in assigned:
            raise DependencyError('unknown_or_duplicate_claim')
        assigned.add(identity)
        claim = declared[identity]
        instance = instances[binding.instance_id]
        if world.entity(binding.account_id).entity_kind != 'account':
            raise DependencyError('claim_requires_account')
        # A shared physical account cannot be split into independent allocations.
        group = accounts.setdefault(binding.account_id, binding.allocation_id)
        if group != binding.allocation_id:
            raise DependencyError('split_shared_account')
        amount = ('output', instance.id, claim.amount_output_ref)
        account_type = account_types.setdefault(binding.account_id, nodes[amount])
        if account_type != nodes[amount]:
            raise DependencyError('incompatible_account_quantity')
        account = add(('account', binding.account_id), outputs[amount].value_type)
        allocation = add(('allocation', binding.allocation_id))
        requested = add(('claim', *identity), outputs[amount].value_type)
        actual = add(('actual_consumption', *identity), outputs[amount].value_type)
        account_input = ('input', instance.id, claim.account_input_ref)
        # The same account input can serve several claims, but cannot disagree.
        if account_input in fixed:
            value = fixed[account_input]
            if value.kind != 'reference' or value.entity_id != binding.account_id:
                raise DependencyError('claim_account_mismatch')
        elif account_input in supplied:
            if (account, account_input) not in edges:
                raise DependencyError('claim_account_mismatch')
        else:
            supply(account_input)
        edges.add((account, account_input))
        allocated_input = ('input', instance.id, claim.allocation_input_ref)
        supply(allocated_input)
        edges.update(((amount, requested), (account, requested),
                      (requested, allocation), (account, allocation),
                      (allocation, actual), (actual, allocated_input)))
        # Preserve declared allocation dependencies even if a future port
        # representation changes: request amounts never substitute for actuals.
        edges.update((actual, ('output', instance.id, p)) for p in claim.dependent_output_refs)
    if assigned != set(declared):
        raise DependencyError('unbound_claim')
    produced_accounts = set()
    for item in request.account_producers:
        source = ('output', item.producer.instance_id, item.producer.port_id)
        if source not in outputs:
            raise DependencyError('unknown_output')
        if outputs[source].value_type.kind != 'quantity':
            raise DependencyError('account_requires_quantity')
        if item.account_id not in accounts:
            raise DependencyError('unbound_produced_account')
        if account_types[item.account_id] != nodes[source]:
            raise DependencyError('incompatible_account_quantity')
        link = (source, ('account', item.account_id))
        if link in produced_accounts:
            raise DependencyError('duplicate_account_producer')
        produced_accounts.add(link)
        edges.add(link)
    for key, port in inputs.items():
        if key not in supplied and (port.required or port.missing_behavior == 'propagate'):
            missing.add(key)
    context = set()
    for link in request.relationships:
        if link.source_instance_id not in instances or link.target_instance_id not in instances:
            raise DependencyError('unknown_context_instance')
        item = (link.kind, link.source_instance_id, link.target_instance_id, link.relationship_ref)
        if item in context:
            raise DependencyError('duplicate_context_relationship')
        context.add(item)
    if len(nodes) > 25000 or len(edges) > 50000:
        raise DependencyError('dependency_budget_exhausted')
    components = _components(nodes, edges, missing)
    # Canonicalize unordered request collections; political procedure order is
    # absent here and must be supplied explicitly to the allocator by the solver.
    data = request.model_dump(mode='json')
    for field in ('instances', 'bindings', 'fixed_inputs', 'claims', 'account_producers', 'relationships'):
        data[field].sort(key=lambda v: json.dumps(v, sort_keys=True))
    encoded = json.dumps(data, sort_keys=True, separators=(',', ':'))
    fingerprint = json.dumps(dict(request=data, model=registry.model,
        definitions={i: d.model_dump(mode='json') for i, d in sorted(definitions.items())}),
        sort_keys=True, separators=(',', ':'))
    return CompiledDependencies(encoded, registry.model,
        'sha256:' + sha256(fingerprint.encode()).hexdigest(),
        tuple(Node(k, nodes[k]) for k in sorted(nodes)), tuple(sorted(edges)),
        components, tuple(sorted(missing)), tuple(sorted(context)))
