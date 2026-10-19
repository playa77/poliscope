"""Synthetic institutional fixtures; expectations do not derive from resolver code."""
from itertools import permutations
import pytest
from pydantic import ValidationError

from poliscope_engine.contracts.mechanisms import MechanismDefinition
from poliscope_engine.contracts.policies import PolicyBinding, ResolutionRule
from poliscope_engine.contracts.world import EntityDTO, ScopeDTO, RelationshipDTO
from poliscope_engine.mechanisms import Implementation, MechanismError
from poliscope_engine.policies import resolve, PolicyError
from poliscope_engine.world import WorldRegistry
from poliscope_engine.world.membership import WorldGraph
from test_mechanism_registry import definitions, registry, PROVENANCE

IDENTITY = dict(id='synthetic:composition', version='v1')
QUANTITY = dict(kind='quantity', unit_id='kg', time_basis_id=None, denominator_scope_id=None)


def quantity(number):
    return dict(**QUANTITY, value=number)


def definition(identity='synthetic:policy', semantics='exclusive', value_type=None):
    data = definitions()[0].model_dump()
    data.update(id=identity, scope_kinds=['settlement', 'region'],
        entity_kinds=['resource', 'account'],
        inputs=[dict(id='synthetic:parameter', value_type=value_type or QUANTITY,
                     required=True, missing_behavior='propagate')],
        policy=dict(semantics=semantics, composition_rule=None if semantics == 'exclusive' else IDENTITY))
    data['support']['static']['implementation']['id'] = identity + '-implementation'
    return MechanismDefinition.model_validate(data)


def edge(identity, source, target, kind='jurisdiction', aggregate=False):
    return RelationshipDTO(id=identity, relationship_version='v1', relationship_kind=kind,
        from_id=source, to_id=target, provenance=PROVENANCE,
        aggregation=dict(kind='partition', partition_id='whole') if aggregate else dict(kind='non_aggregating'))


def graph(edges=None):
    entities = [EntityDTO(id=i, entity_kind=k, label=i, provenance=PROVENANCE) for i, k in
                [('civ', 'civilization'), ('water', 'resource'), ('food', 'resource'),
                 ('account', 'account'), ('choice', 'decision'), ('local-authority', 'institution'),
                 ('regional-authority', 'institution')]]
    scopes = [ScopeDTO(id=i, scope_kind=k, label=i, provenance=PROVENANCE) for i, k in
              [('local', 'settlement'), ('region', 'region')]]
    if edges is None:
        edges = [edge('local-j', 'local-authority', 'local'),
                 edge('regional-j', 'regional-authority', 'region'),
                 edge('member-l', 'water', 'local', 'access', True),
                 edge('member-r', 'water', 'region', 'access', True)]
    return WorldGraph(WorldRegistry('civ', entities=entities, scopes=scopes), edges)


def mechanisms(defs=None, **updates):
    defs = defs or [definition()]
    base = registry(defs)
    return registry(defs, implementations=(*base.implementations,
        Implementation(**IDENTITY, phase='composition', callback=lambda: pytest.fail('must not run'))), **updates)


def binding(identity='a', **updates):
    data = dict(contract_version=1, id=identity, mechanism=dict(id='synthetic:policy', version='v1'), scope_id='local',
                authority_id='local-authority', entity_ids=[], parameter_id='synthetic:parameter',
                value=quantity('2'), conflict_kind='parameter', account_refs=['account'], choice_refs=['choice'])
    return PolicyBinding.model_validate(data | updates)


def rule(participants=('a', 'b'), **updates):
    data = dict(contract_version=1, identity=IDENTITY, authority_id='regional-authority', scope_id='region',
        entity_id='water', parameter_id='synthetic:parameter', participant_ids=list(participants),
        operation='select', selected_id='b', source_refs=['synthetic:source'])
    return ResolutionRule.model_validate(data | updates)


def run(bindings=None, defs=None, rules=(), **updates):
    return resolve(bindings or [binding()], graph=updates.pop('graph', graph()),
                   mechanisms=updates.pop('mechanisms', mechanisms(defs)), rules=rules, **updates)


def overlap():
    return [binding(), binding('b', scope_id='region', authority_id='regional-authority', value=quantity('7'))]


