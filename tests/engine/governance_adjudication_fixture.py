"""Versioned real-adapter fixture; quantities are independently authored JSON."""
from decimal import Decimal
import json
from pathlib import Path
from poliscope_engine.contracts.governance_adjudication import GovernanceAdjudicationRequest
from poliscope_engine.contracts.revisions import RevisionInputs
from poliscope_engine.domains.governance.adjudication_counterpart import (
    MODEL, definitions, host_registry, binding, CONTEXT, policy_registry,
)
from poliscope_engine.mechanisms import Review, declaration_digest
from poliscope_engine.numeric import Registry, Unit
from poliscope_engine.world import WorldRegistry, StateOwner, PopulationDeclaration
from poliscope_engine.world.membership import WorldGraph

PATH = Path(__file__).parents[1] / 'fixtures/domains/governance-adjudication-v1.json'


def fixture():
    return json.loads(PATH.read_text())


def setup(data=None):
    data = fixture() if data is None else data
    request = GovernanceAdjudicationRequest.model_validate(data['request'])
    inputs = RevisionInputs.model_validate(data['inputs'])
    world = WorldRegistry('civ', entities=inputs.entities, scopes=inputs.scopes,
        values=inputs.values, owners=[StateOwner(**o.model_dump()) for o in inputs.owners],
        populations=[PopulationDeclaration(**p.model_dump()) for p in inputs.populations])
    graph = WorldGraph(world, inputs.relationships)
    units = Registry(tuple(Unit(u['id'], tuple(map(tuple, u['dimension'])),
        u['kind'], Decimal(u['scale'])) for u in data['units']))
    return request, inputs, graph, units


def trusted(request, inputs, graph, units):
    # Author's mechanical SV disposition and independent arithmetic derivation;
    # this is explicitly not a nonauthor or scientific review.
    reviews = [Review(declaration_digest(d), *MODEL,
        'sv:WP-032-counterparts-governance-adjudication',
        'oracle:governance-adjudication-literal-v1') for d in definitions()]
    registry = host_registry(request, graph=graph, units=units, reviews=reviews)
    data = inputs.model_dump()
    data['design']['execution']['dependencies']['fixed_inputs'] = [dict(
        consumer=dict(instance_id='work', port_id=CONTEXT),
        value=dict(kind='label', value=binding(request, graph, units, policy_registry(units=units, reviews=registry.reviews))))]
    return registry, RevisionInputs.model_validate(data)
