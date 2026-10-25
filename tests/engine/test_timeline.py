"""Synthetic calendar/adoption fixtures, with independent day and balance oracles."""
from copy import deepcopy
from fractions import Fraction
from itertools import permutations

import pytest
from pydantic import ValidationError

from poliscope_engine.contracts.timeline import TimelinePlan, PolicyAdoption
from poliscope_engine.contracts.world import RevisionContext, LabelValue, UnknownValue
from poliscope_engine.contracts.revisions import PreviewRequest, ApplyRequest, BranchRequest
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.numeric import Registry, Unit, Quantity, parse
from poliscope_engine.revisions import Revisions
from poliscope_engine.storage import Store
from poliscope_engine.timeline import (
    boundaries, stage_changes, calendar_parts, time_basis, TimelineError, validate_approval, schedule_digest,
)
from test_policies import binding, definition as policy_definition
from test_mechanism_registry import registry, PROVENANCE
from test_revisions import inputs, create_request, mechanism_registry, value

CONTEXT = dict(data_store_id='store', civilization_id='civ', branch_id='main', revision_id='opening')
YES = LabelValue(kind='label', value='approved')


def plan(**updates):
    return TimelinePlan.model_validate(dict(contract_version=1, calendar={}, opening_revision=CONTEXT,
        opening_day=0, schedules=[], events=[], adoptions=[]) | updates)


def event(identity='condition', day=7, order=0, expected=None, value=None):
    return dict(id=identity, effective_day=day, order=order, origin='external', source_refs=['synthetic:event'],
        changes=[dict(condition_id='institutional-outcome', scope_id='local', expected_digest=expected,
                      value=value or YES)])


@pytest.fixture
def approved(tmp_path):
    """Produce real accepted parent/child revisions, not preview-shaped approval data."""
    with Store(tmp_path) as store:
        base_registry = mechanism_registry()
        defs = [*base_registry.definitions, policy_definition()]
        policy_host = registry([defs[-1]])
        host = registry(defs, implementations=(*base_registry.implementations, *policy_host.implementations))
        service = Revisions(store, registry=host)
        opening = inputs().model_dump()
        opening['entities'].append(dict(id='local-authority', entity_kind='institution',
            label='Synthetic authority', provenance=PROVENANCE))
        for prop, amount in [('stock', '37'), ('accumulated-assets', '3'), ('pending-cases', '1')]:
            opening['values'].append(value(amount).model_copy(update={
                'id': prop, 'property_id': prop, 'partition': 'dynamic_state'}).model_dump())
            opening['owners'].append(dict(entity_id='supply', property_id=prop,
                partition='dynamic_state', writer_id='synthetic:transition'))
        first = binding('policy-a', entity_ids=['supply'], choice_refs=[])
        second = binding('policy-b', entity_ids=['supply'], parameter_id='synthetic:parameter', choice_refs=[])
        # Separate policies are retained even when their static result is a conflict.
        opening['design']['policies'] = [first.model_dump(), second.model_dump()]
        created = service.create(create_request(service, inputs=opening))
        revised = deepcopy(opening)
        # The approved design carries different opening state, which adoption
        # must never copy into the running experiment.
        for row in revised['values']:
            if row['partition'] == 'dynamic_state':
                row['value']['value'] = '999'
        for b in revised['design']['policies']:
            b['value']['value'] = '9'
        preview = PreviewRequest.model_validate(dict(revision_contract=1, context=created.context,
            changes=[dict(kind='replace_inputs', inputs=revised)],
            decision=dict(alternatives=[], selected_id=None, rationale_ref=None)))
        candidate = service.preview(preview)
        applied = service.apply(ApplyRequest(revision_contract=1, preview=preview,
            candidate_digest=candidate.candidate_digest, operation_id='approve-policies'))
        base, source = service.read(created.context), service.read(applied.context)
        yield service, base, source