def test_single_policy_and_direct_membership():
    result = run().results[0]
    assert (result.entity_id, result.status, result.value.value) == ('water', 'known', '2')
    assert result.source_refs == ['synthetic:source']


def test_explicit_entities_do_not_require_aggregation_and_do_not_roll_up():
    result = run([binding(entity_ids=['food'])]).results[0]
    assert result.entity_id == 'food'
    assert run(graph=graph([edge('contain', 'water', 'local', 'containment')])).not_applicable_ids == ['a']


def test_overlap_is_unresolved_with_inspectable_impact_and_sources():
    result = run(overlap()).results[0]
    assert result.status == 'conflict' and result.value is None
    finding = result.findings[0]
    assert finding.participant_ids == ['a', 'b']
    assert finding.authority_ids == ['local-authority', 'regional-authority']
    assert finding.scope_ids == ['local', 'region']
    assert finding.account_refs == ['account'] and finding.choice_refs == ['choice']
    assert finding.source_refs == ['synthetic:source'] and finding.requirements


def test_explicit_resolution_and_every_input_permutation():
    expected = None
    for bindings in permutations(overlap()):
        for edges in (graph().relationships, tuple(reversed(graph().relationships))):
            result = run(bindings, rules=[rule()], graph=graph(edges))
            assert result.results[0].value.value == '7'
            assert result.results[0].rule.authority_id == 'regional-authority'
            assert result.results[0].rule.scope_id == 'region'
            if expected is None:
                expected = result.model_dump()
            assert result.model_dump() == expected


def test_independent_results_survive_conflicts():
    results = run([*overlap(), binding('c', entity_ids=['food'])]).results
    assert [(r.entity_id, r.status) for r in results] == [('food', 'known'), ('water', 'conflict')]


def test_allocation_precedence_is_a_typed_institutional_finding():
    rows = [b.model_copy(update={'conflict_kind': 'allocation'}) for b in overlap()]
    assert 'unresolved_allocation' in [f.kind for f in run(rows).results[0].findings]


def test_missing_jurisdiction_never_infers_from_containment():
    result = run(graph=graph([edge('c', 'local-authority', 'local', 'containment'),
                              edge('m', 'water', 'local', 'access', True)])).results[0]
    assert result.status == 'conflict'
    assert result.findings[0].kind == 'authority_conflict'


def test_direct_entity_jurisdiction_and_cycles_need_no_numerical_solver():
    edges = [edge('j', 'local-authority', 'water'), edge('back', 'water', 'local-authority'),
             edge('m', 'water', 'local', 'access', True)]
    assert run(graph=graph(edges)).results[0].status == 'known'


def test_rule_cannot_resolve_a_larger_participant_set():
    result = run([*overlap(), binding('c')], rules=[rule()]).results[0]
    assert result.status == 'conflict' and result.rule is None


@pytest.mark.parametrize('updates,code', [
    (dict(authority_id='water'), 'invalid_authority'),
    (dict(scope_id='missing'), 'missing_reference'),
    (dict(entity_id='missing'), 'missing_reference'),
    (dict(participant_ids=['a', 'missing'], selected_id='a'), 'missing_rule_participant'),
    (dict(source_refs=['missing']), 'unresolved_source'),
    (dict(authority_id='local-authority'), 'unauthorized_resolution_rule'),
])
def test_invalid_host_rule_rejected(updates, code):
    with pytest.raises(PolicyError, match=code):
        run(overlap(), rules=[rule(**updates)])


@pytest.mark.parametrize('updates,code', [
    (dict(scope_id='missing'), 'missing_reference'),
    (dict(entity_ids=['missing']), 'missing_reference'),
    (dict(authority_id='water'), 'invalid_authority'),
    (dict(account_refs=['water']), 'invalid_affected_reference'),
    (dict(choice_refs=['account']), 'invalid_affected_reference'),
    (dict(parameter_id='missing'), 'undeclared_parameter'),
])
def test_invalid_bindings_rejected(updates, code):
    with pytest.raises(PolicyError, match=code):
        run([binding(**updates)])


