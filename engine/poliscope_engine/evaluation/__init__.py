"""Pure static orchestration. Host-owned in-memory caching is a separate wrapper."""
from dataclasses import asdict
from collections import deque
import sys
import decimal
import pydantic
from pydantic import TypeAdapter
from poliscope_engine.contracts.evaluation import (
    EvaluationDesign, AssumptionValue, EvaluationResult, EvaluationIdentities,
    NodeObservation, TraceEdge)
from poliscope_engine.contracts.dependencies import FixedInput
from poliscope_engine.contracts.world import WorldValue
from poliscope_engine.contracts.accounts import AccountBatch
from poliscope_engine.accounts import AccountBook
from poliscope_engine.dependencies import compile_dependencies
from poliscope_engine.dependencies.solvers import execute
from poliscope_engine.numeric import RUNTIME_ID, parse
from poliscope_engine.policies import resolve
from .identity import serialized, digest
from .conditions import validate_conditions

# v3 permits retained denied time claims to fund a subsequent allocation phase.
EVALUATOR_ID = 'pure-static-v3'
PYTHON_RUNTIME = tuple(sys.version_info[:3])
VALUE = TypeAdapter(WorldValue)


class EvaluationError(ValueError):
    """Structural invalidity; successful insufficiency is an EvaluationResult."""


def index(rows):
    result = {r.id: r for r in rows}
    if len(result) != len(rows):
        raise EvaluationError('duplicate_identity')
    return result


