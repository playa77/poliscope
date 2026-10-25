"""Data-only, explicit probability models and stable named draw contracts."""
from typing import Annotated, Literal
from pydantic import Field, model_validator
from .base import Contract, Identifier
from .evaluation import Digest
from .world import SafeCount, References

Bound = Annotated[int, Field(ge=0, le=9007199254740991)]
Positive = Annotated[int, Field(ge=1, le=9007199254740991)]
Seed = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]


class RandomRuntime(Contract):
    # Strings permit trusted data-only historical reads of unavailable versions.
    rng: Identifier = 'hmac-sha256-counter-v1'
    key: Identifier = 'named-draw-json-v1'
    sampling: Identifier = 'exact-discrete-rejection-v1'


class Bernoulli(Contract):
    kind: Literal['bernoulli']
    numerator: Bound
    denominator: Positive

    @model_validator(mode='after')
    def probability(self):
        if self.numerator > self.denominator:
            raise ValueError('invalid_probability')
        return self


class UniformInteger(Contract):
    kind: Literal['uniform_integer']
    low: Bound
    high: Bound

    @model_validator(mode='after')
    def interval(self):
        if self.low > self.high:
            raise ValueError('invalid_integer_support')
        return self


class WeightedValue(Contract):
    value: Identifier
    weight: Positive


class Categorical(Contract):
    kind: Literal['categorical']
    outcomes: Annotated[list[WeightedValue], Field(min_length=1, max_length=100)]

    @model_validator(mode='after')
    def support(self):
        if len({o.value for o in self.outcomes}) != len(self.outcomes):
            raise ValueError('duplicate_probability_outcome')
        if sum(o.weight for o in self.outcomes) > 9007199254740991:
            raise ValueError('probability_weight_limit')
        return self


Distribution = Annotated[Bernoulli | UniformInteger | Categorical, Field(discriminator='kind')]


class DrawKey(Contract):
    mechanism_id: Identifier
    mechanism_version: Identifier
    instance_id: Identifier
    entity_id: Identifier
    scope_id: Identifier
    purpose: Identifier
    event_id: Identifier
    draw_name: Identifier
    index: SafeCount


class DrawSpec(Contract):
    variable_id: Identifier
    key: DrawKey
    day: SafeCount
    distribution: Distribution
    lifetime: Literal['event', 'persistent'] = 'event'
    source_refs: References
    # Explicit model assumption; separate keys do not establish independence.
    dependence: Literal['declared_independent', 'shared_realization']
    assumption_refs: Annotated[list[Identifier], Field(min_length=1, max_length=100)]


class DrawReference(Contract):
    instance_id: Identifier
    variable_id: Identifier


class ForkRealization(Contract):
    parent_plan_digest: Digest
    parent_seed: Seed
    policy: Literal['preserve', 'new_realization']


class RandomPlan(Contract):
    contract_version: Literal[1]
    seed: Seed
    runtime: RandomRuntime
    draws: Annotated[list[DrawSpec], Field(max_length=1000)]
    references: Annotated[list[DrawReference], Field(max_length=1000)]
    fork: ForkRealization | None = None

    @model_validator(mode='after')
    def identities(self):
        ids = [d.variable_id for d in self.draws]
        keys = [d.key.model_dump_json() for d in self.draws]
        refs = [(r.instance_id, r.variable_id) for r in self.references]
        if len(set(ids)) != len(ids) or len(set(keys)) != len(keys) or len(set(refs)) != len(refs):
            raise ValueError('duplicate_random_identity')
        if {r.variable_id for r in self.references} != set(ids):
            raise ValueError('unbound_random_variable')
        for draw in self.draws:
            consumers = {r.instance_id for r in self.references if r.variable_id == draw.variable_id}
            if draw.key.instance_id not in consumers:
                raise ValueError('random_owner_reference_required')
            if len(consumers) > 1 and draw.dependence != 'shared_realization':
                raise ValueError('shared_dependence_required')
        if self.fork is not None and ((self.seed == self.fork.parent_seed) != (self.fork.policy == 'preserve')):
            raise ValueError('fork_seed_policy_mismatch')
        return self


class RealizedDraw(Contract):
    runtime: RandomRuntime
    seed: Seed
    spec: DrawSpec
    value: Identifier
    rejected_blocks: Annotated[int, Field(ge=0, lt=128)]
    accepted_block: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