def test_unknown_propagation_and_selected_known_alternative():
    rows = overlap()
    rows[0] = binding(value=dict(kind='unknown', reason='not measured'))
    assert run(rows, rules=[rule()]).results[0].value.value == '7'
    result = run([rows[0]]).results[0]
    assert result.status == 'missing_input' and result.value is None


def test_composable_exact_sum_and_no_callback_or_stock_mutation():
    defs = [definition(semantics='composable')]
    rows = [binding(value=quantity('0.1')), binding('b', scope_id='region',
            authority_id='regional-authority', value=quantity('0.2'))]
    g = graph()
    result = run(rows, defs, [rule(operation='sum', selected_id=None)], graph=g).results[0]
    assert result.value.value == '0.3' and g.registry.values == ()


@pytest.mark.parametrize('floor,ceiling,status', [('3', '9', 'known'), ('9', '3', 'conflict'), ('3', '3', 'known')])
def test_floor_ceiling_interval_is_not_an_automatic_policy_choice(floor, ceiling, status):
    defs = [definition('synthetic:floor', 'floor'), definition('synthetic:ceiling', 'ceiling')]
    rows = [binding(mechanism=dict(id='synthetic:floor', version='v1'), value=quantity(floor)),
            binding('b', mechanism=dict(id='synthetic:ceiling', version='v1'), scope_id='region',
                    authority_id='regional-authority', value=quantity(ceiling))]
    result = run(rows, defs, [rule(operation='bounds', selected_id=None)]).results[0]
    assert result.status == status and result.value is None
    if status == 'known':
        assert (result.floor.value, result.ceiling.value) == (floor, ceiling)
    else:
        assert result.floor is None and result.ceiling is None
        assert result.findings[0].kind == 'incompatible_bounds'


@pytest.mark.parametrize('semantics', ['composable', 'floor', 'ceiling', 'delegated'])
def test_nonexclusive_singleton_requires_declared_rule(semantics):
    assert run(defs=[definition(semantics=semantics)]).results[0].status == 'conflict'


def test_delegation_selects_explicit_policy_and_missing_delegation_is_unresolved():
    assert run(overlap(), [definition(semantics='delegated')], [rule()]).results[0].value.value == '7'
    assert run(overlap(), [definition(semantics='delegated')]).results[0].value is None


def test_incompatible_operation_never_overrides_mechanism_semantics():
    result = run(overlap(), rules=[rule(operation='sum', selected_id=None)]).results[0]
    assert result.status == 'conflict'


def test_multiple_rules_are_conflict_not_first_rule_wins():
    rules = [rule(), rule(identity=dict(id='other', version='v1'), selected_id='a')]
    for ordered in permutations(rules):
        result = run(overlap(), rules=ordered).results[0]
        assert result.status == 'conflict' and result.rule is None
        assert 'resolution_conflict' in [f.kind for f in result.findings]


def test_composition_identity_must_match_declaration():
    result = run(overlap(), [definition(semantics='delegated')],
                 [rule(identity=dict(id='other', version='v1'))]).results[0]
    assert result.status == 'conflict'


@pytest.mark.parametrize('value', [quantity('1e9999'), dict(kind='label', value='wrong')])
def test_bad_values_rejected_before_resolution(value):
    with pytest.raises(ValueError):
        run([binding(value=value)])


def test_unreviewed_mechanism_cannot_activate_policy():
    with pytest.raises(MechanismError, match='review_required'):
        run(mechanisms=mechanisms(reviews=[]))


def test_duplicate_policy_and_rule_identities_rejected():
    with pytest.raises(PolicyError, match='duplicate_identity'):
        run([binding(), binding()])
    with pytest.raises(PolicyError, match='duplicate_identity'):
        run(overlap(), rules=[rule(), rule()])


def test_untrusted_extra_execution_and_bad_selection_rejected():
    with pytest.raises(ValidationError):
        PolicyBinding.model_validate(binding().model_dump() | {'code': 'import os'})
    with pytest.raises(ValidationError):
        rule(selected_id='missing')


def test_results_and_inputs_are_detached():
    rows = overlap()
    original = rows[1].model_dump()
    result = run(rows, rules=[rule()])
    with pytest.raises(ValidationError):
        result.results[0].value.value = '99'
    result.results[0].participant_ids.clear()
    assert rows[1].model_dump() == original
    assert run(rows, rules=[rule()]).results[0].value.value == '7'