def _prepare(world, design, assumptions, model_identity, registry):
    # Normalize the actual execution snapshots as well as their identities.
    design = EvaluationDesign.model_validate_json(serialized(design))
    assumptions = tuple(AssumptionValue.model_validate_json(serialized(a)) for a in assumptions)
    if len(assumptions) > 1000:
        raise EvaluationError('assumption_limit')
    assumptions = tuple(sorted(assumptions, key=lambda a: a.id))
    if tuple(model_identity) != registry.model:
        raise EvaluationError('model_identity_mismatch')
    world_values = index(world.registry.values)
    from poliscope_engine.contracts.mechanisms import QuantityType
    for row in world_values.values():
        if row.value.kind == 'quantity':
            registry._type(QuantityType(**row.value.model_dump(exclude={'value'})), world.registry)
    assumption_values = index(assumptions)
    realization_values = index(design.realization.values)
    if len(set(design.realization.event_ids)) != len(design.realization.event_ids):
        raise EvaluationError('duplicate_event_identity')
    policies = resolve(design.policies, graph=world, mechanisms=registry, rules=design.policy_rules)
    policy_results = {(r.entity_id, r.parameter_id): r for r in policies.results}
    execution = design.execution
    instances = {i.id: i for i in execution.dependencies.instances}
    # Every external input has exactly one authority; compile also rejects overlap
    # with numerical/account bindings. A conflict cannot override a fixed value.
    fixed = list(execution.dependencies.fixed_inputs)
    occupied = {(f.consumer.instance_id, f.consumer.port_id) for f in fixed}
    overrides = []

    def supply(consumer, value, status=None):
        key = consumer.instance_id, consumer.port_id
        if key in occupied:
            raise EvaluationError('multiple_input_producers')
        occupied.add(key)
        if status is not None:
            overrides.append((('input', *key), status))
            value = VALUE.validate_python(dict(kind='unknown', reason=status))
        fixed.append(FixedInput(consumer=consumer, value=value))

    for rows, available in ((design.world_inputs, world_values),
                            (design.assumption_inputs, assumption_values),
                            (design.realization_inputs, realization_values)):
        for binding in rows:
            if binding.value_id not in available:
                raise EvaluationError('missing_value_reference')
            value = available[binding.value_id]
            if rows is design.world_inputs:
                instance = instances.get(binding.consumer.instance_id)
                if instance is None or (value.entity_id, value.scope_id) != (instance.entity_id, instance.scope_id):
                    raise EvaluationError('world_input_context_mismatch')
                definition = registry.definition(instance.mechanism_id, instance.mechanism_version)
                if value.partition not in definition.read_partitions:
                    raise EvaluationError('undeclared_partition_read')
            supply(binding.consumer, value.value)
    for binding in design.policy_inputs:
        instance = instances.get(binding.consumer.instance_id)
        if instance is None or instance.entity_id != binding.entity_id:
            raise EvaluationError('policy_target_mismatch')
        if binding.consumer.port_id != binding.parameter_id:
            raise EvaluationError('policy_parameter_mismatch')
        result = policy_results.get((binding.entity_id, binding.parameter_id))
        if result is None:
            supply(binding.consumer, None, 'missing_input')
        elif result.status != 'known':
            supply(binding.consumer, None, result.status)
        else:
            value = getattr(result, binding.selection)
            supply(binding.consumer, value, 'missing_input' if value is None else None)
    dependencies = execution.dependencies.model_copy(update={'fixed_inputs': fixed})
    execution = type(execution).model_validate_json(serialized(execution.model_copy(update={'dependencies': dependencies})))
    compile_dependencies(execution.dependencies, registry, world.registry)
    validate_conditions(design.conditions, execution.dependencies, registry, world.registry)
    if execution.batch is not None:
        scopes = {s.id for s in world.registry.scopes}
        account_entities = {e.id for e in world.registry.entities if e.entity_kind == 'account'}
        if any(a.id not in account_entities for a in execution.batch.accounts):
            raise EvaluationError('unknown_account_identity')
        if any(a.scope_id not in scopes for a in execution.batch.accounts):
            raise EvaluationError('unknown_account_scope')
        if any(a.period_id is not None and a.period_id not in {t.id for t in registry.times}
               for a in execution.batch.accounts):
            raise EvaluationError('unknown_account_period')
        entities = {e.id for e in world.registry.entities}
        if any(c.claimant_id not in entities for c in execution.batch.claims):
            raise EvaluationError('unknown_claimant')
        AccountBook(execution.batch, registry.units).evaluate()
    world_snapshot = dict(civilization_id=world.registry.civilization_id,
        entities=world.registry.entities, scopes=world.registry.scopes,
        values=world.registry.values, owners=world.registry.owners,
        populations=world.registry.populations, relationships=world.relationships)
    input_data = dict(world=world_snapshot, design=design.model_dump(mode='json', exclude={'realization'}),
                      assumptions=assumptions)
    model_data = dict(identity=registry.model, evaluator=EVALUATOR_ID, numeric=RUNTIME_ID,
        python=PYTHON_RUNTIME, decimal_library=decimal.__libmpdec_version__,
        pydantic=pydantic.__version__, definitions=registry.definitions, graphs=registry.graphs,
        reviews=[asdict(r) for r in registry.reviews],
        implementations=[dict(id=i.id, version=i.version, phase=i.phase) for i in registry.implementations],
        units=registry.units.units, times=registry.times, source_ids=registry.source_ids,
        assumption_ids=registry.assumption_ids, fixture_ids=registry.fixture_ids)
    identity = dict(canonical_version=1, input_digest=digest(input_data),
        model_digest=digest(model_data), realization_digest=digest(design.realization))
    identity['cache_key'] = digest(identity)
    return design, execution, policies, tuple(overrides), input_data, model_data, identity


def _status(code):
    if code in ('known', 'conflict', 'missing_input', 'not_applicable', 'unmodeled'):
        return code
    if code in ('blocked', 'precondition_evaluation_required'):
        return 'missing_input'
    if code.startswith('allocation_unresolved') or code in ('missing_solver', 'missing_joint_funding_procedure'):
        return 'conflict'
    return 'solver_failure'


