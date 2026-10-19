"""WP-019 standalone synthetic setup; never imports implementation test builders.

Frozen arithmetic oracle lives in docs/roadmap/execution/WP-019.md.
Only the published data-only mechanism declarations are reused.
"""
from decimal import Decimal
import json
from pathlib import Path
from poliscope_engine.contracts.mechanisms import MechanismDefinition
from poliscope_engine.contracts.revisions import RevisionInputs, CreateRequest, PreviewRequest, ApplyRequest, BranchRequest
from poliscope_engine.mechanisms import MechanismRegistry, Implementation, Review, declaration_digest
from poliscope_engine.numeric import Registry, Unit, TimeBasis, RUNTIME_ID

PROVENANCE = dict(origin='authored', source_refs=[], assumption_refs=[])
Q = dict(kind='quantity', unit_id='kg', time_basis_id=None, denominator_scope_id=None)


def quantity(value):
    return dict(Q, value=str(value))


def definitions():
    source, demand = json.loads(Path('contracts/mechanism-fixtures.json').read_text())
    # Demand has an explicit authored request input rather than a callback constant.
    demand['inputs'].append(dict(id='synthetic:need', value_type=Q, required=True, missing_behavior='propagate'))
    demand['outputs'][0]['input_refs'] = ['synthetic:need']
    qualitative = dict(source, id='synthetic:qualitative', modeling='qualitative',
                       support=dict(static=None, transition=None), traces=[])
    policy = dict(source, id='synthetic:access-policy', scope_kinds=['settlement', 'region'], policy=dict(semantics='exclusive', composition_rule=None),
                  inputs=[dict(id='synthetic:limit', value_type=Q, required=True, missing_behavior='propagate')],
                  traces=[])
    return [MechanismDefinition.model_validate(d) for d in (demand, qualitative, policy)]


def registry():
    defs = definitions()
    def callback(port, inputs):
        return inputs['synthetic:need' if port == 'synthetic:requested' else 'synthetic:allocated']
    implementations = [Implementation(d.support.static.implementation.id,
        d.support.static.implementation.version, 'static', callback) for d in defs if d.support.static]
    # The policy declaration shares supply implementation identity, but never executes.
    return MechanismRegistry(model=('synthetic:model', 'v1'),
        units=Registry((Unit('kg', (('mass', 1),), 'stock', Decimal(1)),
                        Unit('hours', (('time', 1),), 'capacity', Decimal(1)))),
        times=(TimeBasis('day', Decimal(86400)), TimeBasis('day:0', Decimal(86400))), source_ids=['synthetic:source'],
        fixture_ids=[('synthetic:positive', 'v1')], implementations=implementations,
        reviews=[Review(declaration_digest(d), 'synthetic:model', 'v1', 'wp019:declaration-inspection',
                        'wp019:hand-derived-oracle') for d in defs], definitions=defs)


def account(identity, opening, **updates):
    return dict(contract_version=1, id=identity, kind='stock', unit_id='kg', scope_id='east',
        period_id=None, invariant='physical', quantum='0.01', maximum='1000', opening=opening,
        source_refs=[]) | updates


def posting(identity, kind, source, destination, amount):
    return dict(id=identity, kind=kind, source_id=source, destination_id=destination, amount=amount,
                reservation_id=None, claim_id=None, mechanism_ref='synthetic:finite-import', source_refs=[])


