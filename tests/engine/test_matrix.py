"""Independent direction, finite-account, provenance and bounded projection checks."""
import pytest
from poliscope_engine import matrix, overview
from poliscope_engine.contracts.revisions import RevisionInputs
from poliscope_engine.contracts.matrix import MatrixQuery
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from headless_fixture import registry, inputs, create
from test_interviews import setup


def query(context, **updates):
    return dict(context=context, scope_id='east', axis='scope') | updates


def collect(service, data):
    rows, seen = [], set()
    while True:
        result = matrix.page(service, data)
        assert len(result.relationships) <= 10 and len(result.cells) <= 25
        assert len(result.model_dump_json().encode()) < 900000
        rows.extend(result.relationships)
        if result.detail_next_cursor is None:
            assert len(rows) == result.relationship_total
            assert len({r.id for r in rows}) == len(rows)
            return rows
        assert result.detail_next_cursor not in seen
        seen.add(result.detail_next_cursor)
        data = dict(data, detail_cursor=result.detail_next_cursor)


def test_retained_direction_competition_exact_magnitudes_and_same_inspectors(tmp_path):
    with Store(tmp_path) as store:
        writer = Revisions(store, registry=registry())
        context = create(writer).context
        reader = Revisions(store, registry=None)  # No model execution is available.
        original = writer.read(context).model_dump_json(), writer.evidence(context).model_dump_json()
        rows = collect(reader, query(context))
        requires = next(r for r in rows if r.row.id == 'node:claim/a/synthetic:claim' and r.column.id == 'node:account/stock')
        assert requires.relationship_type == 'requires'
        assert requires.magnitude is None and requires.activation == 'observed'
        assert not any(r.row.id == requires.column.id and r.column.id == requires.row.id and r.relationship_type == 'requires' for r in rows)
        competing = [r for r in rows if r.relationship_type == 'competes']
        assert {(r.row.id,r.column.id) for r in competing} == {('node:claim/a/synthetic:claim','node:account/stock'),('node:claim/b/synthetic:claim','node:account/stock')}
        assert all(r.provenance == 'model' and r.activation == 'declared' and r.magnitude is None for r in competing)
        # Actual allocated amounts are 60/40, never the requested 80/80.
        stock_uses = [r for r in rows if r.relationship_type == 'supplies' and r.row.id == 'node:account/stock' and r.magnitude.unit_id == 'kg']
        assert sum(int(r.magnitude.value) for r in stock_uses) == 110  # 100 allocated + 10 initial loss
        for relation in rows:
            for inspector in relation.inspectors:
                result = overview.page(reader, inspector)
                assert result.items and result.query.context == context
        account_query = next(q for q in requires.inspectors if q.collection == 'accounts')
        account = overview.page(reader, account_query).items[0]
        assert account.id == 'stock' and account.result.available == '0'
        assert set(account.trace_refs) <= {q.item_id for q in requires.inspectors if q.collection == 'traces'}
        assert original == (reader.read(context).model_dump_json(), reader.evidence(context).model_dump_json())
        assert reader.branch(context).sequence == 0


def test_explicit_output_supply_asymmetry_and_mixed_cell_types(tmp_path):
    raw = inputs().model_dump(mode='json')
    dep = raw['design']['execution']['dependencies']
    dep['fixed_inputs'] = [f for f in dep['fixed_inputs'] if f['consumer']['instance_id'] != 'b']
    dep['bindings'] = [dict(producer=dict(instance_id='a',port_id='synthetic:requested'),consumer=dict(instance_id='b',port_id='synthetic:need'))]
    dep['relationships'] = [dict(kind='documentary',source_instance_id='a',target_instance_id='b',relationship_ref='synthetic:context')]
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry())
        context = create(service, RevisionInputs.model_validate(raw)).context
        rows = collect(service, query(context))
        supply = next(r for r in rows if r.row.id == 'node:output/a/synthetic:requested' and r.column.id == 'node:input/b/synthetic:need')
        assert supply.relationship_type == 'supplies' and supply.provenance == 'retained_execution'
        influence = next(r for r in rows if r.relationship_type == 'influences')
        assert influence.row.id == 'node:output/a' and influence.column.id == 'node:input/b'
        assert influence.activation == influence.provenance == 'documentary'
        assert influence.coverage == 'unmodeled' and influence.magnitude is None
        cells = matrix.page(service, query(context)).cells
        assert {'requires','supplies','competes','influences'} <= {c.relationship_type for c in cells}
        assert all(c.count >= 1 for c in cells)
        assert not any(r.relationship_type == 'conflicts' for r in rows)


