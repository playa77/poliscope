"""Stable structural DEC-06 probes. These do not invent twelve-domain models.

Counts match the frozen manifest; executable coupled arithmetic remains a
separate acceptance requirement. All identities are synthetic and deterministic.
"""
from poliscope_engine.contracts.world import EntityDTO, ScopeDTO, RelationshipDTO
from poliscope_engine.world import WorldRegistry, PopulationDeclaration
from poliscope_engine.world.membership import WorldGraph

VERSION = 'dec06-structural-v1'
PROVENANCE = dict(origin='authored', source_refs=[], assumption_refs=[])


def structural(counts):
    entities = [EntityDTO(id='scale:civ', entity_kind='civilization', label='Synthetic scale probe', provenance=PROVENANCE)]
    for field, kind in [('cohorts', 'population_cohort'), ('assets', 'asset'), ('decision_instances', 'decision')]:
        entities.extend(EntityDTO(id=f'scale:{kind}:{i:05}', entity_kind=kind,
            label=f'Synthetic {kind} {i}; domain {i % 12 + 1}', provenance=PROVENANCE)
            for i in range(counts[field]))
    scopes = [ScopeDTO(id=f'scale:scope:{i:05}', scope_kind='settlement',
        label=f'Synthetic overlapping view {i}', provenance=PROVENANCE) for i in range(counts['scopes'])]
    rows = []
    # Every cohort belongs to two overlapping views. One canonical cohort is
    # shared; this never creates another population stock or implicit weight.
    for i in range(counts['cohorts']):
        for view in (0, 1):
            rows.append(RelationshipDTO(id=f'scale:edge:{len(rows):05}', relationship_version='v1',
                relationship_kind='cohort_membership', from_id=f'scale:population_cohort:{i:05}',
                to_id=scopes[(i + view) % len(scopes)].id,
                aggregation=dict(kind='partition', partition_id='scale:whole'), provenance=PROVENANCE))
    kinds = ['supplies', 'consumes', 'access', 'ownership', 'information_channel']
    for i in range(counts['active_typed_edges'] - len(rows)):
        rows.append(RelationshipDTO(id=f'scale:edge:{len(rows):05}', relationship_version='v1',
            relationship_kind=kinds[i % len(kinds)], from_id=entities[1 + i % (len(entities)-1)].id,
            to_id=scopes[(i * 7) % len(scopes)].id,
            aggregation=dict(kind='non_aggregating'), provenance=PROVENANCE))
    return entities, scopes, rows


def graph(counts):
    entities, scopes, rows = structural(counts)
    return WorldGraph(WorldRegistry('scale:civ', entities=entities, scopes=scopes,
        populations=[PopulationDeclaration(e.id, 'fixed_input') for e in entities
                     if e.entity_kind == 'population_cohort']), rows)
