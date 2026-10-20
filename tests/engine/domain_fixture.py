"""Shared v1 conformance adapter; literal expected outputs live in shared-v1.json.

The fixture uses WP-019's finite stock/labor example and adds canonical asset and
cohort anchors. No domain model, empirical evidence or runtime capacity is inferred.
"""
import json
from decimal import Decimal
from pathlib import Path
from poliscope_engine.contracts.domains import DomainModule
from poliscope_engine.contracts.mechanisms import MechanismDefinition
from poliscope_engine.contracts.revisions import RevisionInputs
from poliscope_engine.mechanisms import MechanismRegistry, Implementation, Review, declaration_digest
from poliscope_engine.numeric import Registry, Unit, TimeBasis
from poliscope_engine.domains import DomainRegistry
from poliscope_engine.domains.conformance import ConformanceCase

PATH = Path(__file__).parents[1] / 'fixtures/domains/shared-v1.json'


def fixture():
    return json.loads(PATH.read_text())


def registry(definitions=None, callback=None, **updates):
    defs = [MechanismDefinition.model_validate(d) for d in (definitions or fixture()['definitions'])]
    def actual(port, inputs):
        return inputs['synthetic:need' if port == 'synthetic:requested' else 'synthetic:allocated']
    implementations = [Implementation(p.implementation.id, p.implementation.version, phase, callback or actual)
        for d in defs for phase in ('static', 'transition') if (p := getattr(d.support, phase)) is not None]
    args = dict(model=('synthetic:model','v1'),
        units=Registry((Unit('kg',(('mass',1),),'stock',Decimal(1)), Unit('hours',(('time',1),),'capacity',Decimal(1)))),
        times=(TimeBasis('day',Decimal(86400)),TimeBasis('day:0',Decimal(86400))),
        source_ids=['synthetic:source'], fixture_ids=[('synthetic:positive','v1'),('synthetic:domain-conformance','v1')],
        implementations=implementations, definitions=defs,
        reviews=[Review(declaration_digest(d),'synthetic:model','v1','synthetic:inspection','synthetic:integer-oracle') for d in defs])
    return MechanismRegistry(**(args | updates))


def catalog(defs=None):
    defs = registry().definitions if defs is None else defs
    modules=[]
    for domain in sorted({d.domain for d in defs}):
        selected=[d for d in defs if d.domain==domain]
        modules.append(DomainModule.model_validate(dict(contract_version=1,identity=dict(id='domain:'+domain,version='v1'),
            domain=domain, mechanisms=[dict(id=d.id,version=d.version) for d in selected],
            interfaces=[dict(id=d.id+':'+p.id,mechanism=dict(id=d.id,version=d.version),port_id=p.id,
                direction=direction,value_type=p.value_type.model_dump(),references=[dict(entity_id='stock',entity_kind='account')])
                for d in selected for direction,ports in [('input',d.inputs),('output',d.outputs)] for p in ports],
            authorities=[], transitions=[], runtime='shared_engine',persistence='shared_store',
            coverage=[dict(branch_id='synthetic:'+domain,mechanism_refs=[dict(id=d.id,version=d.version) for d in selected],
                status='partial',evidence_status='hypothetical',scope_kinds=['settlement'],static_available=True,
                transition_available=False,source_refs=['synthetic:source'],limits='Synthetic finite arithmetic only.',next_task='Real domain review remains required.') ])))
    return DomainRegistry(modules)


def case():
    data=fixture()
    expected=data['expected']
    return ConformanceCase(inputs=RevisionInputs.model_validate(data['inputs']),outcome=expected['outcome'],
        observations=tuple(dict(node=['output',i,'synthetic:supported'],status='known',
            value=dict(kind='quantity',value=value,unit_id='kg',time_basis_id=None,denominator_scope_id=None),
            source_refs=['synthetic:source'],assumption_refs=[]) for i,value in expected['outputs'].items()),
        trace_edges=tuple((('actual_consumption',i,'synthetic:claim'),('output',i,'synthetic:supported')) for i in ('a','b')),
        accounts={k:tuple(v) for k,v in expected['accounts'].items()}, claims={k:tuple(v) for k,v in expected['claims'].items()})
