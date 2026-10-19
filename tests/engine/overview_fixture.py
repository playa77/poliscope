"""Synthetic WP-022 oracle: east has no reachable stock; regional reserve is 200 kg.

Uses the already independently inspected WP-019 data-only model declarations.
Expected zero allocation, 80 kg unmet east claim and 200 kg regional reserve are
literal fixture inputs/expectations, never calculated by a UI implementation.
"""
from headless_fixture import inputs as headless_inputs, registry as headless_registry, quantity, PROVENANCE
from poliscope_engine.contracts.revisions import RevisionInputs, CreateRequest

from poliscope_engine.mechanisms import MechanismRegistry

def registry():
    host = headless_registry()
    return MechanismRegistry(model=host.model, units=host.units, times=host.times, source_ids=host.source_ids,
        assumption_ids=['synthetic:assumption'], fixture_ids=host.fixture_ids, implementations=host.implementations,
        reviews=host.reviews, definitions=host.definitions, graphs=host.graphs)

STATUSES = ('known', 'partial', 'missing_input', 'unmodeled', 'conflict', 'solver_failure', 'not_applicable')


def inputs():
    raw = headless_inputs().model_dump(mode='json')
    raw['entities'].append(dict(id='reserve', entity_kind='account', label='Regional reserve', provenance=PROVENANCE))
    execution = raw['design']['execution']
    execution['batch']['accounts'][0]['opening'] = '0'
    execution['batch']['accounts'].append(dict(execution['batch']['accounts'][0], id='reserve', opening='200', scope_id='region'))
    for choice in execution['allocations'][0]['choices']:
        choice['requirements'] = []
    execution['batch']['postings'] = []
    execution['batch']['reservations'] = []
    execution['batch']['claims'][1]['requested'] = '0'
    execution['dependencies']['fixed_inputs'][1]['value'] = quantity(0)
    raw['measurements'] = []
    for i, status in enumerate(STATUSES):
        raw['measurements'].append(dict(id=f'status:{i}', version='v1', name='Synthetic ' + status,
            procedure='identity', inputs=[dict(node=['output', 'a', 'synthetic:supported'], scope_id='east')],
            unit_id='kg', scope_id='east', aggregation='same_scope', time_basis_id=None, denominator_scope_id=None,
            coverage=status, interpretation='Synthetic coverage case; no societal sufficiency is implied.',
            source_refs=['synthetic:source'], assumption_refs=[], diagnostics=[]))
    for identity, scope, account in [('local-reserve', 'east', 'stock'), ('regional-reserve', 'region', 'reserve')]:
        raw['measurements'].append(dict(raw['measurements'][0], id=identity, name='Reserve', scope_id=scope,
            inputs=[dict(node=['account_result', account, 'available'], scope_id=scope)],
            interpretation='Declared account reserve at this scope; no access from another scope is inferred.'))
    for identity, category, threshold in [('red', 'physical_shortage', '1'), ('orange', 'uncertainty', '1'), ('green', 'physical_shortage', '-1')]:
        rule = dict(id='threshold:' + identity, version='v1', name='Synthetic ' + identity + ' boundary',
            operation='lt', threshold=quantity(threshold), category=category,
            interpretation='Explicit hypothetical diagnostic, not a universal desirable direction.', source_refs=['synthetic:source'], assumption_refs=[])
        raw['measurements'].append(dict(raw['measurements'][0], id=identity, name=identity, diagnostics=[rule]))
    raw['goals'] = [dict(id='comparison', kind='comparison', question='Player target must not recolor diagnostics', indicator_id='orange', operation='ge', threshold=quantity(1)), dict(id='question', kind='narrative', question='Can local demand be met?', indicator_id=None, operation=None, threshold=None)]
    raw['assumptions'] = [dict(id='synthetic:assumption', value=dict(kind='label', value='No inter-scope transfer mechanism is declared.'))]
    for definition in raw['measurements']:
        definition['assumption_refs'] = ['synthetic:assumption']
    raw['references'] = [dict(id='synthetic:source', kind='source', visibility='public', availability='available',
        description='Original synthetic WP-022 inspection fixture. <img src="https://sink.invalid/private">', assumption=None,
        source=dict(id='synthetic:source', repository_id='synthetic', document_id='overview-fixture', revision_id='v1',
            location='Synthetic account/coverage fixture', excerpt_digest='sha256:' + 'a'*64, license_id='MIT',
            historical_status='current', supersedes_refs=[]))]
    raw['references'].append(dict(id='synthetic:assumption', kind='assumption', visibility='public', availability='available',
        description='Declared access exclusion', source=None, assumption=dict(id='synthetic:assumption', scope_id='region',
        definition_id='synthetic:no-transfer', definition_version='v1', origin='authored', uncertainty_form='qualitative',
        uncertainty_definition_ref=None, rationale='No inter-scope transfer mechanism is declared.', source_refs=['synthetic:source'])))
    return RevisionInputs.model_validate(raw)


def seed(service, data=None):
    return service.create(CreateRequest(revision_contract=1, data_store_id=service.data_store_id,
        civilization_id='civ', branch_id='main', name='Unreachable east; regional surplus', operation_id='overview:create', inputs=data or inputs()))


if __name__ == '__main__':
    import sys
    from pathlib import Path
    from poliscope_engine.storage import Store
    from poliscope_engine.revisions import Revisions
    with Store(Path(sys.argv[1])) as store:
        print(seed(Revisions(store, registry=registry())).context.revision_id)
