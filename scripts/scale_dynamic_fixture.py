"""Frozen synthetic boundary workload, sharing the scaled static world.

Reuses the tested transition-conformance fixture builders, explicitly as synthetic
benchmark data. Every numerical transition still executes the production reducer,
finite allocator, account oracle and durable boundary validator.
"""
from pathlib import Path
import sys
from typing import get_args
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests/engine'))
import transition_fixture
from poliscope_engine.contracts.mechanisms import Domain
from poliscope_engine.contracts.revisions import RevisionInputs
from poliscope_engine.contracts.transitions import TransitionPlan, TransitionProposal
from poliscope_engine.contracts.domains import DomainModule
from poliscope_engine.domains import DomainRegistry
from poliscope_engine.mechanisms import MechanismRegistry, Review, declaration_digest
from poliscope_engine.numeric import Registry
from poliscope_engine.simulation import TransitionAdapter
from scripts.coupled_scale_fixture import fixture as static_fixture

VERSION='dec06-coupled-dynamic-v1'


def requested(day,index,disrupted):
    # Daily service, weekly finite delivery, seasonal input, annual update,
    # and response/repair with explicit disruption/repair event facts.
    if index==1:return 7 if day%7==0 else 0
    if index==2:return 91 if day%91==0 else 0
    if index==3:return 364 if day%364==0 else 0
    if index==10:return 2 if disrupted else 1
    return 1


def fixture(counts):
    host,initial,expected=static_fixture(counts)
    domains=get_args(Domain)
    callbacks={}
    for index in range(12):
        base=transition_fixture.adapter(requested='1')
        def propose(invocation,index=index):
            disrupted=any(c.condition_id=='scale:disruption' and c.value.value=='on' for c in invocation.conditions)
            return transition_fixture.adapter(requested=str(requested(invocation.day,index,disrupted))).propose(invocation)
        callbacks[chr(97+index)]=TransitionAdapter(propose,base.resolve,base.validate)
    dynamic,catalog,data,plan=transition_fixture.fixture(domains=domains,adapters=callbacks)
    mapping={e.id:'run:'+e.id for e in data.entities if e.id!='civ'}
    mapping.update({v.id:'run:'+v.id for v in data.values})
    mapping.update({chr(97+i):f'run:instance:{i}' for i in range(12)})
    mapping.update(civ='scale:civ',local=initial.scopes[0].id)
    def remap(value):
        if isinstance(value,str):return mapping.get(value,value)
        if isinstance(value,list):return [remap(v) for v in value]
        if isinstance(value,dict):return {k:(v if k in ('entity_kind','kind','role') else remap(v)) for k,v in value.items()}
        return value
    raw=initial.model_dump(mode='json')
    for collection in ['entities','values','owners']:
        raw[collection]+=remap([v.model_dump(mode='json') for v in getattr(data,collection) if not (collection=='entities' and v.id=='civ')])
    raw['design']['effective_time']=dict(tick=0,calendar_id='fixed-364-v1')
    # Dynamic production feeds the scope's dependent cross-domain chain. Every
    # day changes real static inputs; unchanged components may be reused only
    # under complete port/model identity.
    root=raw['design']['execution']['dependencies']['instances'][2]
    assert root['id']=='scale:chain:00000'
    root['entity_id']='run:service-a'
    raw['design']['world_inputs'][0]['value_id']='run:processed-a'
    # Large enough declared stocks/capacity for every scheduled day; no implicit
    # daily renewal. Independent totals below account for every finite use.
    p=remap(plan.model_dump(mode='json'))
    for account in p['opening']['batch']['accounts']:
        account['maximum']='100000'
        if account['id'] in ['run:material','run:labor']:account['opening']='10000'
    for row in raw['values']:
        row['effective_time']=dict(tick=0,calendar_id='fixed-364-v1')
        if row['id'] in ['run:balance:material','run:balance:labor']:row['value']['value']='10000'
    p['instances']=remap([i.model_dump() for i in data.design.execution.dependencies.instances])
    merged=(*host.definitions,*dynamic.definitions)
    implementations={i.key:i for i in [*host.implementations,*dynamic.implementations]}
    # Translate the synthetic proposal's resource references. Resolve/validate
    # operate on their granted canonical entities and actual allocation IDs.
    from poliscope_engine.mechanisms import Implementation
    for key,impl in list(implementations.items()):
        if impl.phase!='transition':continue
        original=impl.callback
        def translated(invocation,original=original):
            proposal=remap(original.propose(invocation).model_dump(mode='json'))
            # Explicit fixture access bound: the test helper's default of 100
            # would incorrectly cap the annual 364-unit request.
            for demand in proposal['demands']:
                demand['choice']['access_limit']='10000'
            return TransitionProposal.model_validate(proposal)
        callback=TransitionAdapter(translated,original.resolve,original.validate)
        implementations[key]=Implementation(impl.id,impl.version,impl.phase,callback)
    merged_host=MechanismRegistry(model=('scale:coupled-dynamic','v1'),
        units=Registry(tuple({u.id:u for u in [*host.units.units,*dynamic.units.units]}.values())),
        times=tuple({t.id:t for t in [*host.times,*dynamic.times]}.values()),
        source_ids=host.source_ids|dynamic.source_ids,fixture_ids=host.fixture_ids|dynamic.fixture_ids,
        definitions=merged,implementations=list(implementations.values()),
        reviews=[Review(declaration_digest(d),'scale:coupled-dynamic','v1',
            'wp051:synthetic-dynamic-inspection','wp051:integer-schedule-oracle') for d in merged])
    # Two authored policy views over the same canonical resource. Their
    # exclusive conflict remains visible; no social coefficient is inferred.
    policy_relationships=[]
    for j,authority in enumerate(['east-authority','region-authority']):
        policy_relationships.append(dict(id=raw['relationships'][-1-j]['id'],relationship_version='v1',
            relationship_kind='jurisdiction',from_id=authority,to_id=raw['scopes'][j]['id'],
            aggregation=dict(kind='non_aggregating'),provenance=dict(origin='authored',source_refs=[],assumption_refs=[])))
    raw['relationships'][-2:]=policy_relationships
    raw['design']['policies']=[dict(contract_version=1,id=f'scale:policy:{j}',
        mechanism=dict(id='synthetic:access-policy',version='v1'),scope_id=raw['scopes'][j]['id'],
        authority_id=authority,entity_ids=['water'],parameter_id='synthetic:limit',
        value=dict(kind='quantity',value='100',unit_id='kg',time_basis_id=None,denominator_scope_id=None),
        conflict_kind='parameter',account_refs=[],choice_refs=[]) for j,authority in enumerate(['east-authority','region-authority'])]
    raw['versions']['model_id']=merged_host.model[0]
    modules=DomainRegistry([DomainModule.model_validate(remap(m.model_dump(mode='json'))) for m in catalog.modules])
    return merged_host,modules,RevisionInputs.model_validate(raw),TransitionPlan.model_validate(p),expected


def oracle(day):
    # An independent integer schedule: nine daily series plus weekly/seasonal/
    # annual series and ten extra response units on days 100..109.
    amounts=[day]*12
    amounts[1]=7*(day//7);amounts[2]=91*(day//91);amounts[3]=364*(day//364)
    amounts[10]+=max(0,min(day,109)-99)
    total=sum(amounts)
    return amounts,dict(material=10000-total,labor=10000-total,product=total*7,residual=total*2)