def test_documentary_supersession_choice_source_and_empty_states(tmp_path):
    store, service, state = setup(tmp_path)
    try:
        data = dict(context=state.context, scope_id='home', axis='decision')
        result = matrix.page(service, data)
        assert result.relationship_total == 1
        row = result.relationships[0]
        assert row.relationship_type == 'supersedes'
        assert row.row.decisions == ['society:DEC-003'] and row.column.id == 'society:DEC-002.2'
        assert row.activation == row.provenance == 'documentary' and row.magnitude is None
        assert row.interviews[0].question_id == 'society:DEC-003'
        assert row.sources[0].source_ref == 'society:source/06_global_decision_ledger.md'
        assert matrix.page(service, data | dict(provenance='retained_execution')).relationship_total == 0
        assert matrix.page(service, data | dict(relationship_type='requires')).cells == []
        assert matrix.page(service, data | dict(row_id='society:DEC-003')).relationship_total == 1
        assert matrix.page(service, data | dict(column_id='society:DEC-003')).relationship_total == 0
        assert matrix.page(service, data | dict(axis='selected_alternative')).relationship_total == 0
        assert matrix.page(service, data | dict(axis='branch')).unmapped_count == 1
        assert 'Private rationale canary' not in result.model_dump_json()
    finally:
        store.close()


def test_query_cursors_bound_to_every_filter_scope_evidence_catalog_and_kind(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry())
        context = create(service).context
        first = matrix.page(service, query(context))
        assert first.detail_next_cursor
        for update in [dict(axis='domain'),dict(scope_id='west'),dict(relationship_type='supplies'),dict(provenance='model'),dict(row_id='east'),dict(column_id='east')]:
            with pytest.raises(ValueError):
                matrix.page(service, query(context, detail_cursor=first.detail_next_cursor) | update)
        for data in [dict(cursor=first.detail_next_cursor),dict(detail_cursor='bad:d:10'),dict(detail_cursor=first.detail_next_cursor.rsplit(':',1)[0]+':99999'),dict(scope_id='foreign')]:
            with pytest.raises(ValueError): matrix.page(service, query(context) | data)
        with pytest.raises(ValueError): MatrixQuery.model_validate(query(context, axis='fabricated'))
        with pytest.raises(ValueError): MatrixQuery.model_validate(query(context) | dict(path='/etc/passwd'))


def test_large_sparse_stream_keeps_mounted_details_bounded_and_pages_cells(tmp_path, monkeypatch):
    store, service, state = setup(tmp_path)
    example = matrix.page(service, dict(context=state.context,scope_id='home')).relationships[0]
    def large(*args):
        for i in range(10000):
            yield example.model_copy(update={'id':f'edge:{i}', 'row':example.row.model_copy(update={'decisions':[f'decision:{i}']})})
    monkeypatch.setattr(matrix, 'relationships', large)
    try:
        data = dict(context=state.context,scope_id='home',axis='decision')
        result = matrix.page(service, data)
        assert result.relationship_total == result.cell_total == 10000
        assert len(result.cells) == 25 and len(result.relationships) == 10
        assert result.next_cursor and result.detail_next_cursor
        next_page = matrix.page(service,data | dict(cursor=result.next_cursor, detail_cursor=result.detail_next_cursor))
        assert not {c.row_id for c in next_page.cells} & {c.row_id for c in result.cells}
        assert next_page.relationships[0].id == 'edge:10'
    finally:
        store.close()


