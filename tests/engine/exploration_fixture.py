"""Synthetic canonical topology for packaged keyboard acceptance."""
from pathlib import Path
import sys
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from poliscope_engine.workspace import starting_inputs, registry, PROVENANCE, TIME
from poliscope_engine.contracts.revisions import RevisionInputs, CreateRequest


def seed(directory):
    raw = starting_inputs(dict(name='World exploration',setup='blank',scope_name='Home',population='12',land_area='3'), 'civ').model_dump(mode='json')
    raw['entities'] += [dict(id=i,entity_kind=k,label=label,provenance=PROVENANCE) for i,k,label in [
        ('clinic','asset','Shared clinic'), ('council-a','institution','Local council'),
        ('council-b','institution','Care council'), ('care-network','network','Care network')]]
    raw['relationships'] = [dict(id=i,relationship_kind=k,from_id=a,to_id=b,relationship_version='v1',
        aggregation=dict(kind='non_aggregating'),provenance=PROVENANCE) for i,k,a,b in [
        ('authority-a','jurisdiction','council-a','clinic'),('authority-b','jurisdiction','council-b','clinic'),
        ('clinic-place','containment','clinic','home'),('clinic-network','connectivity','clinic','care-network'),
        ('clinic-land','access','clinic','land')]]
    with Store(Path(directory)) as store:
        service=Revisions(store,registry=registry())
        return service.create(CreateRequest(revision_contract=1,data_store_id=service.data_store_id,
            civilization_id='civ',branch_id='main',name='World exploration',operation_id='seed',inputs=RevisionInputs.model_validate(raw)))

if __name__ == '__main__': seed(sys.argv[1])
