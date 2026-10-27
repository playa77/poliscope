"""The optimization must retain v1 bytes, including its compatibility exceptions."""
from dataclasses import dataclass
from decimal import Decimal
import json
from pathlib import Path
import random
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from poliscope_engine.evaluation.identity import serialized,normalize,encode
from poliscope_engine.evaluation.canonical import clear
from poliscope_engine.evaluation import evaluate
from poliscope_engine.measurements import observe
from poliscope_engine.explanation import retain
from poliscope_engine.revisions import graph
from scripts.coupled_scale_fixture import fixture


def assert_reference(value):
    try:expected=encode(normalize(value))
    except Exception as error:
        with pytest.raises(type(error)):serialized(value)
    else:assert serialized(value)==expected


def test_full_physical_inputs_results_and_closure_keep_exact_v1_bytes():
    host,data,_=fixture(dict(scopes=4,cohorts=4,assets=4,decision_instances=16,active_typed_edges=401))
    world=graph(data,'scale:civ')
    result=evaluate(world,data.design,(),host.model,registry=host)
    evidence=retain(result,observe(result),data.references)
    for item in [data,world,world.registry,result,evidence,*host.definitions]:
        assert_reference(item)
        assert_reference(item)
    original=serialized(data)
    data.entities[0].provenance.source_refs.append('changed:source')
    assert serialized(data)!=original
    assert_reference(data)
    clear();assert_reference(data)


def test_json_mode_and_plain_tuple_compatibility_rules_cannot_alias_in_cache():
    for drawings in [[],(),[]]:
        value={'values':[{'transition_contract':1,'random_draws':drawings,'value':str(i)} for i in range(10)]}
        assert_reference(value)
    assert_reference({'aggregation':'same_scope','procedure':'difference',
        'inputs':[{'node':['z','a'],'scope_id':'s'},{'node':['a','z'],'scope_id':'s'}]})
    assert_reference({'carry_priority':'existing_first','instance_order':[],'random_plan':None})


def test_time_independent_memo_still_binds_time_and_every_trace_member():
    host,data,_=fixture(dict(scopes=4,cohorts=4,assets=4,decision_instances=16,active_typed_edges=24))
    result=evaluate(graph(data,'scale:civ'),data.design,(),host.model,registry=host)
    report=observe(result)
    for item in [data.design,report.traces[0]]:
        first=serialized(item)
        later=item.model_copy(update={'effective_time':item.effective_time.model_copy(update={'tick':42})})
        assert serialized(later)!=first
        assert_reference(later)
    changed=report.traces[0].model_copy(deep=True)
    changed.members[0].source_refs.append('changed:source')
    assert_reference(changed)
    assert serialized(changed)!=serialized(report.traces[0])


def test_corrupt_observation_cache_is_recomputed_before_its_proof_is_reused(monkeypatch):
    import poliscope_engine.measurements as measurements
    from poliscope_engine.evaluation.canonical import Memo
    cache=Memo(16*1024*1024,entries=8)
    monkeypatch.setattr(measurements,'_observations',cache)
    host,data,_=fixture(dict(scopes=4,cohorts=4,assets=4,decision_instances=16,active_typed_edges=24))
    result=evaluate(graph(data,'scale:civ'),data.design,(),host.model,registry=host)
    expected=observe(result)
    key=next(iter(cache.values))
    entry,size=cache.values[key]
    cache.values[key]=((b'{"corrupt":true}',entry[1]),size)
    assert observe(result)==expected


def test_deterministic_nested_corpus_matches_reference_or_same_error():
    rng=random.Random(51051)
    names=['id','values','inputs','nodes','quantity','value','constant','random_draws','source_refs','kind']
    scalars=[None,True,False,0,7,'1.00','-0','λ','a/b',Decimal('1.20')]
    def tree(depth):
        if depth==0:return rng.choice(scalars)
        choice=rng.randrange(4)
        if choice==0:return rng.choice(scalars)
        if choice==1:return [tree(depth-1) for _ in range(rng.randrange(4))]
        if choice==2:return tuple(tree(depth-1) for _ in range(rng.randrange(4)))
        return {key:tree(depth-1) for key in rng.sample(names,rng.randrange(5))}
    for _ in range(500):assert_reference(tree(4))