def adoption(base, source, identity='adopt-a', ids=('policy-a',), **updates):
    old = {b.id: b for b in base.inputs.design.policies}
    new = {b.id: b for b in source.inputs.design.policies}
    return PolicyAdoption.model_validate(dict(id=identity, effective_day=7, order=0,
        origin='player_approved', base_revision=base.context, source_revision=source.context,
        deltas=[dict(binding_id=i, scope_id='local', expected_digest=digest(old[i]), replacement=new[i]) for i in ids],
        preconditions=[], transition='binding_only', source_refs=['synthetic:approval']) | updates)


def test_year_fast_forward_keeps_daily_shortage_and_all_multirate_boundaries():
    p = plan(schedules=[dict(instance_id=i, first_day=n, interval_days=n)
        for i, n in [('daily', 1), ('weekly', 7), ('seasonal', 91), ('annual', 364)]])
    rows = list(boundaries(p, 364))
    assert [r.day for r in rows] == list(range(1, 365))
    for name, interval in [('weekly', 7), ('seasonal', 91), ('annual', 364)]:
        assert [r.day for r in rows if name in r.mechanism_ids] == list(range(interval, 365, interval))
    # Synthetic daily service has two units, consumes one/day, replenishes weekly.
    # Independently expected first failure is day 3, despite a yearly display.
    stock, shortages = Fraction(2), []
    for row in rows:
        if 'weekly' in row.mechanism_ids:
            stock += 7
        if stock < 1:
            shortages.append(row.day)
        else:
            stock -= 1
    assert shortages[:4] == [3, 4, 5, 6]
    assert list(boundaries(p, 364, after_day=180)) == rows[180:]


def test_calendar_and_rates_use_existing_exact_unit_registry():
    assert calendar_parts(0) == (0, 0, 0, 0)
    assert calendar_parts(91) == (0, 1, 13, 0)
    assert calendar_parts(364) == (1, 0, 0, 0)
    units = Registry((Unit('water-rate', (('volume', 1),), 'flow', parse('1')),))
    daily = Quantity(parse('2'), 'water-rate', 'local', time_basis('day'))
    assert units.convert(daily, 'water-rate', time_basis=time_basis('year')).value == parse('728')
    for bad in [-1, True, 1.5, 9007199254740992]:
        with pytest.raises(TimelineError):
            calendar_parts(bad)
    with pytest.raises(TimelineError):
        time_basis('gregorian-year')


def test_sparse_target_opening_and_huge_horizon_are_lazy():
    p = plan(schedules=[dict(instance_id='annual', first_day=0, interval_days=364)])
    iterator = boundaries(p, 9007199254740991)
    assert next(iterator).day == 364
    assert next(iterator).day == 728
    assert list(boundaries(plan(), 10))[0].day == 10
    assert list(boundaries(plan(), 0)) == []
    assert [r.day for r in boundaries(p, 365)] == [364, 365]
    with pytest.raises(TimelineError):
        list(boundaries(p, 2, after_day=3))


def test_disjoint_approved_deltas_compose_and_conflict_is_atomic(approved):
    service, base, source = approved
    a = adoption(base, source)
    b = adoption(base, source, 'adopt-b', ('policy-b',))
    conflict = adoption(base, source, 'adopt-z', ('policy-a', 'policy-b'), order=1)
    opening = base.inputs.design.policies
    frozen = digest(base)
    for order in permutations([a, b, conflict]):
        p = plan(opening_revision=base.context, adoptions=list(order))
        result, facts = stage_changes(p, 7, opening, {}, read_revision=service.read)
        assert [r.status for r in result.adoptions] == ['applied', 'applied', 'conflict']
        assert result.policies == source.inputs.design.policies
        assert facts == {}
    assert digest(base) == frozen
    # Applying the multi-delta adoption after only A also leaves B unchanged.
    only_a, _ = stage_changes(plan(opening_revision=base.context, adoptions=[a]), 7,
                              opening, {}, read_revision=service.read)
    failed, _ = stage_changes(plan(opening_revision=base.context, adoptions=[conflict]), 7,
                              only_a.policies, {}, read_revision=service.read)
    assert failed.policies == only_a.policies
    assert failed.adoptions[0].status == 'conflict'


