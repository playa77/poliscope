"""Literal twelve-domain fixture, with one canonical finite work book."""
import json
from decimal import Decimal
from pathlib import Path
from poliscope_engine.contracts.static_system import StaticSystemRequest
from poliscope_engine.contracts.world import EntityDTO, ScopeDTO, PartitionValueDTO, RelationshipDTO
from poliscope_engine.numeric import Registry, Unit, TimeBasis
from poliscope_engine.world import WorldRegistry, StateOwner, PopulationDeclaration
from poliscope_engine.world.membership import WorldGraph
from test_policies import mechanisms

PATH = Path(__file__).parents[1] / 'fixtures/domains/static-system-v1.json'


def fixture():
    return json.loads(PATH.read_text())


def setup(data=None):
    data = fixture() if data is None else data
    w = data['world']
    world = WorldRegistry(w['civilization_id'],
        entities=list(map(EntityDTO.model_validate, w['entities'])),
        scopes=list(map(ScopeDTO.model_validate, w['scopes'])),
        values=list(map(PartitionValueDTO.model_validate, w['values'])),
        owners=[StateOwner(**o) for o in w['owners']],
        populations=[PopulationDeclaration(**p) for p in w['populations']])
    graph = WorldGraph(world, list(map(RelationshipDTO.model_validate, w['relationships'])))
    units = Registry(tuple(Unit(v['id'], tuple(map(tuple, v['dimension'])), v['kind'],
        Decimal(v['scale'])) for v in data['units']))
    return StaticSystemRequest.model_validate(data['request']), dict(graph=graph,
        units=units, mechanisms=mechanisms(units=units, times=(TimeBasis('day:0', Decimal(86400)),)))


def set_work(data, work):
    from copy import deepcopy
    for key in ('economy',):
        data['request'][key] = deepcopy(work)
    for key in ('provisioning', 'social_organization', 'knowledge_culture', 'health'):
        data['request'][key]['work'] = deepcopy(work)
    data['request']['provisioning']['chain']['batch'] = deepcopy(work['batch'])
    for key in ('governance', 'law_conflict'):
        data['request'][key]['administration'] = deepcopy(work)


