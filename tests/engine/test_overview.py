"""Production retained projection and independent synthetic oracle acceptance."""
import json
import subprocess
import sys
import pytest
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from poliscope_engine.overview import page, target, chart
from poliscope_engine.contracts.overview import OverviewQuery
from poliscope_engine.contracts.revisions import BranchRequest
from overview_fixture import seed, registry, quantity, STATUSES


def query(context, collection='indicators', **updates):
    return dict(context=context.model_dump(), scope_id='east', collection=collection,
        item_id=None, cursor=None, all_scopes=False) | updates


def test_all_statuses_diagnostics_reference_and_exact_local_vs_regional_oracle(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry())
        context = seed(service).context
        # All inspection uses a reader with no executable mechanism registry.
        reader = Revisions(store, registry=None)
        rows = page(reader, query(context)).items
        observations = {r.id: r for r in rows}
        assert [observations[f'status:{i}'].observation.status for i in range(7)] == list(STATUSES)
        assert observations['status:0'].observation.value.value == '0'
        assert observations['status:1'].observation.value.value == '0'
        assert all(observations[f'status:{i}'].observation.value.kind == 'unknown' for i in range(2, 7))
        assert {k: observations[k].tone for k in ('red', 'orange', 'green', 'status:0', 'status:1')} == dict(red='red', orange='orange', green='green', **{'status:0':'neutral', 'status:1':'gray'})
        assert page(reader, query(context, scope_id='region')).items[0].observation.value.value == '200'
        findings = page(reader, query(context, 'findings', scope_id='region', all_scopes=True)).items
        shortage = next(r for r in findings if r.finding.rule_ref == 'a')
        assert shortage.finding.scope_id == 'east' and shortage.finding.values[0].value == '80'
        assert shortage.finding.category == 'physical_shortage'
        accounts = page(reader, query(context, 'accounts', all_scopes=True)).items
        assert {r.id:r.result.available for r in accounts} == dict(stock='0', product='0', residual='0', labor='12', reserve='200')
        distribution = chart(reader, dict(context=context.model_dump(), scope_id='east', indicator_id='local-reserve'))
        assert [(p.label,p.exact) for p in distribution.points] == [('local-reserve','0'),('regional-reserve','200')]
        reference = page(reader, query(context, 'references', item_id='synthetic:source')).items[0].reference
        assert reference.source.revision_id == 'v1' and reference.source.license_id == 'MIT'
        assert reference.visibility == 'public'
        assumption = page(reader, query(context, 'references', item_id='synthetic:assumption')).items[0].reference
        assert assumption.assumption.rationale == 'No inter-scope transfer mechanism is declared.'
        assert len(page(reader, query(context, 'goals')).items) == 2


def test_target_comparisons_never_write_or_recompute_physics(tmp_path, monkeypatch):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry())
        root = seed(service)
        retained = service.evidence(root.context).model_dump_json()
        record = service.read(root.context).model_dump_json()
        monkeypatch.setattr(service, '_evaluate', lambda *a, **k: pytest.fail('physics must not execute'))
        data = dict(context=root.context.model_dump(), scope_id='east', indicator_id='local-reserve', operation='ge', threshold=quantity('0'))
        assert target(service, data).observation.matched is True
        failed = target(service, data | dict(threshold=quantity('1')))
        assert failed.observation.matched is False
        assert failed.physical_output_digest == service.evidence(root.context).report.physical_output_digest
        unknown = target(service, data | dict(indicator_id='status:2'))
        assert unknown.observation.status == 'unavailable' and unknown.observation.matched is None
        for changes in [dict(scope_id='west'), dict(indicator_id='unknown'), dict(threshold=quantity('NaN')), dict(threshold=quantity('2') | dict(unit_id='hours'))]:
            with pytest.raises(ValueError): target(service, data | changes)
        assert service.evidence(root.context).model_dump_json() == retained
        assert service.read(root.context).model_dump_json() == record
        assert service.branch(root.context).sequence == root.branch_sequence


def test_paged_traces_close_dependencies_and_bind_context_root_and_scope(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry())
        root = seed(service)
        service = Revisions(store, registry=None)
        first = page(service, query(root.context, 'traces', all_scopes=True))
        assert first.next_cursor
        seen, cursor = [], None
        while True:
            result = page(service, query(root.context, 'traces', all_scopes=True, cursor=cursor))
            seen.extend(result.items)
            cursor = result.next_cursor
            assert len(result.model_dump_json().encode()) <= 1000000
            if cursor is None: break
        ids = {r.id for r in seen}
        assert len(ids) == len(seen)
        assert all(set(r.trace.dependency_refs) <= ids for r in seen)
        for changes in [dict(scope_id='region'), dict(item_id=seen[0].id), dict(collection='findings')]:
            with pytest.raises(ValueError): page(service, query(root.context, 'traces', all_scopes=True, cursor=first.next_cursor) | changes)
        one = page(service, query(root.context, 'indicators', item_id='local-reserve')).items[0]
        trace = page(service, query(root.context, 'traces', all_scopes=True, item_id=one.observation.trace_refs[0]))
        assert any(r.id == one.observation.trace_refs[0] for r in trace.items)
        with pytest.raises(ValueError): page(service, query(root.context, scope_id='nonexistent'))
        with pytest.raises(ValueError): page(service, query(root.context, item_id='nonexistent'))


