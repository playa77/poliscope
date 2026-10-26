"""Independent procedural expectations for production interviews and history."""
import json
import pytest
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from poliscope_engine.contracts.revisions import HistoryQuery
from poliscope_engine.workspace import dispatch, registry
from poliscope_engine import interviews


def setup(directory):
    store = Store(directory)
    service = Revisions(store, registry=registry())
    state = dispatch(service, 'create', dict(name='Test', setup='blank', scope_name='Home', population=None, land_area=None), 'one')
    return store, service, state


def edit(state, domain='domain:1', **updates):
    return dict(query=dict(context=state.context.model_dump(), scope_id='home', domain_id=domain),
        choice_id='interview:domain-' + domain.split(':')[1] + '/option-1', proposal=None,
        population=None, land_area=None, rationale='Private rationale canary') | updates


def history(service, context):
    return service.history(HistoryQuery(context=context, cursor=None, limit=100)).items


def test_pure_preview_cancel_apply_full_alternatives_private_rationale_and_reopen(tmp_path):
    store, service, state = setup(tmp_path)
    changes = edit(state, population='125', land_area='2.50')
    before = history(service, state.context)
    staged, request, candidate, preview = interviews.stage(service, changes, 'operation')
    assert history(service, state.context) == before
    assert not (tmp_path / 'private-interviews').exists()
    assert preview.accounts == [] and len(preview.alternatives) == 3
    assert [v.value.kind for v in preview.before] == ['unknown', 'unknown']
    assert {v.id: v.value.value for v in preview.after} == {'population:value': '125', 'land:value': '2.50'}
    result = interviews.apply(service, dict(edit=changes, candidate_digest=preview.candidate_digest), 'operation')
    assert result.status == 'applied'
    assert len(history(service, state.context)) == len(before) + 1
    record = service.read(result.state.context)
    assert len(record.decision.alternatives) == 3
    assert record.decision.selected_id == changes['choice_id']
    assert record.decision.rationale_ref.visibility == 'private'
    assert 'Private rationale canary' not in record.model_dump_json()
    assert 'Private rationale canary' not in service.evidence(result.state.context).model_dump_json()
    files = list((tmp_path / 'private-interviews').glob('*.json'))
    assert len(files) == 1 and json.loads(files[0].read_text())['classification'] == 'private'
    assert len(files[0].stem) == 64 and set(files[0].stem) <= set('0123456789abcdef')
    assert json.loads(files[0].read_text())['text'] == changes['rationale']
    assert record.inputs.design.policies == [] and record.inputs.goals == []
    assert not record.inputs.design.execution.dependencies.instances
    # Replaying after a lost reply retains exactly one revision and one note.
    assert interviews.apply(service, dict(edit=changes, candidate_digest=preview.candidate_digest), 'operation') == result
    assert len(history(service, state.context)) == 2
    store.close()
    with Store(tmp_path) as reopened:
        service = Revisions(reopened, registry=registry())
        assert interviews.question(service, dict(changes['query'], context=result.state.context.model_dump())).current_commitment
        assert service.read(state.context).inputs.values[0].value.kind == 'unknown'
        assert len(history(service, result.state.context)) == 2


def test_stale_candidate_cannot_overwrite_new_head(tmp_path):
    store, service, state = setup(tmp_path)
    first, second = edit(state, population='1'), edit(state, population='2')
    p1 = interviews.stage(service, first, 'one')[3]
    p2 = interviews.stage(service, second, 'two')[3]
    confirmed = interviews.apply(service, dict(edit=first, candidate_digest=p1.candidate_digest), 'one')
    stale = interviews.apply(service, dict(edit=second, candidate_digest=p2.candidate_digest), 'two')
    assert stale.status == 'stale' and stale.state.context == confirmed.state.context
    assert len(history(service, state.context)) == 2
    assert len(list((tmp_path / 'private-interviews').glob('*.json'))) == 1
    # A completed operation replays even when its original base is now old.
    assert interviews.apply(service, dict(edit=first, candidate_digest=p1.candidate_digest), 'one') == confirmed
    store.close()