def test_future_policy_preserves_past_dynamic_inputs_and_pending_cases(approved):
    service, base, source = approved
    a = adoption(base, source)
    p = plan(opening_revision=base.context, adoptions=[a])
    opening = base.inputs.model_dump()
    old, _ = stage_changes(p, 6, base.inputs.design.policies, {}, read_revision=service.read)
    assert old.policies == base.inputs.design.policies
    new, _ = stage_changes(p, 7, old.policies, {}, read_revision=service.read)
    assert new.policies[0] == source.inputs.design.policies[0]
    assert new.policies[1] == base.inputs.design.policies[1]
    assert service.read(base.context).inputs.model_dump() == opening
    # Caller composes just the policy slice; every unrelated field is preserved.
    staged = deepcopy(opening)
    staged['design']['policies'] = [b.model_dump() for b in new.policies]
    assert staged['values'] == opening['values']
    assert staged['values'] != source.inputs.model_dump()['values']
    assert {k: v for k, v in staged.items() if k != 'design'} == {
        k: v for k, v in opening.items() if k != 'design'}


def test_same_day_event_can_satisfy_only_an_already_approved_precondition(approved):
    service, base, source = approved
    a = adoption(base, source, preconditions=[dict(condition_id='institutional-outcome',
        scope_id='local', expected_digest=digest(YES))])
    p = plan(opening_revision=base.context, events=[event()], adoptions=[a])
    result, facts = stage_changes(p, 7, base.inputs.design.policies, {}, read_revision=service.read)
    assert result.adoptions[0].status == 'applied'
    assert facts == {('local', 'institutional-outcome'): YES}
    blocked, _ = stage_changes(p.model_copy(update={'events': []}), 7,
        base.inputs.design.policies, {}, read_revision=service.read)
    assert blocked.adoptions[0].status == 'precondition_failed'
    # An institutional event alone cannot create a policy adoption.
    event_only, _ = stage_changes(plan(events=[event()]), 7,
        base.inputs.design.policies, {}, read_revision=service.read)
    assert event_only.policies == base.inputs.design.policies


def test_event_replay_precedence_conflicts_and_input_permutations(approved):
    service, base, _ = approved
    second = event('second', expected=digest(YES), order=1, value=LabelValue(kind='label', value='later'))
    conflicting = event('third', order=2)
    reference = None
    identity = None
    for order in permutations([event(), second, conflicting]):
        p = plan(events=list(order))
        if identity is None:
            identity = schedule_digest(p)
        assert schedule_digest(p) == identity
        b = list(boundaries(p, 7))[0]
        assert b.event_ids == ['condition', 'second', 'third']
        result = stage_changes(p, 7, base.inputs.design.policies, {}, read_revision=service.read)
        assert [r.status for r in result[0].events] == ['applied', 'applied', 'conflict']
        assert result == reference if reference else True
        reference = result


def test_condition_event_is_atomic_and_scope_specific(approved):
    service, base, _ = approved
    data = event()
    data['changes'].append(dict(condition_id='already-set', scope_id='local', expected_digest=None, value=YES))
    facts = {('local', 'already-set'): YES, ('elsewhere', 'institutional-outcome'): YES}
    result, staged = stage_changes(plan(events=[data]), 7, base.inputs.design.policies,
                                  facts, read_revision=service.read)
    assert result.events[0].status == 'conflict'
    assert staged == facts
    assert ('local', 'institutional-outcome') not in staged


def test_create_and_remove_only_explicitly_approved_bindings(approved):
    service, _, base = approved
    revised = base.inputs.model_dump()
    retained = revised['design']['policies'][0]
    added = deepcopy(retained)
    added['id'] = 'policy-c'
    revised['design']['policies'] = [retained, added]
    preview = PreviewRequest.model_validate(dict(revision_contract=1, context=base.context,
        changes=[dict(kind='replace_inputs', inputs=revised)],
        decision=dict(alternatives=[], selected_id=None, rationale_ref=None)))
    candidate = service.preview(preview)
    accepted = service.apply(ApplyRequest(revision_contract=1, preview=preview,
        candidate_digest=candidate.candidate_digest, operation_id='approve-remove-and-add'))
    source = service.read(accepted.context)
    removed = base.inputs.design.policies[1]
    a = adoption(base, source, ids=(), deltas=[
        dict(binding_id='policy-b', scope_id='local', expected_digest=digest(removed), replacement=None),
        dict(binding_id='policy-c', scope_id='local', expected_digest=None, replacement=added)])
    # Reopened historical reads need no executable model or callback.
    reader = Revisions(service.store, registry=None)
    result, _ = stage_changes(plan(opening_revision=base.context, adoptions=[a]), 7,
        base.inputs.design.policies, {}, read_revision=reader.read)
    assert [b.id for b in result.policies] == ['policy-a', 'policy-c']
    assert result.policies == source.inputs.design.policies


