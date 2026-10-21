"""Independent canonical topology, revision safety and shared-view acceptance."""
import pytest
from poliscope_engine import exploration, matrix, overview, interviews
from poliscope_engine.contracts.revisions import RevisionInputs
from poliscope_engine.revisions import Revisions
from poliscope_engine.storage import Store
from poliscope_engine.workspace import dispatch, registry
from headless_fixture import registry as finite_registry, inputs, create, account
from test_interviews import history

P = dict(origin='player_input', source_refs=[], assumption_refs=[])

def setup(directory):
    store = Store(directory)
    service = Revisions(store, registry=registry())
    state = dispatch(service, 'create', dict(name='Topology', setup='blank', scope_name='Home', population='12', land_area='3'), 'create')
    return store, service, state.context


def query(context, **updates):
    return dict(context=context, scope_id='home') | updates


def commit(service, context, change, identity):
    edit = query(context, change=change)
    preview = exploration.preview(service, edit)
    return exploration.apply(service, dict(edit=edit, candidate_digest=preview.candidate_digest), identity).state.context


def entity(identity, kind='asset', label=None):
    return dict(kind='entity', entity=dict(id=identity, entity_kind=kind, label=label or identity, provenance=P))


def edge(identity, source, target, kind='jurisdiction', version='v1', aggregation=None):
    return dict(kind='relationship', relationship=dict(id=identity, from_id=source, to_id=target,
        relationship_kind=kind, relationship_version=version, aggregation=aggregation or dict(kind='non_aggregating'), provenance=P))


def collect(service, data):
    rows = []
    while True:
        page = exploration.page(service, data)
        assert len(page.items) <= 25
        rows += page.items
        if page.next_cursor is None:
            assert len(rows) == page.total
            return rows
        data = data | dict(cursor=page.next_cursor)


def test_overlapping_authority_separate_projections_shared_identity_and_data_only_history(tmp_path):
    store, service, base = setup(tmp_path)
    try:
        current = base
        for i, change in enumerate([entity('clinic'), entity('council-a','institution'), entity('council-b','institution'),
            edge('a','council-a','clinic'), edge('b','council-b','clinic'), edge('network','clinic','home','connectivity'),
            edge('place','clinic','home','containment')]):
            current = commit(service, current, change, str(i))
        before = service.read(current).model_dump_json(), service.evidence(current).model_dump_json()
        reader = Revisions(store, registry=None)
        authority = collect(reader, query(current, projection='authority'))
        assert {r.relationship.id for r in authority if r.relationship} == {'a','b'}
        assert sum(r.entity is not None and r.id == 'clinic' for r in authority) == 1
        assert {r.relationship.id for r in collect(reader, query(current, projection='geography')) if r.relationship} == {'place'}
        assert {r.relationship.id for r in collect(reader, query(current, projection='networks')) if r.relationship} == {'network'}
        assert not collect(reader, query(current, projection='membership'))
        rows = matrix.page(reader, query(current, axis='scope')).relationships
        assert any(r.world_refs == ['council-a','clinic'] and 'jurisdiction a' in r.explanation for r in rows)
        assert any(r.entity and r.entity.label == 'clinic' for r in collect(reader, query(current, identity='clinic')))
        assert before == (service.read(current).model_dump_json(), service.evidence(current).model_dump_json())
        assert not any(r.entity and r.entity.id == 'clinic' for r in collect(reader, query(base)))
        # Edit an obligation through exactly the normal preview/apply path.
        current = commit(service, current, edge('owed','council-a','clinic','obligation'), 'obligation')
        current = commit(service, current, edge('owed','council-a','clinic','obligation','v2') | dict(terms='Inspect the clinic each month; staffing capacity unanswered'), 'obligation2')
        assert any(r.relationship and r.relationship.id == 'owed' and r.relationship.relationship_version == 'v2' for r in collect(reader, query(current)))
        assert any('obligation owed version v2' in r.explanation and r.world_refs[0] == 'council-a' for r in matrix.page(reader, query(current)).relationships)
    finally: store.close()


