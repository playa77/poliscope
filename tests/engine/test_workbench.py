"""Synthetic retained evidence, revision isolation and classified history canaries."""
import json
import pytest
from poliscope_engine import workbench, private_notes, overview, matrix
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from poliscope_engine.contracts.revisions import RevisionInputs
from poliscope_engine.workspace import dispatch, registry
from headless_fixture import inputs, registry as finite_registry, create, quantity


def query(context, collection='notes', scope='home', **rest):
    return dict(context=context, scope_id=scope, collection=collection, **rest)


def edit(context, change, scope='home'):
    return dict(context=context, scope_id=scope, change=change)


def commit(service, data, identity):
    preview = workbench.preview(service, data, identity)
    outcome = workbench.apply(service, dict(edit=data, candidate_digest=preview.candidate_digest), identity)
    return preview, outcome


def blank(service):
    return dispatch(service, 'create', dict(name='Evidence', setup='blank', scope_name='Home', population='12', land_area='3'), 'create').context


def note(text, identity=None, kind='inquiry'):
    return dict(kind='note', id=identity, note_kind=kind, text=text)


def workbench_registry():
    from poliscope_engine.mechanisms import MechanismRegistry
    r = finite_registry()
    return MechanismRegistry(model=r.model, units=r.units, times=r.times,
        source_ids=r.source_ids, assumption_ids=['need'], fixture_ids=r.fixture_ids,
        implementations=r.implementations, reviews=r.reviews, definitions=r.definitions)


def finite(service):
    raw = inputs().model_dump(mode='json')
    raw['design']['execution']['dependencies']['fixed_inputs'] = [x for x in raw['design']['execution']['dependencies']['fixed_inputs'] if x['consumer']['instance_id'] != 'a']
    raw['design']['assumption_inputs'] = [dict(consumer=dict(instance_id='a', port_id='synthetic:need'), value_id='need')]
    raw['assumptions'] = [dict(id='need', value=quantity(80))]
    raw['measurements'][0]['assumption_refs'] = ['need']
    raw['references'] = [dict(id='need', kind='assumption', visibility='public', availability='available', description='Synthetic request; no empirical interpretation',
        assumption=dict(id='need', scope_id='east', definition_id='synthetic:need', definition_version='v1', origin='player_input',
            uncertainty_form='point', uncertainty_definition_ref=None, rationale='Synthetic request only', source_refs=[]))]
    return create(service, RevisionInputs.model_validate(raw)).context


def test_private_notes_edit_history_deletion_derivatives_and_standalone_projection(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry())
        base = blank(service)
        old_physics = service.evidence(base).report.physical_output_digest
        data = edit(base, note('PRIVATE_CANARY_OLD: expect a different outcome', kind='expectation'))
        # Preview is pure, including the active private store.
        preview = workbench.preview(service, data, 'first')
        assert not (tmp_path / 'private-notes').exists()
        assert service.branch(base).context == base
        first = workbench.apply(service, dict(edit=data, candidate_digest=preview.candidate_digest), 'first')
        assert workbench.apply(service, dict(edit=data, candidate_digest=preview.candidate_digest), 'first') == first
        ref = service.read(first.state.context).inputs.notes[0]
        second_preview, second = commit(service, edit(first.state.context, note('PRIVATE_CANARY_NEW: observation', ref.id, 'observation')), 'second')
        assert preview.physical_after == second_preview.physical_after == old_physics
        reader = Revisions(store, registry=None)
        assert workbench.page(reader, query(first.state.context)).items[0].text.startswith('PRIVATE_CANARY_OLD')
        assert workbench.page(reader, query(second.state.context)).items[0].text.startswith('PRIVATE_CANARY_NEW')
        assert not workbench.page(reader, query(base)).items
        records = [service.read(c) for c in (base, first.state.context, second.state.context)]
        evidences = [service.evidence(c) for c in (base, first.state.context, second.state.context)]
        for record, evidence in zip(records, evidences):
            assert 'PRIVATE_CANARY' not in record.model_dump_json() + evidence.model_dump_json()
        all_sql = '\n'.join(store._connection.iterdump())
        assert 'PRIVATE_CANARY' not in all_sql  # Includes exact operation bindings and history chunks.
        projected = private_notes.project_history(records, evidences)
        projection = json.dumps(projected)
        assert 'PRIVATE_CANARY' not in projection and ref.id not in projection and ref.version not in projection
        assert all(h['evidence']['report']['physical_output_digest'] == old_physics for h in projected['history'])
        assert projected['projection_digest'] != records[-1].evidence_digest
        location = private_notes.location(service, base, ref.id)
        (location / 'derivatives').mkdir()
        (location / 'derivatives' / 'old-index.json').write_text('PRIVATE_CANARY_DERIVED')
        request = dict(context=second.state.context, scope_id='home', id=ref.id)
        assert workbench.delete(reader, request).status == 'deleted'
        assert workbench.delete(reader, request).status == 'deleted'
        for context in (first.state.context, second.state.context):
            row, = workbench.page(reader, query(context)).items
            assert row.status == 'deleted' and row.text is None and row.note_kind is None
        assert not (location / 'payloads').exists() and not (location / 'derivatives').exists()
        assert service.read(second.state.context) == records[-1]
        assert service.evidence(second.state.context) == evidences[-1]
        with pytest.raises(ValueError, match='note_deleted'):
            commit(service, edit(second.state.context, note('resurrect', ref.id)), 'third')