def test_foreign_context_and_unknown_fields_cannot_enter_schedule(approved):
    _, base, source = approved
    a = adoption(base, source).model_dump()
    a['source_revision']['civilization_id'] = 'foreign'
    with pytest.raises(ValidationError, match='foreign_adoption_context'):
        plan(opening_revision=base.context, adoptions=[a])
    with pytest.raises(ValidationError):
        plan(events=[event() | {'policies': []}])


def test_retrospective_fork_preserves_original_approval_and_history(approved):
    service, base, source = approved
    forked = service.change_branch(BranchRequest(revision_contract=1, context=source.context,
        expected_sequence=1, operation_id='fork-past', action='fork',
        target_revision_id=base.context.revision_id, new_branch_id='counterfactual', name='Counterfactual'))
    assert service.read(forked.context).context == base.context
    a = adoption(base, source, base_revision=forked.context)
    # The fork authorizes reading a retained record whose original branch is main.
    validate_approval(a, service.read)
    with pytest.raises(ValidationError, match='past_event_requires_fork'):
        plan(opening_revision=forked.context, opening_day=10, adoptions=[a])
    assert service.read(base.context) == base


def test_unknown_precondition_and_unsupported_delay_remain_unapplied(approved):
    service, base, source = approved
    unknown = UnknownValue(kind='unknown', reason='not measured')
    a = adoption(base, source, preconditions=[dict(condition_id='outcome', scope_id='local',
        expected_digest=digest(unknown))])
    result, _ = stage_changes(plan(opening_revision=base.context, adoptions=[a]), 7,
        base.inputs.design.policies, {('local', 'outcome'): unknown}, read_revision=service.read)
    assert result.adoptions[0].status == 'precondition_failed'
    gap = adoption(base, source, transition='unsupported')
    result, _ = stage_changes(plan(opening_revision=base.context, adoptions=[gap]), 7,
        base.inputs.design.policies, {}, read_revision=service.read)
    assert result.adoptions[0].status == 'coverage_gap'
    assert result.policies == base.inputs.design.policies


@pytest.mark.parametrize('mutation', ['digest', 'replacement', 'context', 'scope', 'duplicate'])
def test_unapproved_or_forged_delta_is_rejected(approved, mutation):
    service, base, source = approved
    data = adoption(base, source).model_dump()
    if mutation == 'digest':
        data['deltas'][0]['expected_digest'] = digest('wrong')
    elif mutation == 'replacement':
        data['deltas'][0]['replacement']['value']['value'] = '999'
    elif mutation == 'context':
        data['base_revision']['revision_id'] = source.context.revision_id
    elif mutation == 'scope':
        data['deltas'][0]['scope_id'] = 'foreign'
        data['deltas'][0]['replacement']['scope_id'] = 'foreign'
    else:
        data['deltas'] *= 2
    with pytest.raises((TimelineError, ValidationError)):
        validate_approval(PolicyAdoption.model_validate(data), service.read)


@pytest.mark.parametrize('updates', [dict(opening_day=7, events=[event()]),
    dict(events=[event(), event()]), dict(schedules=[dict(instance_id='a', first_day=0, interval_days=0)]),
    dict(calendar={'id': 'gregorian'}), dict(opening_day=True)])
def test_invalid_or_retrospective_schedule_is_rejected(updates):
    with pytest.raises(ValidationError):
        plan(**updates)
