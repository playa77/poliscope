"""Canonical host binding identity; no simulation arithmetic or activation."""
from dataclasses import asdict
from hashlib import sha256
import json
from poliscope_engine.numeric import RUNTIME_ID
from poliscope_engine.evaluation import EVALUATOR_ID

MODEL = ('authored:provisioning-economy', 'v1')


def digest(data):
    return 'sha256:' + sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def binding(request, graph, units, *, adapter="provisioning-economy-v1", model=MODEL):
    return digest(dict(adapter=adapter, model=model, numeric_runtime=RUNTIME_ID, evaluator=EVALUATOR_ID,
        request=request.model_dump(mode='json'),
        world=dict(civilization_id=graph.registry.civilization_id,
            entities=[e.model_dump(mode='json') for e in graph.registry.entities],
            scopes=[s.model_dump(mode='json') for s in graph.registry.scopes],
            values=[v.model_dump(mode='json') for v in graph.registry.values],
            owners=[asdict(o) for o in graph.registry.owners],
            populations=[asdict(p) for p in graph.registry.populations],
            relationships=[r.model_dump(mode='json') for r in graph.relationships]),
        units=[dict(id=u.id, dimension=u.dimension, kind=u.kind, scale=str(u.scale))
               for u in units.units]))


def policy_evidence(mechanisms):
    """Complete immutable declaration/review identity, never executable content."""
    return dict(model=mechanisms.model,
            definitions=[d.model_dump(mode='json') for d in mechanisms.definitions],
            graphs=[g.model_dump(mode='json') for g in mechanisms.graphs],
            reviews=[asdict(r) for r in mechanisms.reviews],
            sources=sorted(mechanisms.source_ids), assumptions=sorted(mechanisms.assumption_ids),
            fixtures=sorted(mechanisms.fixture_ids), times=[asdict(t) | {'seconds': str(t.seconds)}
                for t in mechanisms.times],
            implementations=[i.key for i in mechanisms.implementations])