def test_assumption_preview_exact_changes_comparison_and_historical_definition(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=workbench_registry())
        base = finite(service)
        row, = workbench.page(service, query(base, 'assumptions', 'east')).items
        assert row.editable and row.definition.definition_version == 'v1'
        old = service.evidence(base)
        assert old.report.measurements[0].value.value == '60'  # 100 stock minus the other claim's 40 hold
        preview, accepted = commit(service, edit(base, dict(kind='assumption', id='need', value=quantity(20)), 'east'), 'need')
        new = service.evidence(accepted.state.context)
        assert new.report.measurements[0].value.value == '20'
        assert preview.physical_before != preview.physical_after and preview.changed_observations > 0
        assert old.report.measurements[0].value.value == '60'  # 100 stock minus the other claim's 40 hold
        reader = Revisions(store, registry=None)
        rows = workbench.page(reader, query(base, 'references', 'east')).items
        assert next(r.reference.assumption for r in rows if r.reference.kind == 'assumption').definition_version == 'v1'
        assert matrix.model(reader, dict(context=base, kind='mechanism', identity='synthetic:demand')).status == 'retained'
        assert workbench.page(reader, query(base, 'models', 'east')).items
        from poliscope_engine import comparison
        compared = comparison.compare(reader, dict(context=base, other=accepted.state.context, cursor=None))
        assert any(r.left.observation and r.right.observation and r.left.observation.value != r.right.observation.value for r in compared.items)
        for change in [dict(kind='assumption',id='missing',value=quantity(3)),
                dict(kind='assumption',id='need',value=quantity(3) | dict(unit_id='hours')),
                dict(kind='assumption',id='need',value=dict(kind='label',value='unsupported range'))]:
            with pytest.raises(ValueError):
                workbench.preview(service, edit(accepted.state.context, change, 'east'), 'bad')
        with pytest.raises(ValueError, match='unsupported_assumption'):
            workbench.preview(service, edit(accepted.state.context, dict(kind='assumption',id='need',value=quantity(3)), 'west'), 'bad')


def test_persisted_typed_goals_scoped_physics_isolation_updates_and_removal(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=workbench_registry())
        base = finite(service)
        assert not service.read(base).inputs.goals
        goal = dict(id='target',kind='comparison',question='Does output reach 90 kg?',indicator_id='east-output',operation='ge',threshold=quantity(90))
        preview, first = commit(service, edit(base, dict(kind='goal',goal=goal), 'east'), 'goal1')
        assert preview.physical_before == preview.physical_after
        row, = workbench.page(service, query(first.state.context, 'goals', 'east')).items
        assert row.observation.matched is False
        assert not workbench.page(service, query(first.state.context, 'goals', 'west')).items
        _, second = commit(service, edit(first.state.context, dict(kind='goal',goal=goal | dict(threshold=quantity(50))), 'east'), 'goal2')
        row, = workbench.page(service, query(second.state.context, 'goals', 'east')).items
        assert row.observation.matched is True
        assert service.evidence(first.state.context).evaluation == service.evidence(second.state.context).evaluation == service.evidence(base).evaluation
        observed, = overview.page(service, dict(context=second.state.context,scope_id='east',collection='goals',item_id=None,cursor=None,all_scopes=False)).items
        assert observed.observation == row.observation
        _, removed = commit(service, edit(second.state.context, dict(kind='goal',goal=goal,remove=True), 'east'), 'remove')
        assert not service.read(removed.state.context).inputs.goals
        assert len(service.read(first.state.context).inputs.goals) == 1
        with pytest.raises(ValueError, match='goal_metadata'):
            workbench.preview(service, edit(removed.state.context, dict(kind='goal',goal=goal | dict(threshold=quantity(4) | dict(unit_id='hours'))), 'east'), 'bad')


