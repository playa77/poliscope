"""Independent deltas and persistent lineage through real SQLite and model-free reads."""
from decimal import getcontext
import pytest
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from poliscope_engine.contracts.revisions import PreviewRequest, ApplyRequest
from poliscope_engine.comparison import compare, lineage, action, retained, difference, rationale
from overview_fixture import seed, registry, inputs
from test_interviews import setup, edit
from poliscope_engine import interviews


def all_comparison(service, left, right):
    query = dict(context=left.model_dump(), other=right.model_dump(), cursor=None)
    rows, changes = [], []
    while True:
        reply = compare(service, query)
        rows.extend(reply.items); changes.extend(reply.changes)
        if not reply.next_cursor:
            return {r.id: r for r in rows}, changes
        query['cursor'] = reply.next_cursor


def accept(service, context, data, identity):
    preview = PreviewRequest(revision_contract=1, context=context,
        changes=[dict(kind='replace_inputs', inputs=data)], decision=dict(alternatives=[], selected_id=None, rationale_ref=None))
    candidate = service.preview(preview)
    return service.apply(ApplyRequest(revision_contract=1, operation_id=identity, preview=preview, candidate_digest=candidate.candidate_digest)).context


def move(service, context, kind, identity, **updates):
    return action(service, dict(context=context.model_dump(), expected_sequence=service.branch(context).sequence,
        action=kind, name=None, target_revision_id=None) | updates, identity)


def test_exact_deltas_and_no_execution_or_mutation_on_historical_reader(tmp_path, monkeypatch):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry())
        root = seed(service).context
        changed = inputs().model_dump()
        changed['design']['execution']['batch']['accounts'][-1]['opening'] = '250'
        head = accept(service, root, changed, 'second')
        reader = Revisions(store, registry=None)
        monkeypatch.setattr(reader, '_evaluate', lambda *a: pytest.fail('no recomputation'))
        before = service.catalogue()
        getcontext().prec = 2  # Authoritative comparisons use a fresh 28-digit context.
        try:
            rows, changes = all_comparison(reader, root, head)
        finally:
            getcontext().prec = 28
        assert rows['regional-reserve'].delta.value == '50'
        assert rows['local-reserve'].delta.value == '0'
        assert rows['status:1'].delta is None  # Partial is not zero or fully known.
        assert rows['status:2'].left.observation.value.kind == 'unknown'
        assert rows['regional-reserve'].left.origin == 'retained_evidence'
        assert rows['regional-reserve'].left.trace_state == 'complete'
        assert service.catalogue() == before
        backwards, _ = all_comparison(reader, head, root)
        assert backwards['regional-reserve'].delta.value == '-50'


@pytest.mark.parametrize('field,value', [('scope_id','east'), ('unit_id','people'), ('time_basis_id','year'),
    ('denominator_scope_id','east'), ('version','v2'), ('procedure','mean')])
def test_incompatible_definitions_explain_noncomparison(tmp_path, field, value):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry()); ctx = seed(service).context
        saved = service.evidence(ctx); record = service.read(ctx)
        left = retained(saved, 'regional-reserve')
        right = left.model_copy(update={'definition': left.definition.model_copy(update={field:value})})
        result = difference('regional-reserve', left, right, record, record, saved.evaluation, saved.evaluation)
        assert result.delta is None and 'Incompatible definition: ' + field in result.reasons


def test_model_identity_time_missing_and_trace_availability_are_separate(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry()); ctx = seed(service).context
        saved = service.evidence(ctx); record = service.read(ctx)
        left = retained(saved, 'regional-reserve')
        incomplete = left.model_copy(update={'trace_state':'incomplete'})
        assert difference('reserve', left, incomplete, record, record, saved.evaluation, saved.evaluation).delta.value == '0'
        missing = retained(saved, 'absent')
        assert difference('reserve', left, missing, record, record, saved.evaluation, saved.evaluation).delta is None
        other = saved.evaluation.model_copy(update={'identities':saved.evaluation.identities.model_copy(update={'model_digest':'sha256:'+'b'*64})})
        result = difference('reserve', left, left, record, record, saved.evaluation, other)
        assert result.delta is None and 'Incompatible executable model definitions' in result.reasons
        changed = left.model_copy(update={'observation':left.observation.model_copy(update={'effective_time':left.observation.effective_time.model_copy(update={'tick':1})})})
        assert 'Incompatible effective time' in difference('reserve', left, changed, record, record, saved.evaluation, saved.evaluation).reasons
        no_traces = saved.model_copy(update={'report':saved.report.model_copy(update={'traces':[]})})
        assert retained(no_traces, 'regional-reserve').trace_state == 'incomplete'