def test_current_condition_binding_and_unavailable_node_are_explicit(tmp_path):
    raw = inputs().model_dump(mode='json')
    dep = raw['design']['execution']['dependencies']
    dep['fixed_inputs'] = [f for f in dep['fixed_inputs'] if f['consumer']['instance_id'] != 'a']
    raw['design']['world_inputs'] = [dict(consumer=dict(instance_id='a',port_id='synthetic:need'),value_id='water-value')]
    raw['values'][0]['value'] = dict(kind='unknown',reason='Unanswered input')
    raw['values'][0]['entity_id'] = 'stock'
    raw['owners'][0]['entity_id'] = 'stock'
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry())
        context = create(service, RevisionInputs.model_validate(raw)).context
        rows = collect(service, query(context))
        link = next(r for r in rows if r.column.id == 'condition:water-value')
        assert link.relationship_type == 'requires' and link.provenance == 'model'
        condition = overview.page(service, link.inspectors[0]).items[0]
        assert condition.condition.value.kind == 'unknown'
        assert any(r.coverage == 'missing_input' and r.activation == 'unavailable' for r in rows)
        assert all(r.magnitude is None for r in rows if r.coverage == 'missing_input')


def test_policy_conflicts_keep_authority_group_and_exact_inspector_links(tmp_path):
    raw = inputs().model_dump(mode='json')
    policy = dict(contract_version=1,id='p1',mechanism=dict(id='synthetic:access-policy',version='v1'),
        scope_id='east',authority_id='east-authority',entity_ids=['water'],parameter_id='synthetic:limit',
        value=dict(kind='quantity',value='10',unit_id='kg',time_basis_id=None,denominator_scope_id=None),
        conflict_kind='parameter',account_refs=['stock'],choice_refs=[])
    raw['design']['policies'] = [policy, policy | dict(id='p2',authority_id='region-authority',value=policy['value'] | dict(value='20'))]
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry())
        context = create(service, RevisionInputs.model_validate(raw)).context
        conflicts = [r for r in collect(service, query(context)) if r.relationship_type == 'conflicts']
        assert len(conflicts) == 2 and len({r.column.id for r in conflicts}) == 1
        assert {r.row.id for r in conflicts} == {'policy:p1','policy:p2'}
        assert all(r.coverage == 'conflict' and r.magnitude is None for r in conflicts)
        for r in conflicts:
            policy = overview.page(service,next(q for q in r.inspectors if q.collection == 'policies')).items[0]
            assert 'policy:' + policy.id == r.row.id


def test_retained_model_and_rule_reads_do_not_need_executable_registry(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry())
        context = create(service).context
        reader = Revisions(store, registry=None)
        mechanism = matrix.model(reader, dict(context=context,kind='mechanism',identity='synthetic:demand'))
        assert mechanism.status == 'retained' and mechanism.mechanism.id == 'synthetic:demand'
        assert mechanism.mechanism.domain == 'economy'
        rule = matrix.model(reader, dict(context=context,kind='rule',identity='shared'))
        assert rule.status == 'retained' and rule.allocation_rule.procedure == 'priority'
        assert rule.allocation_rule.claim_order == ['a','b']
        assert matrix.model(reader,dict(context=context,kind='mechanism',identity='unknown')).status == 'unavailable'
        with pytest.raises(ValueError):
            matrix.model(reader,dict(context=context,kind='mechanism',identity='synthetic:demand',load='code'))


def test_selected_choice_grouping_retains_documentary_status_and_context(tmp_path):
    from test_atlas import apply, all_rows, query as atlas_query
    from test_interviews import edit
    store, service, state = setup(tmp_path)
    try:
        row = next(r for r in all_rows(service, atlas_query(state)) if r.question.id == 'society:DEC-003')
        change = edit(state, choice_id=row.options[0].id, rationale='') | dict(query=row.interview.model_dump())
        selected = apply(service, change, 'matrix-choice')
        result = matrix.page(service, dict(context=selected.context,scope_id='home',axis='selected_alternative'))
        assert result.relationship_total == 1
        assert result.cells[0].row_id == row.question.id + '/' + row.options[0].id.replace('/', '%2F')
        assert result.relationships[0].activation == 'documentary'
        assert result.relationships[0].interviews[0].context == selected.context
        assert matrix.page(service,dict(context=state.context,scope_id='home',axis='selected_alternative')).relationship_total == 0
    finally:
        store.close()


def test_structured_endpoint_ids_do_not_collapse_distinct_slash_containing_ids():
    assert matrix.compound(['input','a/b','c']) != matrix.compound(['input','a','b/c'])
    assert matrix.compound(['input','a%2Fb','c']) != matrix.compound(['input','a/b','c'])
    assert len(matrix.compound(['x'*256,'y'*256])) <= 256