@pytest.mark.parametrize('kind', ['inquiry', 'expectation', 'observation', 'model_gap', 'proposal'])
def test_all_note_kinds_remain_qualitative_and_model_unavailable_reads(tmp_path, kind):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry())
        base = blank(service)
        preview, accepted = commit(service, edit(base, note('Multiply population by 100; proposed only', kind=kind)), kind)
        assert preview.physical_before == preview.physical_after
        assert accepted.state.mechanism_count == 0 and accepted.state.goal_count == 0
        reader = Revisions(store, registry=None)
        assert workbench.page(reader, query(accepted.state.context)).items[0].note_kind == kind
        assert service.read(base).inputs.values == service.read(accepted.state.context).inputs.values


def test_stale_preview_rejected_exact_retry_no_partial_history_and_payload_binding(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry())
        base = blank(service)
        stale = edit(base, note('not committed'))
        preview = workbench.preview(service, stale, 'stale')
        _, winner = commit(service, edit(base, note('winner')), 'winner')
        outcome = workbench.apply(service, dict(edit=stale,candidate_digest=preview.candidate_digest), 'stale')
        assert outcome.status == 'stale' and outcome.state.context == winner.state.context
        assert not private_notes.location(service, base, 'note:stale').exists()
        with pytest.raises(ValueError, match='candidate_digest'):
            workbench.apply(service, dict(edit=stale,candidate_digest='sha256:'+'0'*64), 'stale')
        with pytest.raises(ValueError):
            workbench.page(service, query(winner.state.context, scope='unknown'))
        with pytest.raises(ValueError):
            workbench.delete(service, dict(context=winner.state.context,scope_id='home',id='foreign'))


def test_bounded_pages_cursor_binding_corrupt_payload_and_missing_payload(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry())
        context = blank(service)
        # Twenty-six narrative goals exercise real paged storage without private text.
        for i in range(26):
            goal = dict(id=f'goal:{i:02d}',kind='narrative',question='Why?',indicator_id=None,operation=None,threshold=None)
            _, accepted = commit(service, edit(context,dict(kind='goal',goal=goal)), str(i))
            context = accepted.state.context
        page = workbench.page(service, query(context, 'goals'))
        assert len(page.items) == 25 and page.next_cursor
        assert len(workbench.page(service, query(context, 'goals', cursor=page.next_cursor)).items) == 1
        for cursor in [page.next_cursor + '1', 'sha256:'+'0'*64+':25']:
            with pytest.raises(ValueError): workbench.page(service, query(context, 'goals', cursor=cursor))
        with pytest.raises(ValueError): workbench.page(service, query(context, 'notes', cursor=page.next_cursor))
        _, accepted = commit(service, edit(context,note('private')), 'note')
        ref = service.read(accepted.state.context).inputs.notes[0]
        location = private_notes.location(service, context, ref.id)
        file, = (location / 'payloads').iterdir()
        file.write_text('{malformed')
        assert workbench.page(service, query(accepted.state.context)).items[0].status == 'unavailable'
        file.unlink()
        assert workbench.page(service, query(accepted.state.context)).items[0].status == 'unavailable'


def test_private_rationale_history_projection_and_active_deletion(tmp_path):
    from test_interviews import setup, edit as interview_edit
    from poliscope_engine import interviews, comparison
    store, service, state = setup(tmp_path)
    try:
        data = interview_edit(state, rationale='PRIVATE_RATIONALE_CANARY')
        preview = interviews.stage(service, data, 'rationale')[3]
        outcome = interviews.apply(service, dict(edit=data, candidate_digest=preview.candidate_digest), 'rationale')
        context = outcome.state.context
        record, evidence = service.read(context), service.evidence(context)
        row, = workbench.page(service, query(context, 'rationale')).items
        assert row.text == 'PRIVATE_RATIONALE_CANARY' and row.rationale.visibility == 'private'
        projected = json.dumps(private_notes.project_history([record], [evidence]))
        assert row.id not in projected and 'PRIVATE_RATIONALE' not in projected
        before = evidence.report.physical_output_digest
        workbench.delete(service, dict(context=context, scope_id='home', id=row.id))
        reply = comparison.rationale(service, dict(context=context))
        assert reply.reference.status == 'deleted' and reply.text is None
        assert service.evidence(context).report.physical_output_digest == before
        assert not list((tmp_path / 'private-interviews').glob('*.json'))
    finally:
        store.close()


