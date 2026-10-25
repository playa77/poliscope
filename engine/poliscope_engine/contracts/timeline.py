"""Data-only day schedules. These contracts grant no execution or IPC authority."""
from typing import Annotated, Literal
from pydantic import Field, model_validator
from .base import Contract, Identifier
from .world import SafeCount, RevisionContext, WorldValue, References
from .policies import PolicyBinding
from .evaluation import Digest

Day = SafeCount
Interval = Annotated[int, Field(ge=1, le=9007199254740991)]


class Calendar(Contract):
    id: Literal['fixed-364-v1'] = 'fixed-364-v1'
    # Day zero opens year zero. Four 91-day seasons, 52 seven-day weeks.
    # No civil dates, leap days, time zones or inferred seasonal effects.


class MechanismSchedule(Contract):
    instance_id: Identifier
    interval_days: Interval
    first_day: Day


class BindingDelta(Contract):
    binding_id: Identifier
    scope_id: Identifier
    expected_digest: Digest | None  # None explicitly requires absence.
    replacement: PolicyBinding | None  # None removes this binding only.

    @model_validator(mode='after')
    def matching_binding(self):
        if self.replacement is not None and (
            self.replacement.id != self.binding_id or self.replacement.scope_id != self.scope_id
        ):
            raise ValueError('delta_binding_mismatch')
        if self.expected_digest is None and self.replacement is None:
            raise ValueError('empty_delta')
        return self


class AdoptionCondition(Contract):
    condition_id: Identifier
    scope_id: Identifier
    expected_digest: Digest


class PolicyAdoption(Contract):
    id: Identifier
    effective_day: Day
    order: SafeCount
    origin: Literal['player_approved']
    source_revision: RevisionContext
    base_revision: RevisionContext
    deltas: Annotated[list[BindingDelta], Field(min_length=1, max_length=100)]
    preconditions: Annotated[list[AdoptionCondition], Field(max_length=100)]
    # Unimplemented migrations/delays must remain visible, never instant effects.
    transition: Literal['binding_only', 'unsupported']
    source_refs: References


class ConditionChange(Contract):
    condition_id: Identifier
    scope_id: Identifier
    expected_digest: Digest | None
    value: WorldValue


class DatedEvent(Contract):
    id: Identifier
    effective_day: Day
    order: SafeCount
    origin: Literal['player_authored', 'external']
    changes: Annotated[list[ConditionChange], Field(min_length=1, max_length=100)]
    source_refs: References


class TimelinePlan(Contract):
    contract_version: Literal[1]
    calendar: Calendar
    opening_revision: RevisionContext
    opening_day: Day
    schedules: Annotated[list[MechanismSchedule], Field(max_length=1000)]
    events: Annotated[list[DatedEvent], Field(max_length=1000)]
    adoptions: Annotated[list[PolicyAdoption], Field(max_length=1000)]

    @model_validator(mode='after')
    def unique_entries(self):
        ids = [x.id for x in [*self.events, *self.adoptions]]
        instances = [x.instance_id for x in self.schedules]
        if len(set(ids)) != len(ids) or len(set(instances)) != len(instances):
            raise ValueError('duplicate_schedule_identity')
        if any(x.effective_day <= self.opening_day for x in [*self.events, *self.adoptions]):
            raise ValueError('past_event_requires_fork')
        for adoption in self.adoptions:
            for context in (adoption.source_revision, adoption.base_revision):
                if (context.data_store_id, context.civilization_id) != (
                    self.opening_revision.data_store_id, self.opening_revision.civilization_id
                ):
                    raise ValueError('foreign_adoption_context')
        return self


class ScheduledBoundary(Contract):
    day: Day
    mechanism_ids: Annotated[list[Identifier], Field(max_length=1000)]
    event_ids: Annotated[list[Identifier], Field(max_length=1000)]
    adoption_ids: Annotated[list[Identifier], Field(max_length=1000)]


class AdoptionOutcome(Contract):
    id: Identifier
    day: Day
    status: Literal['applied', 'conflict', 'precondition_failed', 'coverage_gap']
    affected_scope_ids: References
    reason: Identifier


class EventOutcome(Contract):
    id: Identifier
    day: Day
    status: Literal['applied', 'conflict']


class BoundaryChanges(Contract):
    day: Day
    policies: Annotated[list[PolicyBinding], Field(max_length=100)]
    events: Annotated[list[EventOutcome], Field(max_length=1000)]
    adoptions: Annotated[list[AdoptionOutcome], Field(max_length=1000)]