def test_shared_condition_edits_domain_matrix_world_purity_retry_and_stale(tmp_path):
    store, service, base = setup(tmp_path)
    try:
        current = commit(service, base, edge('land-access','land','home','access'), 'access')
        edit = query(current, change=dict(kind='value',value_id='land:value',value=dict(kind='quantity',value='9',unit_id='km2',time_basis_id=None,denominator_scope_id=None)))
        before = len(history(service, current))
        preview = exploration.preview(service, edit)
        assert len(history(service, current)) == before
        apply = dict(edit=edit,candidate_digest=preview.candidate_digest)
        accepted = exploration.apply(service, apply, 'area')
        assert exploration.apply(service, apply, 'area') == accepted
        assert exploration.apply(service, apply, 'other').status == 'stale'
        context = accepted.state.context
        assert len(history(service, context)) == before + 1
        world_value = next(r.value for r in collect(service, query(context)) if r.id == 'land:value')
        assert world_value.value.value == '9'
        interview = interviews.question(service, dict(query(context),domain_id='domain:1'))
        assert next(v for v in interview.conditions if v.id == 'land:value') == world_value
        relation = next(r for r in matrix.page(service, query(context)).relationships if r.world_refs == ['land','home'])
        inspected = overview.page(service, relation.inspectors[0])
        assert inspected.items[0].condition == world_value
        assert next(v for v in service.read(current).inputs.values if v.id == 'land:value').value.value == '3'
    finally: store.close()


def test_invalid_graph_or_ownership_never_commits(tmp_path):
    store, service, base = setup(tmp_path)
    try:
        current = commit(service, base, edge('contains','land','home','containment'), 'contains')
        bad = [edge('cycle','home','land','containment'), edge('missing','land','absent'),
            edge('member','land','home','cohort_membership'),
            edge('contains','land','home','containment'), entity('land','institution'),
            dict(kind='value',value_id='population:value',value=dict(kind='quantity',value='1.5',unit_id='people',time_basis_id=None,denominator_scope_id=None)),
            dict(kind='value',value_id='land:value',value=dict(kind='quantity',value='4',unit_id='people',time_basis_id=None,denominator_scope_id=None))]
        for change in bad:
            with pytest.raises(ValueError): exploration.preview(service, query(current,change=change))
        assert len(history(service,current)) == 2
        for update in [dict(scope_id='foreign'),dict(identity='foreign'),dict(cursor='wrong:25')]:
            with pytest.raises(ValueError): exploration.page(service,query(current,**update))
    finally: store.close()


def test_bounded_pages_and_filter_bound_cursors(tmp_path):
    store, service, context = setup(tmp_path)
    try:
        raw = service.read(context).inputs.model_dump(mode='json')
        raw['entities'] += [entity(f'asset:{i}')['entity'] for i in range(100)]
        context = create_from(service, raw)
        first = exploration.page(service, query(context))
        assert first.total == 106 and first.next_cursor
        assert len(collect(service, query(context))) == 106
        with pytest.raises(ValueError): exploration.page(service,query(context,projection='networks',cursor=first.next_cursor))
        with pytest.raises(ValueError): exploration.page(service,query(context,cursor=first.next_cursor.rsplit(':',1)[0]+':0'))
    finally: store.close()


def create_from(service, raw):
    from poliscope_engine.contracts.revisions import CreateRequest
    raw['entities'] = [dict(e, id='other') if e['entity_kind'] == 'civilization' else e for e in raw['entities']]
    return service.create(CreateRequest(revision_contract=1,data_store_id=service.data_store_id,
        civilization_id='other',branch_id='main',name='Large',operation_id='large',inputs=RevisionInputs.model_validate(raw))).context