def test_retained_source_revision_cannot_silently_switch_to_current_bundle(tmp_path, monkeypatch):
    from test_atlas import setup, edit as interview_edit, apply as interview_apply
    from poliscope_engine import atlas
    store, service, state = setup(tmp_path)
    try:
        # Source-backed choice retains the exact source descriptor in its closure.
        from test_atlas import all_rows, query as atlas_query
        source_row = next(r for r in all_rows(service, atlas_query(state)) if r.question.id == 'society:DEC-001')
        data = interview_edit(state, choice_id=source_row.options[0].id, rationale='') | dict(query=source_row.interview.model_dump())
        current = interview_apply(service, data, 'source')
        source_id = source_row.question.source_refs[0]
        original = atlas.source(service, dict(context=current.context, source_ref=source_id))
        catalogs = atlas.catalogs
        def amended(release):
            domains, packs = catalogs(release)
            changed = []
            for pack in packs:
                sources = [s.model_copy(update={'reference': s.reference.model_copy(update={'revision_id': 'different-revision'})})
                    if s.reference.id == source_id else s for s in pack.sources]
                changed.append(pack.model_copy(update={'sources': sources}))
            return domains, changed
        monkeypatch.setattr(atlas, 'catalogs', amended)
        with pytest.raises(ValueError, match='archived_source_unavailable'):
            atlas.source(service, dict(context=current.context, source_ref=source_id))
        assert original.source.reference.revision_id != 'different-revision'
    finally:
        store.close()


def test_retained_declarative_formula_is_readable_without_current_model(tmp_path):
    from test_expressions import setup as graph_setup
    from test_revisions import inputs as revision_inputs
    from test_dependencies import request
    from test_evaluation import design
    from poliscope_engine.contracts.revisions import CreateRequest
    r, expected = graph_setup()
    from poliscope_engine.mechanisms import MechanismRegistry, Review, declaration_digest
    second = r.definitions[0].model_copy(update={'version': 'v2'})
    r = MechanismRegistry(model=r.model, units=r.units, times=r.times, source_ids=r.source_ids,
        fixture_ids=r.fixture_ids, implementations=r.implementations, definitions=[*r.definitions, second], graphs=r.graphs,
        reviews=[*r.reviews, Review(declaration_digest(second), *r.model, 'synthetic:evidence', 'synthetic:fixture', r.reviews[0].graph_digest)])
    raw = revision_inputs().model_dump(mode='json')
    definition = r.definitions[0]
    raw['design'] = design(request(('a',), definition, fixed_inputs=[dict(
        consumer=dict(instance_id='a', port_id='synthetic:x'), value=quantity('1.25'))])).model_dump(mode='json')
    with Store(tmp_path) as store:
        writer = Revisions(store, registry=r)
        context = writer.create(CreateRequest(revision_contract=1, data_store_id=writer.data_store_id,
            civilization_id='civ',branch_id='main',name='Formula',operation_id='formula',inputs=raw)).context
        reader = Revisions(store, registry=None)
        assert matrix.model(reader, dict(context=context,kind='mechanism',identity=definition.id)).status == 'unavailable'
        assert matrix.model(reader, dict(context=context,kind='mechanism',identity=definition.id,version='v2')).mechanism.version == 'v2'
        result = matrix.model(reader, dict(context=context,kind='mechanism',identity=definition.id,version='v1'))
        from poliscope_engine.evaluation.identity import digest
        assert len(result.expression_graphs) == 1 and digest(result.expression_graphs[0]) == digest(expected)
        assert next(n for n in result.expression_graphs[0].nodes if n.kind == 'operator').operator.id == 'add'
        assert next(o.value.value for o in reader.evidence(context).evaluation.observations if o.node[0] == 'output') == '3.75'


def test_interrupted_private_deletion_hides_all_versions_before_retry_cleanup(tmp_path, monkeypatch):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry())
        base = blank(service)
        _, accepted = commit(service, edit(base, note('PRIVATE_INTERRUPT_CANARY')), 'interrupt')
        ref = service.read(accepted.state.context).inputs.notes[0]
        target = private_notes.location(service, base, ref.id)
        original = private_notes.shutil.rmtree
        def interrupt(path):
            raise OSError('synthetic interruption after tombstone')
        monkeypatch.setattr(private_notes.shutil, 'rmtree', interrupt)
        request = dict(context=accepted.state.context,scope_id='home',id=ref.id)
        with pytest.raises(OSError):
            workbench.delete(service, request)
        assert (target / 'payloads').exists()
        row, = workbench.page(service, query(accepted.state.context)).items
        assert row.status == 'deleted' and row.text is None
        monkeypatch.setattr(private_notes.shutil, 'rmtree', original)
        workbench.delete(service, request)
        assert not (target / 'payloads').exists()
