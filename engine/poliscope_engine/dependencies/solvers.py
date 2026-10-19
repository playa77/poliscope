"""Pure, bounded execution. Only reviewed registry implementations run.

Static callback protocol: callback(output_id, inputs), with only the declared
input_refs available. Callbacks return a WorldValue; no account writes occur.
Solver plans are trusted host selections, never executable pack content.
"""
from dataclasses import dataclass, replace
from decimal import DecimalException, localcontext
from types import MappingProxyType
from pydantic import TypeAdapter

from poliscope_engine.contracts.solvers import ExecutionRequest
from poliscope_engine.contracts.world import WorldValue, QuantityValue, ReferenceValue
from poliscope_engine.contracts.mechanisms import PortType
from poliscope_engine.contracts.allocations import AllocationRequest
from poliscope_engine.contracts.accounts import AccountBatch, AccountPosting
from poliscope_engine.accounts import AccountBook, AccountError
from poliscope_engine.allocations import allocate
from poliscope_engine.numeric import parse, canonical, context, NumericError, RUNTIME_ID
from poliscope_engine.mechanisms import MechanismError
from . import compile_dependencies, DependencyError, _components

VALUE = TypeAdapter(WorldValue)
TYPE = TypeAdapter(PortType)


class Failure(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class NumericalResult:
    # JSON strings keep nested DTOs detached and immutable.
    request_json: str
    compiler_digest: str
    model: tuple[str, str]
    numeric_runtime_id: str
    values: tuple[tuple[tuple[str, ...], str], ...]
    statuses: tuple[tuple[tuple[str, ...], str], ...]
    diagnostics: tuple[tuple[tuple[tuple[str, ...], ...], str], ...]
    batch_json: str | None
    operations: int


def linear_eliminate(matrix, rhs, spend):
    """Stable first-nonzero pivot; fresh Decimal28 context supplied by caller."""
    n = len(rhs)
    a = [list(row) + [value] for row, value in zip(matrix, rhs, strict=True)]
    pivot_row, pivots = 0, []
    for column in range(n):
        pivot = next((r for r in range(pivot_row, n) if a[r][column]), None)
        if pivot is None:
            continue
        a[pivot_row], a[pivot] = a[pivot], a[pivot_row]
        divisor = a[pivot_row][column]
        for j in range(column, n + 1):
            spend()
            a[pivot_row][j] /= divisor
        for r in range(n):
            if r == pivot_row:
                continue
            factor = a[r][column]
            for j in range(column, n + 1):
                spend()
                a[r][j] -= factor * a[pivot_row][j]
        pivots.append(column)
        pivot_row += 1
    if any(not any(row[:n]) and row[n] for row in a):
        raise Failure('inconsistent_system')
    if len(pivots) != n:
        raise Failure('singular_system')
    return [row[n] for row in a]


def execute(request, registry, world):
    request = ExecutionRequest.model_validate_json(request.model_dump_json())
    graph = compile_dependencies(request.dependencies, registry, world)
    dep = request.dependencies
    nodes = {n.key: n for n in graph.nodes}
    instances = {i.id: i for i in dep.instances}
    definitions = {i.id: registry.definition(i.mechanism_id, i.mechanism_version) for i in dep.instances}
    fixed = {('input', f.consumer.instance_id, f.consumer.port_id): f.value for f in dep.fixed_inputs}
    claim_links = {(c.instance_id, c.claim_id): c for c in dep.claims}
    runtime = {(c.instance_id, c.claim_id): c.account_claim_id for c in request.claims}
    if len(runtime) != len(request.claims) or set(runtime) != set(claim_links) or len(set(runtime.values())) != len(runtime):
        raise DependencyError('invalid_runtime_claims')
    plans = {p.id: p for p in request.allocations}
    if len(plans) != len(request.allocations) or set(plans) != {c.allocation_id for c in dep.claims}:
        raise DependencyError('invalid_finite_plans')
    batch = request.batch
    if claim_links and batch is None:
        raise DependencyError('missing_account_batch')
    if batch is not None:
        AccountBook(batch, registry.units).evaluate()
        account_defs = {a.id: a for a in batch.accounts}
        account_claims = {c.id: c for c in batch.claims}
        if set(account_claims) != set(runtime.values()):
            raise DependencyError('unbound_account_claims')
        for identity, link in claim_links.items():
            c = account_claims[runtime[identity]]
            a = account_defs.get(link.account_id)
            t = TYPE.validate_json(nodes['account', link.account_id].value_type_json)
            if (c.account_id != link.account_id or a is None or
                a.scope_id != instances[identity[0]].scope_id or a.unit_id != t.unit_id or
                a.period_id != t.time_basis_id or t.denominator_scope_id is not None):
                raise DependencyError('incompatible_runtime_account')
        for pid, plan in plans.items():
            ids = {runtime[k] for k, link in claim_links.items() if link.allocation_id == pid}
            if {c.claim_id for c in plan.choices} != ids or len(plan.choices) != len(ids):
                raise DependencyError('invalid_finite_choices')
            if plan.procedure is not None and (set(plan.claim_order) != ids or len(plan.claim_order) != len(ids)):
                raise DependencyError('invalid_claim_order')
    # Host choices extend the numerical graph before execution/SCC selection.
    # Funding and transformation links cannot create an implicit single pass.
    edges = set(graph.edges)
    funding_users = {}
    resource_users = {}
    for link in dep.claims:
        resource_users.setdefault(link.account_id, set()).add(link.allocation_id)
    produced_targets = {p.account_id for p in dep.account_producers}
    for pid, plan in plans.items():
        for choice in plan.choices:
            if produced_targets & {o.account_id for o in choice.outputs}:
                raise DependencyError('duplicate_production_authority')
            for requirement in choice.requirements:
                funding_users.setdefault(requirement.account_id, set()).add(pid)
                source = ('account', requirement.account_id)
                if source in nodes:
                    edges.add((source, ('allocation', pid)))
            for output in choice.outputs:
                target = ('account', output.account_id)
                if target in nodes:
                    edges.add((('allocation', pid), target))
    # Separate groups have no declared joint priority over shared funding.
    contenders = [users | resource_users.get(aid, set()) for aid, users in funding_users.items()]
    ambiguous_funding = {('allocation', pid) for users in contenders
                         if len(users) > 1 for pid in users}
    if len(edges) > 50000:
        raise DependencyError('dependency_budget_exhausted')
    graph = replace(graph, edges=tuple(sorted(edges)), components=_components(nodes, edges, set(graph.missing_inputs)))
    parents = {n: [] for n in nodes}
    for source, target in graph.edges:
        parents[target].append(source)
    solver_for = {}
    cyclic = {frozenset(c.nodes) for c in graph.components if c.cyclic}
    for plan in request.solvers:
        keys = tuple(map(tuple, plan.nodes))
        if len(set(keys)) != len(keys) or frozenset(keys) not in cyclic or any(k in solver_for for k in keys):
            raise DependencyError('invalid_solver_component')
        if any(k[0] not in ('input', 'output') or nodes[k].value_type_json is None or TYPE.validate_json(nodes[k].value_type_json).kind != 'quantity' for k in keys):
            raise DependencyError('inapplicable_solver')
        if parse(plan.tolerance) < 0:
            raise DependencyError('invalid_tolerance')
        if plan.kind == 'iterative':
            if (set(map(tuple, plan.update_order)) != set(keys) or len(plan.update_order) != len(keys) or
                {tuple(s.node) for s in plan.starting_state} != set(keys) or len(plan.starting_state) != len(keys) or plan.equations):
                raise DependencyError('invalid_iteration_contract')
        elif (set(tuple(e.node) for e in plan.equations) != set(keys) or len(plan.equations) != len(keys)
              or plan.starting_state or plan.update_order):
            raise DependencyError('invalid_linear_contract')
        for key in keys:
            solver_for[key] = plan
    values, statuses, diagnostics = {}, {}, []
    operations = 0
    actuals = {}
    missing = set(graph.missing_inputs)

    def spend():
        nonlocal operations
        if operations >= request.operation_limit:
            raise Failure('budget_exhausted')
        operations += 1

    def quantity(key, number):
        t = TYPE.validate_json(nodes[key].value_type_json)
        return QuantityValue(kind='quantity', value=canonical(number), unit_id=t.unit_id,
            time_basis_id=t.time_basis_id, denominator_scope_id=t.denominator_scope_id)

    def number(value):
        if value.kind != 'quantity':
            raise Failure('nonquantity_solver_value')
        return parse(value.value)

    def calculate(key, state):
        nonlocal batch
        spend()
        kind = key[0]
        if kind == 'input':
            if key in fixed and fixed[key].kind != 'unknown':
                return fixed[key]
            source = next((p for p in parents[key] if p[0] in ('output', 'actual_consumption', 'account')), None)
            if source is None:
                port = next(p for p in definitions[key[1]].inputs if p.id == key[2])
                if not port.required and port.missing_behavior == 'omit':
                    return None
                raise Failure('missing_input')
            if source[0] == 'account':
                return ReferenceValue(kind='reference', entity_id=source[1])
            return state[source]
        if kind == 'output':
            instance = instances[key[1]]
            definition = definitions[key[1]]
            if definition.preconditions:
                raise Failure('precondition_evaluation_required')
            port = next(p for p in definition.outputs if p.id == key[2])
            inputs = {p: VALUE.validate_json(state['input', key[1], p].model_dump_json()) for p in port.input_refs
                      if ('input', key[1], p) in state}
            procedure = definition.support.static
            if procedure.kind == 'declarative_graph':
                result = registry.evaluate_graph(instance.mechanism_id, instance.mechanism_version,
                    phase='static', world=world, scope_id=instance.scope_id, entity_id=instance.entity_id, inputs=inputs)
                value = result[0][key[2]]
                if value is None:
                    raise Failure('missing_input')
            else:
                impl = next(i for i in registry.implementations if i.key ==
                    (procedure.implementation.id, procedure.implementation.version, 'static'))
                try:
                    with localcontext(context()):
                        value = VALUE.validate_python(impl.callback(key[2], MappingProxyType(inputs)))
                except Exception as exc:
                    raise Failure('implementation_failure') from exc
            if value.kind == 'unknown':
                raise Failure('missing_input')
            registry.validate_value(port.value_type, value, world)
            return value
        if kind == 'account':
            if batch is None:
                raise Failure('missing_input')
            for producer in (p for p in parents[key] if p[0] == 'output'):
                amount = number(state[producer])
                used = {v.id for group in (batch.accounts, batch.postings, batch.claims, batch.reservations, batch.subtotals) for v in group}
                serial = 0
                while f'solver:production:{serial}' in used:
                    serial += 1
                posting = AccountPosting(id=f'solver:production:{serial}', kind='production',
                    source_id=None, destination_id=key[1], amount=canonical(amount),
                    reservation_id=None, claim_id=None, mechanism_ref=definitions[producer[1]].id, source_refs=definitions[producer[1]].source_refs)
                batch = AccountBatch.model_validate(batch.model_dump() | {'postings': [*batch.postings, posting]})
            result = AccountBook(batch, registry.units).evaluate()
            return quantity(key, parse(next(a.available for a in result.accounts if a.account_id == key[1])))
        if kind == 'claim':
            return state[next(p for p in parents[key] if p[0] == 'output')]
        if kind == 'allocation':
            plan = plans[key[1]]
            identities = [k for k, link in claim_links.items() if link.allocation_id == key[1]]
            amounts = {runtime[k]: number(state['claim', *k]) for k in identities}
            claims = [c.model_copy(update={'requested': canonical(amounts[c.id])}) for c in batch.claims if c.id in amounts]
            # Keep every other group's holds unavailable in the local allocation.
            other_holds = []
            used_hold_ids = {v.id for group in (batch.accounts, batch.postings, batch.claims, batch.reservations, batch.subtotals) for v in group}
            hold_serial = 0
            for reservation in batch.reservations:
                if reservation.claim_id not in amounts:
                    fulfilled = sum((parse(p.amount) for p in batch.postings if p.reservation_id == reservation.id), parse('0'))
                    remaining = parse(reservation.amount) - fulfilled
                    if remaining:
                        while f'solver:hold:{hold_serial}' in used_hold_ids:
                            hold_serial += 1
                        hold_id = f'solver:hold:{hold_serial}'
                        used_hold_ids.add(hold_id)
                        other_holds.append(AccountPosting(id=hold_id, kind='use', source_id=reservation.account_id,
                            destination_id=None, amount=canonical(remaining), reservation_id=None, claim_id=None,
                            mechanism_ref='solver:other-hold', source_refs=[]))
            selected = batch.model_copy(update={'claims': claims,
                'reservations': [r for r in batch.reservations if r.claim_id in amounts]})
            # Other groups' claimed fulfillment is retained as an ordinary use;
            # their reservation IDs cannot refer to this bounded claim subset.
            selected = selected.model_copy(update={'postings': [p.model_copy(update={'claim_id': None, 'reservation_id': None})
                if p.claim_id not in amounts else p for p in selected.postings] + other_holds})
            result = allocate(AllocationRequest(contract_version=1, batch=selected, procedure=plan.procedure,
                claim_order=plan.claim_order, choices=plan.choices, mechanism_ref=plan.mechanism_ref, source_refs=[]), registry.units)
            if result.status != 'resolved':
                raise Failure('allocation_unresolved:' + ','.join(result.missing))
            new = result.batch.postings[len(selected.postings):]
            # Allocator-local serials are replaced with globally unique IDs.
            used = {p.id for p in batch.postings} | {a.id for a in batch.accounts} | {c.id for c in batch.claims} | {r.id for r in batch.reservations} | {s.id for s in batch.subtotals}
            renamed = []
            serial = 0
            for posting in new:
                while f'solver:allocation:{serial}' in used:
                    serial += 1
                pid = f'solver:allocation:{serial}'
                used.add(pid)
                renamed.append(posting.model_copy(update={'id': pid}))
            batch = AccountBatch.model_validate(batch.model_dump() | {'claims': [next((c for c in claims if c.id == old.id), old) for old in batch.claims],
                'postings': [*batch.postings, *renamed]})
            AccountBook(batch, registry.units).evaluate()
            actuals.update({k: next(a.actual for a in result.accounts.claims if a.claim_id == runtime[k]) for k in identities})
            return None
        if kind == 'actual_consumption':
            return quantity(key, parse(actuals[key[1:]]))
        raise Failure('unsupported_node')

    def solve(component, plan):
        keys = tuple(sorted(component.nodes))
        if plan.kind == 'linear':
            equations = {tuple(e.node): e for e in plan.equations}
            matrix, rhs = [], []
            for key in keys:
                e = equations[key]
                row = [parse('1') if k == key else parse('0') for k in keys]
                right = parse(e.constant)
                seen = set()
                for term in e.terms:
                    source = tuple(term.node)
                    if source in seen or source not in parents[key]:
                        raise Failure('invalid_linear_dependency')
                    seen.add(source)
                    coefficient = parse(term.coefficient)
                    if source in keys:
                        row[keys.index(source)] -= coefficient
                    else:
                        right += coefficient * number(values[source])
                matrix.append(row)
                rhs.append(right)
            solved = linear_eliminate(matrix, rhs, spend)
            candidate = values | {k: quantity(k, v) for k, v in zip(keys, solved, strict=True)}
        else:
            candidate = values | {tuple(s.node): quantity(tuple(s.node), parse(s.value)) for s in plan.starting_state}
        count = 1 if plan.kind == 'linear' else plan.iteration_limit
        tolerance = parse(plan.tolerance)
        for _ in range(count):
            if plan.kind == 'iterative':
                updated = dict(candidate)
                for raw in plan.update_order:
                    key = tuple(raw)
                    updated[key] = calculate(key, candidate if plan.update_mode == 'simultaneous' else updated)
                candidate = updated
            # Verify the equations against actual reviewed mechanism execution,
            # including identity bindings, rather than accepting a step delta.
            residual = max(abs(number(calculate(k, candidate)) - number(candidate[k])) for k in keys)
            if residual <= tolerance:
                return {k: candidate[k] for k in keys}
        raise Failure('linear_residual_failure' if plan.kind == 'linear' else 'nonconvergence')

    with localcontext(context()):
        for component in graph.components:
            keys = component.nodes
            external = [p for k in keys for p in parents[k] if p not in keys]
            if any(statuses.get(p) != 'known' for p in external):
                code = 'blocked'
            elif any(k in ambiguous_funding for k in keys):
                code = 'missing_joint_funding_procedure'
            elif any(k in missing for k in keys):
                code = 'missing_input'
            else:
                try:
                    if component.cyclic:
                        plan = solver_for.get(keys[0])
                        if plan is None:
                            raise Failure('missing_solver')
                        values.update(solve(component, plan))
                    else:
                        value = calculate(keys[0], values)
                        if value is not None:
                            values[keys[0]] = value
                    code = 'known'
                except (Failure, NumericError, DecimalException, AccountError, MechanismError) as exc:
                    code = str(exc)
            for key in keys:
                statuses[key] = code
            if code != 'known':
                diagnostics.append((keys, code))
    complete = all(s == 'known' for s in statuses.values())
    return NumericalResult(request.model_dump_json(), graph.digest, graph.model, RUNTIME_ID, tuple((k, v.model_dump_json()) for k, v in sorted(values.items())),
        tuple(sorted(statuses.items())), tuple(diagnostics),
        batch.model_dump_json() if complete and batch is not None else None, operations)