def test_local_accounts_and_unreachable_surpluses_remain_exact_without_aggregation(tmp_path):
    with Store(tmp_path) as store:
        writer = Revisions(store,registry=finite_registry())
        raw = inputs().model_dump(mode='json')
        raw['entities'].append(entity('remote-stock', 'account')['entity'])
        raw['design']['execution']['batch']['accounts'].append(account('remote-stock', '200', scope_id='west'))
        context = create(writer, RevisionInputs.model_validate(raw)).context
        reader = Revisions(store,registry=None)
        rows = collect(reader,dict(context=context,scope_id='east'))
        stock = next(r for r in rows if r.id == 'account:stock')
        stock_row = overview.page(reader,stock.inspector).items[0]
        assert stock_row.result.available == '0'
        # A west account is separate: geography does not silently make it deliverable.
        west = collect(reader,dict(context=context,scope_id='west'))
        assert not any(r.id == 'account:stock' for r in west)
        remote = next(r for r in west if r.id == 'account:remote-stock')
        assert overview.page(reader, remote.inspector).items[0].result.available == '200'
        assert stock_row.result.available == '0'  # Remote surplus never replenishes the disconnected local stock.
        assert all(r.inspector.scope_id == 'west' for r in west if r.inspector)


def test_crash_after_commit_replays_once_and_terms_are_public_shared_content(tmp_path, monkeypatch):
    store, service, base = setup(tmp_path)
    try:
        edit = query(base,change=edge('stewardship','population','land','obligation') | dict(terms='Maintain common land; no capacity is promised'))
        preview = exploration.preview(service,edit)
        original = service.apply
        def lost_reply(request):
            original(request)
            raise RuntimeError('reply lost after SQLite commit')
        monkeypatch.setattr(service,'apply',lost_reply)
        with pytest.raises(RuntimeError): exploration.apply(service,dict(edit=edit,candidate_digest=preview.candidate_digest),'lost')
        monkeypatch.setattr(service,'apply',original)
        accepted = exploration.apply(service,dict(edit=edit,candidate_digest=preview.candidate_digest),'lost')
        assert len(history(service,accepted.state.context)) == 2
        world = collect(service,query(accepted.state.context))
        terms = next(r for r in world if r.value and r.value.partition == 'design')
        assert terms.value.value.value == 'Maintain common land; no capacity is promised'
        relation = next(r for r in matrix.page(service,query(accepted.state.context)).relationships if r.world_refs == ['population','land'])
        inspector = next(q for q in relation.inspectors if q.item_id == terms.id)
        assert overview.page(service,inspector).items[0].condition == terms.value
        assert service.read(accepted.state.context).inputs.design.policies == []
    finally: store.close()


def test_cohort_role_explicit_and_shared_condition_owner_cannot_be_overridden(tmp_path):
    store, service, base = setup(tmp_path)
    try:
        change = entity('care-cohort','population_cohort')
        with pytest.raises(ValueError): exploration.preview(service,query(base,change=change))
        context = commit(service,base,change | dict(population_role='fixed_input'),'cohort')
        context = commit(service,context,edge('cohort-home','care-cohort','home','cohort_membership',
            aggregation=dict(kind='partition',partition_id='whole')),'membership')
        membership = collect(service,query(context,projection='membership'))
        assert sum(r.entity is not None and r.id == 'care-cohort' for r in membership) == 1
        assert any(r.relationship and r.relationship.id == 'cohort-home' for r in membership)
        raw = service.read(context).inputs.model_dump(mode='json')
        next(o for o in raw['owners'] if o['entity_id'] == 'land')['writer_id'] = 'model:land'
        other = create_from(service,raw)
        with pytest.raises(ValueError,match='write_denied'):
            exploration.preview(service,query(other,change=dict(kind='value',value_id='land:value',
                value=dict(kind='quantity',value='4',unit_id='km2',time_basis_id=None,denominator_scope_id=None))))
    finally: store.close()