def test_blank_conditions_have_provenance_without_invented_calculation(tmp_path):
    from poliscope_engine.workspace import dispatch, registry as blank_registry
    with Store(tmp_path) as store:
        service = Revisions(store, registry=blank_registry())
        state = dispatch(service, 'create', dict(name='Blank', setup='blank', scope_name='Home', population=None, land_area='0'), 'blank')
        result = page(service, query(state.context, 'conditions', scope_id='home'))
        assert [(r.id, r.condition.value.kind) for r in result.items] == [('land:value','quantity'),('population:value','unknown')]
        assert result.items[0].condition.value.value == '0'
        assert all(r.writer_id == 'player' for r in result.items)
        assert page(service, query(state.context, scope_id='home')).items == []


def test_one_shot_projection_validates_and_does_not_expose_paths(tmp_path):
    with Store(tmp_path) as store:
        context = seed(Revisions(store, registry=registry())).context
    command = [sys.executable, '-I', '-m', 'poliscope_engine.workspace', '--directory', str(tmp_path), '--operation', 'overview']
    result = subprocess.run(command, input=json.dumps(query(context))+'\n', text=True, capture_output=True)
    assert result.returncode == 0 and json.loads(result.stdout)['items']
    for data in [query(context) | dict(path='/private'), query(context, scope_id='foreign')]:
        result = subprocess.run(command, input=json.dumps(data)+'\n', text=True, capture_output=True)
        assert result.returncode == 1 and result.stdout == '' and result.stderr == ''


def test_collection_pagination_is_filtered_before_slicing_and_bound_to_all_query_fields(tmp_path):
    from overview_fixture import inputs
    from poliscope_engine.contracts.revisions import RevisionInputs
    with Store(tmp_path) as store:
        data = inputs().model_dump(mode='json')
        base = data['measurements'][0]
        data['goals'] = []
        data['measurements'] = [dict(base, id='indicator:' + str(i).zfill(3)) for i in range(63)]
        service = Revisions(store, registry=registry())
        root = seed(service, RevisionInputs.model_validate(data))
        first = page(service, query(root.context))
        assert len(first.items) == 25 and first.next_cursor
        second = page(service, query(root.context, cursor=first.next_cursor))
        third = page(service, query(root.context, cursor=second.next_cursor))
        assert len(second.items) == 25 and len(third.items) == 13 and third.next_cursor is None
        assert len({r.id for r in first.items + second.items + third.items}) == 63
        for changes in [dict(scope_id='region'), dict(all_scopes=True), dict(item_id=first.items[0].id), dict(collection='findings')]:
            with pytest.raises(ValueError): page(service, query(root.context, cursor=first.next_cursor) | changes)
        # A fork has the same report but a different read context.
        fork = service.change_branch(BranchRequest(revision_contract=1, operation_id='fork', context=root.context,
            expected_sequence=root.branch_sequence, action='fork', new_branch_id='fork', name='Fork'))
        with pytest.raises(ValueError): page(service, query(fork.context, cursor=first.next_cursor))


def test_qualitative_commitments_remain_separate_from_conditions_diagnostics_and_private_rationale(tmp_path):
    from poliscope_engine.workspace import dispatch, registry as blank_registry
    from poliscope_engine import interviews
    with Store(tmp_path) as store:
        service = Revisions(store, registry=blank_registry())
        state = dispatch(service, 'create', dict(name='Blank', setup='blank', scope_name='Home', population=None, land_area=None), 'blank')
        edit = dict(query=dict(context=state.context.model_dump(), scope_id='home', domain_id='domain:3'),
            choice_id='player:proposal', proposal='<b>Community assembly</b>', population=None, land_area=None,
            rationale='PRIVATE_RATIONALE_NOT_AN_OVERVIEW_VALUE')
        preview = interviews.stage(service, edit, 'choose')[3]
        confirmed = interviews.apply(service, dict(edit=edit, candidate_digest=preview.candidate_digest), 'choose')
        result = page(service, query(confirmed.state.context, 'policies', scope_id='home'))
        assert len(result.items) == 1 and result.items[0].kind == 'commitment'
        assert '<b>Community assembly</b>' in result.items[0].condition.value.value
        assert result.items[0].label == 'Collective decisions'
        assert 'PRIVATE_RATIONALE' not in result.model_dump_json()
        assert len(page(service, query(confirmed.state.context, 'conditions', scope_id='home')).items) == 2
        assert page(service, query(confirmed.state.context, scope_id='home')).items == []