def test_real_undo_edit_retained_future_restore_historical_fork_rename_replay_and_reopen(tmp_path):
    store, service, root = setup(tmp_path)
    def apply(state, identity, population):
        change = edit(state, population=population)
        preview = interviews.stage(service, change, identity)[3]
        return interviews.apply(service, dict(edit=change, candidate_digest=preview.candidate_digest), identity).state
    first = apply(root, 'first', '125')
    undone = move(service, first.context, 'undo', 'undo')
    second = apply(undone, 'second', '150')
    futures = [b for b in service.catalogue() if b.context.branch_id.startswith('retained:')]
    assert len(futures) == 1 and futures[0].context.revision_id == first.context.revision_id
    page = lineage(service, dict(context=second.context.model_dump(), cursor=None))
    assert len(page.items) == 3
    archived = next(r for r in page.items if r.context.revision_id == first.context.revision_id)
    assert len(archived.alternatives) == 3 and all(a.wording for a in archived.alternatives)
    assert 'Original wording unavailable' not in archived.model_dump_json()
    note = rationale(service, dict(context=first.context.model_dump()))
    assert note.classification == 'private' and note.text == 'Private rationale canary'
    from poliscope_engine.evaluation.identity import digest
    private_path = tmp_path / 'private-interviews' / (digest(archived.rationale.id).split(':',1)[1] + '.json')
    private_path.unlink()
    missing_note = rationale(service, dict(context=first.context.model_dump()))
    assert missing_note.text is None and missing_note.reference.status == 'unavailable'
    assert rationale(service, dict(context=root.context.model_dump())).text is None
    assert archived.rationale.visibility == 'private' and 'Private rationale canary' not in page.model_dump_json()
    fork = move(service, second.context, 'fork', 'fork-old', target_revision_id=first.context.revision_id, name='Old experiment')
    assert fork.context.revision_id == first.context.revision_id and fork.context.branch_id == 'fork:fork-old'
    renamed = move(service, fork.context, 'rename', 'name', name='Named experiment')
    assert renamed.branch.name == 'Named experiment'
    query = dict(context=second.context.model_dump(), expected_sequence=service.branch(second.context).sequence,
        action='restore', target_revision_id=root.context.revision_id, name=None)
    restored = action(service, query, 'restore')
    assert action(service, query, 'restore') == restored
    assert restored.context.revision_id == root.context.revision_id
    assert any(b.context.revision_id == second.context.revision_id for b in service.catalogue())
    store.close()
    with Store(tmp_path) as reopened:
        reader = Revisions(reopened, registry=None)
        assert reader.branch(second.context).context == restored.context
        assert next(v.value.value for v in reader.read(first.context).inputs.values if v.id == 'population:value') == '125'
        assert next(v.value.value for v in reader.read(second.context).inputs.values if v.id == 'population:value') == '150'
        rows, changes = all_comparison(reader, first.context, second.context)
        assert any(c.id == 'population:value' and '125' in c.before and '150' in c.after for c in changes)


def test_comparison_cursor_bound_to_both_contexts_and_foreign_civilization_rejected(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry()); root = seed(service).context
        query = dict(context=root.model_dump(), other=root.model_dump(), cursor=None)
        page = compare(service, query)
        assert page.next_cursor
        with pytest.raises(ValueError):
            compare(service, dict(query, cursor=page.next_cursor, other=root.model_copy(update={'branch_id':'other'}).model_dump()))
        with pytest.raises(ValueError):
            compare(service, dict(query, other=root.model_copy(update={'civilization_id':'foreign'}).model_dump()))
        with pytest.raises(ValueError):
            compare(service, dict(query, cursor=page.next_cursor + '0'))


def test_precision_loss_is_labeled_instead_of_publishing_a_rounded_delta(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry()); ctx = seed(service).context
        saved = service.evidence(ctx); record = service.read(ctx)
        left = retained(saved, 'regional-reserve')
        right = left.model_copy(update={'observation':left.observation.model_copy(update={'value':left.observation.value.model_copy(update={'value':'1e28'})})})
        left = left.model_copy(update={'observation':left.observation.model_copy(update={'value':left.observation.value.model_copy(update={'value':'0.1'})})})
        result = difference('reserve', left, right, record, record, saved.evaluation, saved.evaluation)
        assert result.delta is None
        assert result.reasons == ['Difference exceeds supported numerical precision']
