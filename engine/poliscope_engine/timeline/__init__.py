"""Pure scheduling and private effective-change staging, calendar fixed-364-v1.

This service neither runs domain transitions nor publishes/persists state. WP-034
consumes its boundaries and staged changes; only a coordinated confirmed boundary
may become visible. There is deliberately no aggregate-transition shortcut.
"""
from copy import deepcopy
from heapq import heappop, heappush
from typing import Callable, Iterator

from poliscope_engine.contracts.timeline import (
    Calendar, TimelinePlan, ScheduledBoundary, BoundaryChanges, AdoptionOutcome,
    EventOutcome, PolicyAdoption,
)
from poliscope_engine.contracts.revisions import RevisionRecord
from poliscope_engine.contracts.world import RevisionContext, WorldValue
from poliscope_engine.contracts.policies import PolicyBinding
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.numeric import TimeBasis, parse

CALENDAR = Calendar()
INTERVALS = {'day': 1, 'week': 7, 'season': 91, 'year': 364}
MAX_DAY = 9007199254740991
SCHEDULER_ID = 'day-boundaries-events-before-adoptions-v1'


class TimelineError(ValueError):
    pass


def day_number(day: int) -> int:
    if type(day) is not int or not 0 <= day <= MAX_DAY:
        raise TimelineError('invalid_day')
    return day


def calendar_parts(day: int) -> tuple[int, int, int, int]:
    """Zero-based (year, season within year, week within year, day within week)."""
    day_number(day)
    return day // 364, (day % 364) // 91, (day % 364) // 7, day % 7


def time_basis(period: str) -> TimeBasis:
    """Use WP-006 Registry.convert for rate conversion, with explicit scope/unit."""
    if period not in INTERVALS:
        raise TimelineError('unknown_calendar_period')
    return TimeBasis(f'{CALENDAR.id}:{period}', parse(str(86400 * INTERVALS[period])))


def schedule_digest(plan: TimelinePlan) -> str:
    """Stable semantic plan identity, independent of input collection order."""
    data = TimelinePlan.model_validate(plan.model_dump()).model_dump()
    data['schedules'].sort(key=lambda row: row['instance_id'])
    for category in ('events', 'adoptions'):
        data[category].sort(key=lambda row: (row['effective_day'], row['order'], row['id']))
    for event in data['events']:
        event['changes'].sort(key=lambda row: (row['scope_id'], row['condition_id']))
    for adoption in data['adoptions']:
        adoption['deltas'].sort(key=lambda row: row['binding_id'])
    return digest(dict(scheduler=SCHEDULER_ID, plan=data))


