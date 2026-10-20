"""Reusable authoring harness. Host code is trusted; this is not a Python sandbox."""
from copy import deepcopy
from dataclasses import dataclass
from poliscope_engine.contracts.revisions import RevisionInputs
from poliscope_engine.contracts.evaluation import EvaluationResult
from poliscope_engine.evaluation import evaluate
from poliscope_engine.world import WorldRegistry, StateOwner, PopulationDeclaration
from poliscope_engine.world.membership import WorldGraph
from . import ConformanceError


@dataclass(frozen=True)
class ConformanceCase:
    """Expected results must be independently authored, not produced by this harness.

    Observations are exact selected node assertions including status/value/provenance;
    account and claim expectations are complete sets when supplied.
    """
    inputs: RevisionInputs
    outcome: str
    observations: tuple[dict, ...]
    accounts: dict[str, tuple[str, str, str]] | None = None
    claims: dict[str, tuple[str, str]] | None = None
    trace_edges: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = ()


def run_case(case, *, catalog, mechanisms, branch_ids):
    case = deepcopy(case)
    data = RevisionInputs.model_validate_json(case.inputs.model_dump_json())
    civs = [e.id for e in data.entities if e.entity_kind == 'civilization']
    if len(civs) != 1:
        raise ConformanceError('fixture_requires_one_civilization')
    world = WorldRegistry(civs[0], entities=data.entities, scopes=data.scopes, values=data.values,
        owners=[StateOwner(**o.model_dump()) for o in data.owners],
        populations=[PopulationDeclaration(**p.model_dump()) for p in data.populations])
    graph = WorldGraph(world, data.relationships)
    catalog.validate(world=world, mechanisms=mechanisms, branch_ids=branch_ids)
    listed = {(m.id, m.version) for d in catalog.modules for m in d.mechanisms}
    for i in data.design.execution.dependencies.instances:
        if (i.mechanism_id, i.mechanism_version) not in listed:
            raise ConformanceError('unlisted_instance')
    before = (world.entities, world.scopes, world.values, world.owners, graph.relationships,
              data.model_dump_json(), tuple(d.model_dump_json() for d in mechanisms.definitions))
    result = evaluate(graph, data.design, data.assumptions, mechanisms.model, registry=mechanisms)
    repeat = evaluate(graph, data.design, data.assumptions, mechanisms.model, registry=mechanisms)
    after = (world.entities, world.scopes, world.values, world.owners, graph.relationships,
             data.model_dump_json(), tuple(d.model_dump_json() for d in mechanisms.definitions))
    if before != after or result != repeat:
        raise ConformanceError('impure_evaluation')
    if result.outcome != case.outcome:
        raise ConformanceError('unexpected_outcome')
    observations = {tuple(o.node): o.model_dump(mode='json') for o in result.observations}
    for expected in case.observations:
        actual = observations.get(tuple(expected['node']))
        if actual is None or any(actual.get(key) != value for key, value in expected.items()):
            raise ConformanceError('unexpected_observation')
    if case.accounts is not None:
        actual = None if result.accounts is None else {
            a.account_id: (a.closing, a.outstanding_reserved, a.available) for a in result.accounts.accounts}
        if actual != case.accounts:
            raise ConformanceError('unexpected_accounts')
    if case.claims is not None:
        actual = None if result.accounts is None else {
            c.claim_id: (c.actual, c.unmet) for c in result.accounts.claims}
        if actual != case.claims:
            raise ConformanceError('unexpected_claims')
    edges = {(tuple(e.source), tuple(e.target)) for e in result.trace_edges}
    if not set(case.trace_edges) <= edges:
        raise ConformanceError('missing_trace_edge')
    if any(a not in observations or b not in observations for a, b in edges):
        raise ConformanceError('dangling_trace')
    return EvaluationResult.model_validate_json(result.model_dump_json())


def stage_transition(*, catalog, mechanisms, world, module_domain, mechanism,
                     entity_id, scope_id, changes):
    """Pure proposal hook only; no transition scheduling or durable publication."""
    catalog.validate(world=world, mechanisms=mechanisms,
                     branch_ids=[c.branch_id for m in catalog.modules for c in m.coverage])
    module = next((m for m in catalog.modules if m.domain == module_domain), None)
    hook = None if module is None else next((h for h in module.transitions if
        (h.mechanism.id, h.mechanism.version) == mechanism and h.entity_id == entity_id and
        h.scope_id == scope_id and h.status == 'proposal_only'), None)
    if hook is None:
        raise ConformanceError('unavailable_transition')
    changes = tuple(changes)
    if any(c.property_id not in hook.property_refs for c in changes):
        raise ConformanceError('undeclared_transition_write')
    return mechanisms.stage_changes(*mechanism, world=world, entity_id=entity_id,
                                   scope_id=scope_id, changes=changes)