def test_overlapping_membership_union_applies_each_binding_once():
    edges = [*graph().relationships, edge('member-duplicate', 'food', 'local', 'access', True),
             edge('food-region', 'food', 'region', 'access', True)]
    results = run(overlap(), graph=graph(edges)).results
    assert len(results) == 2
    assert all(r.participant_ids == ['a', 'b'] and r.status == 'conflict' for r in results)


def test_no_implicit_jurisdiction_inheritance():
    edges = [edge('j', 'local-authority', 'regional-authority'),
             edge('j2', 'regional-authority', 'local'),
             edge('m', 'water', 'local', 'access', True)]
    assert run(graph=graph(edges)).results[0].findings[0].kind == 'authority_conflict'


def test_unsupported_scope_class_fails_closed():
    d = definition().model_copy(update={'scope_kinds': ['settlement']})
    with pytest.raises(PolicyError, match='unsupported_scope'):
        run(overlap(), [d])


def test_types_cannot_be_chosen_by_a_precedence_rule():
    defs = [definition(), definition('synthetic:label', value_type=dict(kind='label'))]
    rows = [binding(), binding('b', scope_id='region', authority_id='regional-authority',
            mechanism=dict(id='synthetic:label', version='v1'), value=dict(kind='label', value='public'))]
    result = run(rows, defs, [rule()]).results[0]
    assert result.status == 'conflict' and result.value is None


def test_bound_rule_rejects_label_comparison_and_composable_unknown_is_not_zero():
    d = definition(semantics='floor', value_type=dict(kind='label'))
    result = run([binding(value=dict(kind='label', value='x'))], [d],
        [rule(('a',), scope_id='local', authority_id='local-authority', operation='bounds', selected_id=None)]).results[0]
    assert result.status == 'conflict'
    rows = [binding(value=dict(kind='unknown', reason='not measured')), overlap()[1]]
    result = run(rows, [definition(semantics='composable')],
                 [rule(operation='sum', selected_id=None)]).results[0]
    assert result.status == 'missing_input' and result.value is None


def test_single_floor_explicit_rule_returns_only_a_constraint():
    result = run(defs=[definition(semantics='floor')], rules=[rule(('a',), scope_id='local',
        authority_id='local-authority', operation='bounds', selected_id=None)]).results[0]
    assert result.status == 'known' and result.value is None
    assert result.floor.value == '2' and result.ceiling is None


def test_rule_for_different_scope_or_parameter_does_not_apply():
    for changes in (dict(parameter_id='other'), dict(scope_id='local', authority_id='local-authority')):
        rows = overlap() if 'parameter_id' in changes else [overlap()[1]]
        r = rule() if 'parameter_id' in changes else rule(('b',), selected_id='b')
        result = run(rows, rules=[r.model_copy(update=changes)]).results[0]
        assert result.rule is None


def test_empty_snapshot_and_size_limits():
    assert resolve([], graph=graph(), mechanisms=mechanisms()).results == []
    with pytest.raises(PolicyError, match='policy_limit'):
        run([binding(f'p{i}') for i in range(101)])


def test_binding_definition_must_declare_policy_semantics():
    d = definition().model_copy(update={'policy': None})
    with pytest.raises(PolicyError, match='missing_policy_declaration'):
        run(defs=[d])


def test_transition_policy_uses_transition_review_gate_and_remains_pure():
    data = definition().model_dump()
    data['support']['transition'] = data['support']['static']
    data['support']['static'] = None
    d = MechanismDefinition.model_validate(data)
    assert run(defs=[d], phase='transition').results[0].status == 'known'
    with pytest.raises(MechanismError, match='unsupported_phase'):
        run(defs=[d])
    with pytest.raises(PolicyError, match='invalid_phase'):
        run(phase='invalid')


def test_many_mismatched_declarations_return_one_bounded_finding():
    rows = [binding(f'p{i}') for i in range(100)]
    r = rule(tuple(b.id for b in rows), scope_id='local', authority_id='local-authority',
             identity=dict(id='other', version='v1'), selected_id='p0')
    result = run(rows, [definition(semantics='delegated')], [r]).results[0]
    assert result.status == 'conflict' and len(result.findings) == 1