def inputs():
    entities = [dict(id=i, entity_kind=k, label='Synthetic ' + i, provenance=PROVENANCE) for i, k in
                [('civ', 'civilization'), ('stock', 'account'), ('water', 'resource'),
                 ('product', 'account'), ('residual', 'account'), ('labor', 'account'),
                 ('east-authority', 'institution'), ('region-authority', 'institution')]]
    scopes = [dict(id=i, scope_kind=k, label='Synthetic ' + i, provenance=PROVENANCE) for i, k in
              [('east', 'settlement'), ('west', 'settlement'), ('watershed', 'region'), ('region', 'region')]]
    relationships = [dict(id=i, relationship_version='v1', relationship_kind=k, from_id=a, to_id=b,
        aggregation=dict(kind='partition', partition_id='whole') if k == 'access' else dict(kind='non_aggregating'),
        provenance=PROVENANCE) for i, k, a, b in [
            ('view-east', 'access', 'water', 'east'), ('view-west', 'access', 'water', 'west'), ('view-water', 'access', 'water', 'watershed'),
            ('view-region', 'access', 'water', 'region'),
            ('authority-east', 'jurisdiction', 'east-authority', 'east'),
            ('authority-region', 'jurisdiction', 'region-authority', 'region')]]
    values = [dict(id='water-value', entity_id='water', scope_id='east', partition='conditions',
        property_id='water-stock', value=quantity(100), effective_time=dict(tick=0, calendar_id='calendar'),
        provenance=PROVENANCE)]
    accounts = [account('stock', '100'), account('product', '0'), account('residual', '0'),
                account('labor', '12', kind='capacity', unit_id='hours', period_id='day:0', invariant='budget')]
    claims = [dict(id=i, account_id='stock', claimant_id='water', requested='80', source_refs=[]) for i in ('a', 'b')]
    choices = [dict(claim_id=i, access='allowed', access_limit='100', funding_known=True,
        requirements=[dict(account_id='labor', per_unit='0.1', kind='funding')],
        outputs=[dict(account_id='product', per_unit='0.7', role='product'),
                 dict(account_id='residual', per_unit='0.2', role='residual')], loss_per_unit='0.1',
        mechanism_ref='synthetic:selected-access', source_refs=[]) for i in ('a', 'b')]
    instances = [dict(id=i, mechanism_id='synthetic:demand', mechanism_version='v1', scope_id=s, entity_id='stock')
                 for i, s in [('a', 'east'), ('b', 'east')]]
    dep = dict(contract_version=1, instances=instances, bindings=[], fixed_inputs=[
        dict(consumer=dict(instance_id=i, port_id='synthetic:need'), value=quantity(80)) for i in ('a', 'b')],
        claims=[dict(instance_id=i, claim_id='synthetic:claim', account_id='stock', allocation_id='shared') for i in ('a', 'b')],
        account_producers=[], relationships=[])
    execution = dict(contract_version=1, dependencies=dep,
        batch=dict(contract_version=1, accounts=accounts, claims=claims,
            postings=[posting('finite-import', 'import', None, 'stock', '10'),
                      posting('initial-loss', 'loss', 'stock', None, '10')],
            reservations=[dict(id='hold-b', account_id='stock', claim_id='b', amount='40')], subtotals=[]),
        claims=[dict(instance_id=i, claim_id='synthetic:claim', account_claim_id=i) for i in ('a', 'b')],
        allocations=[dict(id='shared', procedure='priority', claim_order=['a', 'b'], choices=choices,
                          mechanism_ref='synthetic:selected-priority')], solvers=[], operation_limit=100000)
    design = dict(contract_version=1, effective_time=dict(tick=0, calendar_id='calendar'), execution=execution,
        policies=[], policy_rules=[], policy_inputs=[], world_inputs=[], assumption_inputs=[], realization_inputs=[],
        conditions=[], realization=dict(identity=dict(id='synthetic:realization', version='v1'), seed=None, event_ids=[], values=[]))
    measurements = [dict(id='east-output', version='v1', name='Synthetic east actual input', procedure='identity',
        inputs=[dict(node=['output', 'a', 'synthetic:supported'], scope_id='east')], unit_id='kg', scope_id='east',
        aggregation='same_scope', time_basis_id=None, denominator_scope_id=None, coverage='known',
        interpretation='Allocated input, not requested input', source_refs=[], assumption_refs=[], diagnostics=[])]
    return RevisionInputs.model_validate(dict(versions=dict(world_schema=1, catalog_id='synthetic:catalog',
        model_id='synthetic:model', numeric_runtime_id=RUNTIME_ID), entities=entities, scopes=scopes, values=values,
        owners=[dict(entity_id='water', property_id='water-stock', partition='conditions', writer_id='fixture')],
        populations=[], relationships=relationships, design=design, assumptions=[], measurements=measurements,
        goals=[], references=[]))


def create(service, data=None):
    return service.create(CreateRequest(revision_contract=1, data_store_id=service.data_store_id,
        civilization_id='civ', branch_id='main', name='WP-019 synthetic world', operation_id='create', inputs=data or inputs()))


def preview(context, data, alternatives=()):
    changes = [dict(kind='replace_inputs', inputs=data.model_dump(mode='json'))]
    return PreviewRequest.model_validate(dict(revision_contract=1, context=context, changes=changes,
        decision=dict(alternatives=list(alternatives), selected_id=None, rationale_ref=None)))


def apply(service, request, operation='apply'):
    return ApplyRequest(revision_contract=1, preview=request,
        candidate_digest=service.preview(request).candidate_digest, operation_id=operation)


def move(service, outcome, action, **updates):
    return service.change_branch(BranchRequest.model_validate(dict(revision_contract=1, context=outcome.context,
        expected_sequence=outcome.branch_sequence, operation_id=action + str(outcome.branch_sequence),
        action=action, new_branch_id=None, name=None) | updates))


def physical(evidence):
    result = evidence.evaluation
    return dict(outcome=result.outcome,
        accounts={a.account_id: [a.closing, a.outstanding_reserved, a.available] for a in result.accounts.accounts},
        claims={c.claim_id: [c.actual, c.unmet] for c in result.accounts.claims},
        outputs={o.node[1]: o.value.value for o in result.observations
                 if o.node[0] == 'output' and o.node[-1] == 'synthetic:supported'})


# Literal oracle; no production arithmetic, allocation or digest code derives it.
EXPECTED = dict(outcome='insufficient', accounts={'stock': ['0', '0', '0'], 'labor': ['2', '0', '2'],
    'product': ['70', '0', '70'], 'residual': ['20', '0', '20']},
    claims={'a': ['60', '20'], 'b': ['40', '40']}, outputs={'a': '60', 'b': '40'})