def _run(prepared, world, registry):
    design, execution, policies, overrides, input_data, model_data, identity = prepared
    numerical = execute(execution, registry, world.registry, conditions=design.conditions,
                        input_statuses=overrides)
    values = {key: VALUE.validate_json(value) for key, value in numerical.values}
    instances = {i.id: i for i in execution.dependencies.instances}
    definitions = {i.id: registry.definition(i.mechanism_id, i.mechanism_version) for i in instances.values()}
    # Each node can advance only a few coverage levels; no quadratic rescans.
    coverage = {k: _status(code) for k, code in numerical.statuses}
    codes = dict(numerical.statuses)
    for key in coverage:
        if key[0] in ('input', 'output', 'claim', 'actual_consumption') and coverage[key] == 'known' and definitions[key[1]].modeling == 'partial':
            coverage[key] = 'partial'
    children = {key: [] for key in coverage}
    for source, target in numerical.edges:
        children[source].append(target)
    rank = {'unmodeled': 1, 'solver_failure': 2, 'conflict': 3}
    pending = deque(coverage)
    while pending:
        source = pending.popleft()
        status = coverage[source]
        for target in children[source]:
            if (codes[target] == 'blocked' and status in rank and
                    rank[status] > rank.get(coverage[target], 0) or
                    codes[target] == 'known' and status == 'partial' and coverage[target] == 'known'):
                coverage[target] = status
                pending.append(target)
    observations = []
    for key, code in numerical.statuses:
        instance = instances.get(key[1]) if key[0] in ('input', 'output', 'claim', 'actual_consumption') else None
        definition = definitions[instance.id] if instance else None
        status = coverage[key]
        observations.append(NodeObservation(node=list(key), scope_id=instance.scope_id if instance else None,
            entity_id=instance.entity_id if instance else None, status=status, reason=code,
            value=values.get(key), source_refs=definition.source_refs if definition else [],
            assumption_refs=definition.assumption_refs if definition else []))
    final_batch = AccountBatch.model_validate_json(numerical.batch_json) if numerical.batch_json else None
    accounts = AccountBook(final_batch, registry.units).evaluate() if final_batch else None
    statuses = {o.status for o in observations} | {r.status for r in policies.results}
    outcome = ('unresolved' if statuses & {'conflict', 'solver_failure'} else
               'incomplete' if statuses & {'missing_input', 'partial', 'unmodeled'} else
               'insufficient' if accounts and any(parse(c.unmet) > 0 for c in accounts.claims) else 'complete')
    payload = dict(contract_version=1, effective_time=design.effective_time,
        outcome=outcome, observations=observations, policies=policies, accounts=accounts,
        trace_edges=[TraceEdge(source=list(a), target=list(b)) for a, b in numerical.edges],
        final_batch_json=serialized(final_batch) if final_batch else None,
        input_json=serialized(input_data), model_json=serialized(model_data),
        realization_json=serialized(design.realization))
    identity = identity | {'output_digest': digest(payload)}
    result = EvaluationResult(identities=EvaluationIdentities(**identity), **payload)
    return EvaluationResult.model_validate_json(serialized(result))


def evaluate(world, design, assumptions, model_identity, *, registry):
    """No mutation, persistence, providers, wall clock, sampling or implicit input.

    `world` is a WorldGraph; `registry` is trusted versioned host code. Imported
    rules cannot become host rules by calling this internal Python API.
    """
    return _run(_prepare(world, design, assumptions, model_identity, registry), world, registry)


class EvaluationCache:
    """Bounded host-local optimization, never a cache of accepted evidence.

    Results are stored as immutable bytes and returned detached. Registry object
    identity additionally isolates callback objects whose host violated version
    discipline. Complete manifests still participate in the portable cache key.
    There is no API to import arbitrary persisted entries as trusted results.
    """
    def __init__(self, capacity=16):
        if type(capacity) is not int or not 1 <= capacity <= 1000:
            raise EvaluationError('invalid_cache_capacity')
        self.capacity = capacity
        self._entries = {}

    def evaluate(self, world, design, assumptions, model_identity, *, registry):
        prepared = _prepare(world, design, assumptions, model_identity, registry)
        key = prepared[-1]['cache_key']
        entry = self._entries.get(key)
        if entry is not None and entry[0] is registry:
            result = EvaluationResult.model_validate_json(entry[1])
            payload = result.model_dump(mode='json', exclude={'identities'})
            if result.identities.output_digest == digest(payload):
                return result
        result = _run(prepared, world, registry)
        if key not in self._entries and len(self._entries) >= self.capacity:
            del self._entries[next(iter(self._entries))]
        self._entries[key] = registry, result.model_dump_json()
        return result