def boundaries(plan: TimelinePlan, target_day: int, *, after_day: int | None = None
               ) -> Iterator[ScheduledBoundary]:
    """Yield every due boundary in (after, target], bounded memory, no skipping.

    Mechanisms are ordered by stable instance ID. At each boundary, dated events
    precede adoptions; each class uses (player order, stable ID) as precedence.
    Target always appears, even when no mechanism is due. Chunk continuation must
    pass the last confirmed day, never a partially processed boundary.
    """
    plan = TimelinePlan.model_validate(plan.model_dump())
    start = plan.opening_day if after_day is None else day_number(after_day)
    day_number(target_day)
    if not plan.opening_day <= start <= target_day:
        raise TimelineError('past_target_requires_fork')
    heap = []
    for schedule in plan.schedules:
        first = schedule.first_day
        if first <= start:
            first += ((start - first) // schedule.interval_days + 1) * schedule.interval_days
        if first <= target_day:
            heappush(heap, (first, schedule.instance_id, schedule.interval_days))
    dated = {}
    for kind, entries in [('event', plan.events), ('adoption', plan.adoptions)]:
        for entry in entries:
            if start < entry.effective_day <= target_day:
                dated.setdefault(entry.effective_day, []).append((kind, entry.order, entry.id))
    days = iter(sorted({*dated, *([target_day] if target_day > start else [])}))
    pending = next(days, None)
    while heap or pending is not None:
        day = min(heap[0][0] if heap else MAX_DAY + 1,
                  pending if pending is not None else MAX_DAY + 1)
        mechanisms = []
        while heap and heap[0][0] == day:
            _, identity, interval = heappop(heap)
            mechanisms.append(identity)
            if day + interval <= target_day:
                heappush(heap, (day + interval, identity, interval))
        rows = sorted(dated.get(day, []))
        yield ScheduledBoundary(day=day, mechanism_ids=sorted(mechanisms),
            event_ids=[r[2] for r in rows if r[0] == 'event'],
            adoption_ids=[r[2] for r in rows if r[0] == 'adoption'])
        if pending == day:
            pending = next(days, None)


def _unique(rows, key, error):
    result = {key(row): row for row in rows}
    if len(result) != len(rows):
        raise TimelineError(error)
    return result


def validate_approval(adoption: PolicyAdoption,
                      read_revision: Callable[[RevisionContext], RevisionRecord]) -> None:
    """Read accepted immutable revisions through trusted Revisions.read, not input data.

    A candidate/preview is insufficient. Only explicitly selected approved policy
    bindings are eligible; other design edits and dynamic state never migrate.
    """
    base, source = (read_revision(c) for c in (adoption.base_revision, adoption.source_revision))
    for expected, actual in [(adoption.base_revision, base), (adoption.source_revision, source)]:
        # Revisions.read authorizes the requested branch; a fork may retain a
        # record originally accepted on a different branch without rewriting it.
        if (actual.context.data_store_id, actual.context.civilization_id, actual.context.revision_id) != (
            expected.data_store_id, expected.civilization_id, expected.revision_id
        ):
            raise TimelineError('approval_context_mismatch')
    if (source.context.data_store_id != base.context.data_store_id or
        source.context.civilization_id != base.context.civilization_id or
        source.parent_id != base.context.revision_id):
        raise TimelineError('approval_base_mismatch')
    old = _unique(base.inputs.design.policies, lambda b: b.id, 'duplicate_binding')
    new = _unique(source.inputs.design.policies, lambda b: b.id, 'duplicate_binding')
    _unique(adoption.deltas, lambda d: d.binding_id, 'duplicate_delta')
    _unique(adoption.preconditions, lambda c: (c.scope_id, c.condition_id), 'duplicate_precondition')
    for delta in adoption.deltas:
        previous = old.get(delta.binding_id)
        replacement = new.get(delta.binding_id)
        if (delta.expected_digest != (digest(previous) if previous is not None else None)
            or delta.replacement != replacement
            or (previous is not None and previous.scope_id != delta.scope_id)
            or (replacement is not None and replacement.scope_id != delta.scope_id)
            or previous == replacement):
            raise TimelineError('unapproved_policy_delta')


def stage_changes(plan: TimelinePlan, day: int, policies: list[PolicyBinding],
                  conditions: dict[tuple[str, str], WorldValue], *,
                  read_revision: Callable[[RevisionContext], RevisionRecord]
                  ) -> tuple[BoundaryChanges, dict[tuple[str, str], WorldValue]]:
    """Stage one due boundary. Caller supplies confirmed opening bindings/conditions.

    Each event/adoption is atomic. A failed delta cannot partly apply its siblings.
    Other same-day disjoint changes proceed. No stocks, assets or pending cases
    are accepted here, so policy adoption cannot reset them. Source revisions are
    checked even for unsupported transitions; untrusted content never grants them.
    """
    day_number(day)
    plan = TimelinePlan.model_validate(plan.model_dump())
    if day <= plan.opening_day:
        raise TimelineError('past_event_requires_fork')
    bindings = deepcopy(_unique(policies, lambda b: b.id, 'duplicate_binding'))
    facts = deepcopy(conditions)
    event_results, adoption_results = [], []
    for event in sorted((e for e in plan.events if e.effective_day == day), key=lambda e: (e.order, e.id)):
        _unique(event.changes, lambda c: (c.scope_id, c.condition_id), 'duplicate_condition_change')
        conflict = any(c.expected_digest != (
            digest(facts[(c.scope_id, c.condition_id)]) if (c.scope_id, c.condition_id) in facts else None
        ) for c in event.changes)
        if not conflict:
            for change in event.changes:
                facts[(change.scope_id, change.condition_id)] = change.value.model_copy(deep=True)
        event_results.append(EventOutcome(id=event.id, day=day, status='conflict' if conflict else 'applied'))
    for adoption in sorted((a for a in plan.adoptions if a.effective_day == day), key=lambda a: (a.order, a.id)):
        validate_approval(adoption, read_revision)
        conflict = any(d.expected_digest != (digest(bindings[d.binding_id]) if d.binding_id in bindings else None)
                       for d in adoption.deltas)
        missing = any((c.scope_id, c.condition_id) not in facts or
            facts[(c.scope_id, c.condition_id)].kind == 'unknown' or
            digest(facts[(c.scope_id, c.condition_id)]) != c.expected_digest for c in adoption.preconditions)
        if conflict:
            status, reason = 'conflict', 'stale_policy_binding'
        elif missing:
            status, reason = 'precondition_failed', 'missing_or_unsatisfied_condition'
        elif adoption.transition == 'unsupported':
            status, reason = 'coverage_gap', 'unsupported_transition_or_delay'
        else:
            status, reason = 'applied', 'binding_only_no_dynamic_effect'
            for delta in adoption.deltas:
                if delta.replacement is None:
                    bindings.pop(delta.binding_id)
                else:
                    bindings[delta.binding_id] = delta.replacement.model_copy(deep=True)
        adoption_results.append(AdoptionOutcome(id=adoption.id, day=day, status=status,
            affected_scope_ids=sorted({d.scope_id for d in adoption.deltas}), reason=reason))
    return BoundaryChanges(day=day, policies=[bindings[k] for k in sorted(bindings)],
                           events=event_results, adoptions=adoption_results), facts