@pytest.mark.parametrize('updates', [dict(population='1.5'), dict(population='NaN'), dict(land_area='-1'),
    dict(choice_id='arbitrary:code'), dict(proposal='unexpected'), dict(choice_id='player:proposal', proposal=' '),
    dict(query=dict(context={}, scope_id='home', domain_id='domain:1'))])
def test_invalid_drafts_never_write(tmp_path, updates):
    store, service, state = setup(tmp_path)
    with pytest.raises(ValueError):
        interviews.stage(service, edit(state, **updates), 'one')
    assert len(history(service, state.context)) == 1
    store.close()


def test_every_domain_works_without_dependencies_and_hostile_prose_stays_data(tmp_path):
    store, service, state = setup(tmp_path)
    for domain in range(1, 13):
        data = edit(state, domain='domain:' + str(domain), rationale='')
        q = interviews.question(service, data['query'])
        assert len(q.options) == 3 and q.definition.source_refs == ['interview:source/conventions']
        assert q.definition.evidence == 'hypothetical'
        assert interviews.stage(service, data, 'one')[3].accounts == []
    text = '<script>throw new Error("executed")</script> $(touch /tmp/should-not-exist)'
    data = edit(state, 'domain:3', choice_id='player:proposal', proposal=text, rationale='')
    candidate = interviews.stage(service, data, 'proposal')[3]
    assert len(candidate.alternatives) == 4
    result = interviews.apply(service, dict(edit=data, candidate_digest=candidate.candidate_digest), 'proposal')
    q = interviews.question(service, dict(data['query'], context=result.state.context.model_dump()))
    metadata = json.loads(q.current_commitment)
    assert metadata['option']['original_text'] == text
    assert metadata['option']['origin'] == 'player_proposed'
    assert not service.read(result.state.context).inputs.design.policies
    store.close()


def test_explicit_zero_unknown_and_scope_failures(tmp_path):
    store, service, state = setup(tmp_path)
    data = edit(state, population='0', land_area=None)
    preview = interviews.stage(service, data, 'zero')[3]
    rows = {v.id: v.value for v in preview.after}
    assert rows['population:value'].value == '0' and rows['land:value'].kind == 'unknown'
    for field, token in [('scope_id', 'foreign'), ('domain_id', 'domain:13')]:
        with pytest.raises(ValueError):
            interviews.question(service, data['query'] | {field: token})
    with pytest.raises(ValueError):
        interviews.stage(service, edit(state, 'domain:3', population='4'), 'unexpected')
    with pytest.raises(ValueError):
        interviews.apply(service, dict(edit=data, candidate_digest='sha256:' + '0'*64), 'zero')
    assert len(history(service, state.context)) == 1
    store.close()


def test_private_payload_write_is_atomic_retryable_and_absent_from_operation_binding(tmp_path, monkeypatch):
    store, service, state = setup(tmp_path)
    data = edit(state, proposal='界' * 1024, choice_id='player:proposal', rationale='private canary ' * 100)
    preview = interviews.stage(service, data, 'atomic')[3]
    original = service.apply
    monkeypatch.setattr(service, 'apply', lambda request: (_ for _ in ()).throw(RuntimeError('fault before commit')))
    with pytest.raises(RuntimeError):
        interviews.apply(service, dict(edit=data, candidate_digest=preview.candidate_digest), 'atomic')
    assert len(history(service, state.context)) == 1
    private = list((tmp_path / 'private-interviews').glob('*.json'))
    assert len(private) == 1
    monkeypatch.setattr(service, 'apply', original)
    accepted = interviews.apply(service, dict(edit=data, candidate_digest=preview.candidate_digest), 'atomic')
    assert accepted.status == 'applied' and len(history(service, state.context)) == 2
    rows = store._connection.execute('SELECT binding,outcome FROM operations').fetchall()
    assert all('private canary' not in value for row in rows for value in row)
    assert len(list((tmp_path / 'private-interviews').glob('*.json'))) == 1
    assert not list((tmp_path / 'private-interviews').glob('.pending-*'))
    # Same operation ID cannot silently replay a request with a changed rationale.
    with pytest.raises(ValueError):
        interviews.apply(service, dict(edit=data | dict(rationale='changed'), candidate_digest=preview.candidate_digest), 'atomic')
    store.close()


