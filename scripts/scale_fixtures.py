"""Stable structural DEC-06 probes. These do not invent twelve-domain models.

Counts match the frozen manifest; executable coupled arithmetic remains a
separate acceptance requirement. All identities are synthetic and deterministic.
"""
from poliscope_engine.contracts.world import EntityDTO, ScopeDTO, RelationshipDTO
from poliscope_engine.world import WorldRegistry, PopulationDeclaration
from poliscope_engine.world.membership import WorldGraph


def history_fixture():
    """Fifty dependent exact increments: 100 semantic trace nodes per revision.

    The independent oracle is output(step i) = revision input + i + 1.
    This is a history/trace workload, not the coupled twelve-domain DEC-06 world.
    All data crosses ordinary validation, evaluation and retained-evidence APIs.
    """
    from decimal import Decimal, localcontext
    import json
    from pathlib import Path
    from poliscope_engine.contracts.mechanisms import MechanismDefinition
    from poliscope_engine.contracts.revisions import RevisionInputs
    from poliscope_engine.mechanisms import MechanismRegistry, Implementation, Review, declaration_digest
    from poliscope_engine.numeric import Registry, Unit, RUNTIME_ID, parse, canonical, context

    qtype = dict(kind='quantity', unit_id='kg', time_basis_id=None, denominator_scope_id=None)
    declaration = json.loads((Path(__file__).resolve().parents[1] / 'contracts/mechanism-fixtures.json').read_text())[0]
    declaration.update(id='scale:history-step', source_refs=[], traces=[],
        inputs=[dict(id='scale:in', value_type=qtype, required=True, missing_behavior='propagate')],
        outputs=[dict(id='scale:out', value_type=qtype, input_refs=['scale:in'], missing_behavior='propagate')])
    definition = MechanismDefinition.model_validate(declaration)
    identity = definition.support.static.implementation

    def increment(port, values):
        with localcontext(context()):
            return dict(qtype, value=canonical(parse(values['scale:in'].value) + Decimal(1)))

    host = MechanismRegistry(model=('scale:history', 'v1'),
        units=Registry((Unit('kg', (('mass', 1),), 'stock', Decimal(1)),)),
        fixture_ids=[('synthetic:positive', 'v1')],
        implementations=[Implementation(identity.id, identity.version, 'static', increment)],
        reviews=[Review(declaration_digest(definition), 'scale:history', 'v1',
            'wp051:history-declaration-inspection', 'wp051:history-integer-oracle')], definitions=[definition])
    ids = [f'scale:step:{i:02}' for i in range(50)]
    dependencies = dict(contract_version=1, instances=[dict(id=i, mechanism_id=definition.id,
        mechanism_version=definition.version, scope_id='scale:home', entity_id='scale:resource') for i in ids],
        bindings=[dict(producer=dict(instance_id=a, port_id='scale:out'),
            consumer=dict(instance_id=b, port_id='scale:in')) for a, b in zip(ids, ids[1:])],
        fixed_inputs=[], claims=[], account_producers=[], relationships=[])
    inputs = RevisionInputs.model_validate(dict(versions=dict(world_schema=1,
        catalog_id='scale:history', model_id=host.model[0], numeric_runtime_id=RUNTIME_ID),
        entities=[dict(id=i, entity_kind=k, label='Synthetic history ' + i, provenance=PROVENANCE)
            for i, k in [('scale:civ', 'civilization'), ('scale:resource', 'resource')]],
        scopes=[dict(id='scale:home', scope_kind='settlement', label='Synthetic history scope', provenance=PROVENANCE)],
        values=[dict(id='scale:input', entity_id='scale:resource', scope_id='scale:home', partition='conditions',
            property_id='scale:amount', value=dict(qtype, value='0'),
            effective_time=dict(tick=0, calendar_id='scale:calendar'), provenance=PROVENANCE)],
        owners=[dict(entity_id='scale:resource', property_id='scale:amount', partition='conditions', writer_id='scale:writer')],
        populations=[], relationships=[], assumptions=[], measurements=[], goals=[], references=[],
        design=dict(contract_version=1, effective_time=dict(tick=0, calendar_id='scale:calendar'),
            execution=dict(contract_version=1, dependencies=dependencies, batch=None, claims=[],
                allocations=[], solvers=[], operation_limit=100000),
            policies=[], policy_rules=[], policy_inputs=[], assumption_inputs=[], realization_inputs=[], conditions=[],
            world_inputs=[dict(consumer=dict(instance_id=ids[0], port_id='scale:in'), value_id='scale:input')],
            realization=dict(identity=dict(id='scale:history-realization', version='v1'), seed=None, event_ids=[], values=[]))))
    return host, inputs

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
