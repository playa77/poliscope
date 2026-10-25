"""Portable stateless keyed draws; no process RNG, clock or floating arithmetic."""
import hashlib
import hmac
import json
from poliscope_engine.contracts.stochastic import RandomPlan, RandomRuntime, RealizedDraw
from poliscope_engine.evaluation.identity import digest

RUNTIME = RandomRuntime()


class RandomModelError(ValueError):
    pass


def require_runtime(runtime):
    if runtime != RUNTIME:
        raise RandomModelError('historical_random_runtime_unavailable')


def sample(seed, runtime, spec):
    """HMAC key is 32 seed bytes; message is fixed canonical UTF-8 JSON.

    Rejection removes modulo bias. Each named draw owns its local counter, so
    neither global insertion nor a rejected block shifts any other draw.
    """
    from poliscope_engine.contracts.stochastic import DrawSpec, Seed
    from pydantic import TypeAdapter
    seed = TypeAdapter(Seed).validate_python(seed, strict=True)
    runtime = RandomRuntime.model_validate_json(runtime.model_dump_json())
    spec = DrawSpec.model_validate_json(spec.model_dump_json())
    require_runtime(runtime)
    distribution = spec.distribution
    if distribution.kind == 'bernoulli':
        size = distribution.denominator
    elif distribution.kind == 'uniform_integer':
        size = distribution.high - distribution.low + 1
    else:
        size = sum(o.weight for o in distribution.outcomes)
    ceiling = (1 << 256) - ((1 << 256) % size)
    for counter in range(128):
        message = json.dumps(dict(runtime=runtime.model_dump(), key=spec.key.model_dump(), counter=counter),
                             sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        block = hmac.new(bytes.fromhex(seed), message, hashlib.sha256).digest()
        integer = int.from_bytes(block, 'big')
        if integer < ceiling:
            selected = integer % size
            if distribution.kind == 'bernoulli':
                value = 'true' if selected < distribution.numerator else 'false'
            elif distribution.kind == 'uniform_integer':
                value = str(distribution.low + selected)
            else:
                for outcome in distribution.outcomes:
                    if selected < outcome.weight:
                        value = outcome.value
                        break
                    selected -= outcome.weight
            return RealizedDraw(runtime=runtime, seed=seed, spec=spec, value=value,
                                rejected_blocks=counter, accepted_block=block.hex())
    raise RandomModelError('random_rejection_quota')


def available(spec, day):
    return spec.day == day or (spec.lifetime == 'persistent' and spec.day < day)


def realize(plan, day, *, checkpoint=None):
    plan = RandomPlan.model_validate_json(plan.model_dump_json())
    require_runtime(plan.runtime)
    result = []
    for spec in sorted(plan.draws, key=lambda d: d.variable_id):
        if available(spec, day):
            if checkpoint is not None:
                checkpoint()
            result.append(sample(plan.seed, plan.runtime, spec))
    return result


def verify_draw(draw):
    if sample(draw.seed, draw.runtime, draw.spec) != draw:
        raise RandomModelError('realized_draw_mismatch')


def validate_plan(plan, instances, timeline):
    """Bind named streams to actual mechanisms and scheduled effective events."""
    if plan is None:
        return
    plan = RandomPlan.model_validate_json(plan.model_dump_json())
    require_runtime(plan.runtime)
    instances = {i.id: i for i in instances}
    schedules = {s.instance_id: s for s in timeline.schedules}
    for draw in plan.draws:
        key = draw.key
        owner = instances.get(key.instance_id)
        if owner is None or (key.mechanism_id, key.mechanism_version, key.entity_id, key.scope_id) != (
                owner.mechanism_id, owner.mechanism_version, owner.entity_id, owner.scope_id):
            raise RandomModelError('random_instance_identity_mismatch')
        for ref in (r for r in plan.references if r.variable_id == draw.variable_id):
            schedule = schedules.get(ref.instance_id)
            if ref.instance_id not in instances or schedule is None or draw.day <= timeline.opening_day or (
                    draw.day < schedule.first_day or (draw.day - schedule.first_day) % schedule.interval_days):
                raise RandomModelError('random_reference_not_due')


def fork_plan(parent, *, policy, seed=None):
    """Record paired preservation or intentional reseeding; never mutate parent."""
    parent = RandomPlan.model_validate_json(parent.model_dump_json())
    selected = parent.seed if policy == 'preserve' and seed is None else seed
    child = RandomPlan.model_validate(parent.model_dump() | dict(seed=selected,
        fork=dict(parent_plan_digest=digest(parent), parent_seed=parent.seed, policy=policy)))
    verify_fork(parent, child)
    return child


def check_retained(plan, day, draws):
    """Data-only binding check, even when historical sampling code is unavailable."""
    expected = {} if plan is None else {d.variable_id: d for d in plan.draws if available(d, day)}
    if set(expected) != {d.spec.variable_id for d in draws} or len(expected) != len(draws):
        raise RandomModelError('retained_random_variables_mismatch')
    for draw in draws:
        if draw.spec != expected[draw.spec.variable_id] or draw.seed != plan.seed or draw.runtime != plan.runtime:
            raise RandomModelError('retained_random_model_mismatch')


def verify_fork(parent, child):
    """Bind a fork declaration to an actual parent before experiment orchestration."""
    parent = RandomPlan.model_validate_json(parent.model_dump_json())
    child = RandomPlan.model_validate_json(child.model_dump_json())
    if (child.fork is None or child.fork.parent_plan_digest != digest(parent)
            or child.fork.parent_seed != parent.seed
            or digest(child.model_dump(exclude={'seed', 'fork'})) != digest(parent.model_dump(exclude={'seed', 'fork'}))):
        raise RandomModelError('fork_random_identity_mismatch')