def trusted(data=None):
    """Real engine registry and revision inputs, with explicit SV dispositions."""
    from copy import deepcopy
    from poliscope_engine.contracts.revisions import RevisionInputs
    from poliscope_engine.domains.static_host import conformance_catalog
    from poliscope_engine.domains.static_host import host_registry, definitions, MODEL, context_digest, incoming
    from poliscope_engine.domains.static_system import evaluate_system, DOMAINS
    from poliscope_engine.mechanisms import Review, declaration_digest
    data = fixture() if data is None else data
    request, ctx = setup(data)
    reviews = [Review(declaration_digest(d), *MODEL, 'sv:WP-032/inspection',
        'oracle:whole-system-literal-v1') for d in definitions()]
    registry = host_registry(request, **ctx, reviews=reviews)
    inputs = json.loads((PATH.parent / 'care-education-v1.json').read_text())['inputs']
    inputs.update({k: deepcopy(v) for k, v in data['world'].items() if k != 'civilization_id'})
    inputs['versions'].update(model_id=MODEL[0],catalog_id='authored:static-system-catalog-v1')
    dependencies = dict(contract_version=1, instances=[], bindings=[], fixed_inputs=[],
        claims=[], account_producers=[], relationships=[])
    token = context_digest(request, **ctx)
    for i, domain in enumerate(DOMAINS):
        dependencies['instances'].append(dict(id=domain, mechanism_id='authored:system/'+domain,
            mechanism_version='v1',scope_id='local',entity_id='local-authority'))
        dependencies['fixed_inputs'].append(dict(consumer=dict(instance_id=domain,port_id='system:context'),
            value=dict(kind='label',value=token)))
        for upstream in incoming(domain):
            dependencies['bindings'].append(dict(producer=dict(instance_id=upstream,port_id='system:evidence'),
                consumer=dict(instance_id=domain,port_id='system:from/'+upstream)))
    dependencies['relationships'] = [dict(kind='institutional',
        source_instance_id=r.source,target_instance_id=r.target,relationship_ref=r.obligation_ref)
        for r in request.requirements]
    result = evaluate_system(request, **ctx)
    inputs['design']['execution']['dependencies'] = dependencies
    inputs['design']['execution']['batch'] = result['candidate_batch']
    if result['candidate_batch'] is not None:
        batch = result['candidate_batch']
        accounts = {a['id']:a for a in batch['accounts']}
        plan = dict(id='system-ledger',procedure='priority',claim_order=[],choices=[],
            mechanism_ref='authored:static-system-snapshot')
        for i,claim in enumerate(batch['claims']):
            instance = 'ledger-' + str(i)
            account = accounts[claim['account_id']]
            dependencies['instances'].append(dict(id=instance,
                mechanism_id='authored:static-ledger/'+account['unit_id'],mechanism_version='v1',
                entity_id=account['id'],scope_id=account['scope_id']))
            for port,value in [('system:context',dict(kind='label',value=token)),
                    ('system:claim',dict(kind='label',value=claim['id'])),
                    ('system:account',dict(kind='reference',entity_id=account['id']))]:
                dependencies['fixed_inputs'].append(dict(consumer=dict(instance_id=instance,port_id=port),value=value))
            dependencies['claims'].append(dict(instance_id=instance,claim_id='system:ledger-claim',
                account_id=account['id'],allocation_id='system-ledger'))
            inputs['design']['execution']['claims'].append(dict(instance_id=instance,
                claim_id='system:ledger-claim',account_claim_id=claim['id']))
            plan['claim_order'].append(claim['id'])
            plan['choices'].append(dict(claim_id=claim['id'],access='denied',access_limit='0',
                funding_known=True,requirements=[],outputs=[],loss_per_unit='0',
                mechanism_ref='authored:static-system-snapshot',source_refs=['synthetic:whole-system']))
        inputs['design']['execution']['allocations'] = [plan]
    inputs['references'] = [dict(id='synthetic:whole-system',kind='source',visibility='public',
        availability='available',description='Authored finite synthetic all-domain fixture; no source activation or empirical validity.',
        source=dict(id='synthetic:whole-system',repository_id='poliscope',document_id='static-system-v1',
            revision_id='v1',location='tests/fixtures/domains/static-system-v1.json',
            excerpt_digest='sha256:'+__import__('hashlib').sha256(PATH.read_bytes()).hexdigest(),
            license_id='MIT',historical_status='current',supersedes_refs=[]),assumption=None)]
    for identity,account_id,name in [('shared-time','time:a','Shared participant time'),
            ('staff-time','time:b','Shared staff time'),('supplies','supplies','Finite supplies'),
            ('classroom','school:slots','Classroom seats')]:
        account = next(a for a in result['candidate_batch']['accounts'] if a['id']==account_id)
        inputs['measurements'].append(dict(id=identity,version='v1',name=name,procedure='identity',
            inputs=[dict(node=['account_result',account_id,'available'],scope_id=account['scope_id'])],
            unit_id=account['unit_id'],scope_id=account['scope_id'],aggregation='same_scope',
            time_basis_id=account['period_id'],denominator_scope_id=None,coverage='partial',
            interpretation='Finite synthetic input capacity; no delivered service or desired societal outcome is inferred.',
            source_refs=['synthetic:whole-system'],assumption_refs=[],diagnostics=[]))
    parsed = RevisionInputs.model_validate(inputs)
    catalog = conformance_catalog()
    catalog.validate(world=ctx['graph'].registry, mechanisms=registry,
        branch_ids=[c.branch_id for m in catalog.modules for c in m.coverage])
    return request, ctx, registry, parsed


if __name__ == '__main__':
    import sys
    from poliscope_engine.storage import Store
    from poliscope_engine.revisions import Revisions
    from poliscope_engine.contracts.revisions import CreateRequest
    _,_,registry,inputs = trusted()
    with Store(Path(sys.argv[1])) as store:
        service=Revisions(store,registry=registry)
        print(service.create(CreateRequest(revision_contract=1,data_store_id=service.data_store_id,
            civilization_id='civ',branch_id='main',operation_id='whole-system:create',
            name='Synthetic all-domain education',inputs=inputs)).context.revision_id)
