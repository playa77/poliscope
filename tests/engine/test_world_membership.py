"""Synthetic watershed, political region and cross-settlement care views."""
import pytest
from poliscope_engine.contracts.world import RelationshipDTO
from poliscope_engine.world import WorldError
from poliscope_engine.world.membership import WorldGraph
from test_world_registry import registry, scope, value, PROVENANCE


def edge(identity, source='asset', target='watershed', kind='access', rule=None):
    return RelationshipDTO(id=identity, relationship_version='v1', relationship_kind=kind,
                           from_id=source, to_id=target,
                           aggregation=rule or dict(kind='partition', partition_id='whole'),
                           provenance=PROVENANCE)


def world(**changes):
    return registry(scopes=[scope(), scope('watershed'), scope('political'), scope('care')], **changes)


def aggregate(graph, scopes=('watershed', 'political')):
    return graph.aggregate(scopes, property_id='water', partition='dynamic_state')


def test_overlapping_views_do_not_duplicate_canonical_water_stock():
    graph = WorldGraph(world(), [edge('a'), edge('b', target='political'), edge('c', target='care')])
    assert aggregate(graph).value == '10'
    assert aggregate(graph, ('watershed', 'political', 'care', 'care')).value == '10'
    assert len(graph.related('asset')) == 3
    assert len(graph.registry.values) == 1


def test_adjacency_matches_full_scan_order_filters_and_detached_self_edges():
    from copy import deepcopy
    from poliscope_engine.evaluation.identity import digest
    rows = [edge('a'), edge('self', source='asset', target='asset', kind='connectivity',
            rule=dict(kind='non_aggregating')), edge('b', target='political')]
    graph = WorldGraph(world(), rows)
    assert digest(graph) == digest(dict(registry=graph.registry, _relationships=graph._relationships))
    assert deepcopy(graph) == graph
    for identity in ['asset', 'watershed', 'political', 'care']:
        for kind in [None, 'access', 'connectivity', 'supplies']:
            expected = tuple(r for r in graph.relationships if identity in (r.from_id, r.to_id)
                and (kind is None or r.relationship_kind == kind))
            assert graph.related(identity, kind=kind) == expected
    assert [r.id for r in graph.related('asset')].count('self') == 1
    graph.related('asset')[0].provenance.source_refs.append('untrusted:mutation')
    assert graph.related('asset')[0].provenance.source_refs == []
    replacement = graph.with_relationships(rows[:1])
    assert [r.id for r in replacement.related('asset')] == ['a']
    assert len(graph.related('asset')) == 3
    with pytest.raises(WorldError, match='missing_reference'):
        graph.related('unknown')


def test_explicit_disjoint_weights_and_exact_fractional_sum():
    graph = WorldGraph(world(), [edge('a', rule=dict(kind='weight', weight='0.25')),
                                edge('b', target='political', rule=dict(kind='weight', weight='0.75'))])
    assert aggregate(graph).value == '10'
    assert aggregate(graph, ('watershed',)).value == '2.5'


@pytest.mark.parametrize('weight', ['0', '-0.1', '1.1'])
def test_invalid_weights(weight):
    with pytest.raises(WorldError, match='invalid_membership_weight'):
        WorldGraph(world(), [edge('a', rule=dict(kind='weight', weight=weight))])


@pytest.mark.parametrize('rules,code', [
    ([dict(kind='weight', weight='0.6')]*2, 'membership_overallocated'),
    ([dict(kind='partition', partition_id='whole'), dict(kind='weight', weight='0.1')], 'ambiguous_membership'),
    ([dict(kind='partition', partition_id='one'), dict(kind='partition', partition_id='two')], 'ambiguous_membership'),
])
def test_ambiguous_or_overallocated_union_rejected(rules, code):
    graph = WorldGraph(world(), [edge('a', rule=rules[0]), edge('b', target='political', rule=rules[1])])
    with pytest.raises(WorldError, match=code):
        aggregate(graph)


@pytest.mark.parametrize('kind', ['containment', 'jurisdiction', 'connectivity'])
def test_only_containment_cycles_fail(kind):
    rows = [edge('a', 'watershed', 'political', kind, dict(kind='non_aggregating')),
            edge('b', 'political', 'watershed', kind, dict(kind='non_aggregating'))]
    if kind == 'containment':
        with pytest.raises(WorldError, match='containment_cycle'):
            WorldGraph(world(), rows)
    else:
        assert len(WorldGraph(world(), rows).relationships) == 2


@pytest.mark.parametrize('rows,code', [
    ([edge('a', source='absent')], 'missing_reference'),
    ([edge('asset')], 'duplicate_identity'),
    ([edge('a'), edge('a')], 'duplicate_identity'),
    ([edge('a'), edge('b')], 'duplicate_membership'),
    ([edge('a', kind='cohort_membership')], 'invalid_membership_endpoints'),
    ([edge('a', source='local')], 'invalid_membership_endpoints'),
])
def test_invalid_relationships(rows, code):
    with pytest.raises(WorldError, match=code):
        WorldGraph(world(), rows)


def test_pure_candidate_and_detached_queries():
    original = edge('a')
    graph = WorldGraph(world(), [original])
    original.provenance.source_refs.append('edit')
    graph.relationships[0].provenance.source_refs.append('edit')
    with pytest.raises(WorldError):
        graph.with_relationships([edge('bad', source='missing')])
    assert graph.relationships[0].provenance.source_refs == []
    assert len(graph.with_relationships([]).relationships) == 0
    assert len(graph.relationships) == 1


@pytest.mark.parametrize('values', [[], [value(amount='10', value=dict(kind='unknown', reason='unmeasured'))]])
def test_missing_and_unknown_never_become_zero(values):
    assert aggregate(WorldGraph(world(values=values), [edge('a')])).kind == 'unknown'


def test_empty_membership_is_unknown_and_missing_scope_fails():
    graph = WorldGraph(world())
    assert aggregate(graph).kind == 'unknown'
    with pytest.raises(WorldError, match='invalid_aggregation_scopes'):
        aggregate(graph, ('absent',))


def test_cross_settlement_care_cohort_is_one_population():
    from test_world_registry import entity
    from poliscope_engine.world import PopulationDeclaration, StateOwner
    base = world(entities=[entity(), entity('people', 'population_cohort')],
                 populations=[PopulationDeclaration('people', 'fixed_input')],
                 owners=[StateOwner('people', 'water', 'dynamic_state', 'population')],
                 values=[value(entity_id='people', amount='24')])
    graph = WorldGraph(base, [edge('a', source='people', kind='cohort_membership'),
                             edge('b', source='people', target='care', kind='cohort_membership')])
    assert aggregate(graph, ('watershed', 'care')).value == '24'


@pytest.mark.parametrize('field,changed', [('unit_id', 'kg'), ('time_basis_id', 'year'),
                                        ('denominator_scope_id', 'local')])
def test_incompatible_quantity_metadata_fails(field, changed):
    from test_world_registry import entity
    from poliscope_engine.world import StateOwner
    second = value('second', entity_id='other')
    data = second.model_dump()
    data['value'][field] = changed
    second = type(second).model_validate(data)
    base = world(entities=[entity(), entity('asset', 'asset'), entity('other', 'asset')],
                 owners=[StateOwner(e, 'water', 'dynamic_state', 'water') for e in ('asset', 'other')],
                 values=[value(), second])
    graph = WorldGraph(base, [edge('a'), edge('b', source='other', target='political')])
    with pytest.raises(WorldError, match='incompatible_aggregation'):
        aggregate(graph)