def test_condition_editor_cannot_claim_another_writer_state(tmp_path):
    from poliscope_engine.contracts.revisions import PreviewRequest, ApplyRequest
    from poliscope_engine.workspace import select
    store, service, state = setup(tmp_path)
    inputs = service.read(state.context).inputs.model_dump(mode='json')
    inputs['owners'][0]['writer_id'] = 'engine'
    request = PreviewRequest.model_validate(dict(revision_contract=1, context=state.context.model_dump(),
        changes=[dict(kind='replace_inputs', inputs=inputs)],
        decision=dict(alternatives=[], selected_id=None, rationale_ref=None)))
    candidate = service.preview(request)
    service.apply(ApplyRequest(revision_contract=1, operation_id='owner', preview=request, candidate_digest=candidate.candidate_digest))
    current = select(service, dict(civilization_id=state.context.civilization_id, branch_id='main', revision_id=None))
    with pytest.raises(ValueError, match='condition_not_player_editable'):
        interviews.stage(service, edit(current, population='1'), 'forbidden')
    assert len(history(service, current.context)) == 2
    store.close()


def test_assistant_excerpt_promotion_is_pure_qualitative_and_retains_only_explicit_content(tmp_path):
    store, service, state = setup(tmp_path)
    try:
        promotion = dict(source_request_id='turn-id', manifest_digest='sha256:'+'a'*64,
                         coverage='unverified qualitative assistant excerpt')
        changes = edit(state, domain='domain:3', choice_id='player:proposal',
                       proposal='Public selected alternative', rationale='', promotion=promotion)
        before = '\n'.join(store._connection.iterdump())
        preview = interviews.stage(service, changes, 'promotion')[3]
        assert '\n'.join(store._connection.iterdump()) == before
        result = interviews.apply(service, dict(edit=changes, candidate_digest=preview.candidate_digest), 'promotion')
        assert result.status == 'applied'
        assert interviews.apply(service, dict(edit=changes, candidate_digest=preview.candidate_digest), 'promotion') == result
        record = service.read(result.state.context)
        commitment = next(v for v in record.inputs.values if v.property_id == 'interview:commitment')
        metadata = json.loads(commitment.value.value)
        assert metadata['option']['origin'] == 'ai_proposed'
        assert metadata['option']['original_text'] == changes['proposal']
        assert metadata['promotion'] == promotion
        assert 'Private rationale canary' not in record.model_dump_json()
        assert not record.inputs.design.policies and not record.inputs.design.execution.dependencies.instances
        assert not (tmp_path/'private-interviews').exists()
        assert len(history(service, result.state.context)) == 2
    finally:
        store.close()


def test_assistant_promotion_cannot_label_an_authored_option_or_claim_supported_coverage(tmp_path):
    store, service, state = setup(tmp_path)
    try:
        receipt = dict(source_request_id='turn', manifest_digest='sha256:'+'a'*64,
                       coverage='unverified qualitative assistant excerpt')
        with pytest.raises(ValueError):
            interviews.stage(service, edit(state, promotion=receipt), 'forged')
        with pytest.raises(ValueError):
            interviews.stage(service, edit(state, choice_id='player:proposal', proposal='Text',
                promotion=receipt | {'coverage':'scientifically validated'}), 'forged')
        assert len(history(service, state.context)) == 1
    finally:
        store.close()
