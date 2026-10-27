"""Scaled production admission and cooperative aborts preserve accepted history."""
import hashlib
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from poliscope_engine.ingestion import decode_chunks, IngestionError
from poliscope_engine.contracts.revisions import CreateRequest, PreviewRequest, ApplyRequest
from poliscope_engine.revisions import Revisions, graph
from poliscope_engine.storage import Store
from poliscope_engine.work_limits import WorkLimits, WorkStopped, limited
from poliscope_engine.evaluation import evaluate
from scripts.coupled_scale_fixture import fixture, verify
import headless_fixture


def chunks(value):
    payload = value.model_dump_json().encode()
    return [payload[i:i+128000] for i in range(0,len(payload),128000)], hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize('name', ['classroom-v1', 'exploratory-v1'])
def test_scaled_admission_evaluation_and_integer_oracle(name):
    counts=json.loads(Path('docs/roadmap/execution/benchmarks.json').read_text())['fixtures'][name]
    host, data, expected=fixture(counts)
    request=CreateRequest(revision_contract=1,data_store_id='store',civilization_id='scale:civ',branch_id='main',name='Synthetic',operation_id='create',inputs=data)
    parts, checksum=chunks(request)
    admitted=decode_chunks(parts,expected_sha256=checksum,model=CreateRequest)
    assert admitted == request
    result=evaluate(graph(admitted.inputs,'scale:civ'), data.design, (), host.model, registry=host)
    verify(result,expected)
    assert len(data.relationships)==counts['active_typed_edges']
    assert len(data.design.execution.dependencies.instances)==counts['decision_instances']
    assert len({d.domain for d in host.definitions})==12


@pytest.mark.parametrize('mode', ['wrong_hash','reordered','oversized','cancelled','duplicate','total_bytes'])
def test_ingestion_failures_never_publish(mode, tmp_path, monkeypatch):
    import poliscope_engine.ingestion as ingestion
    with Store(tmp_path) as store:
        service=Revisions(store,registry=headless_fixture.registry())
        data=CreateRequest(revision_contract=1,data_store_id=service.data_store_id,civilization_id='civ',branch_id='main',name='Synthetic',operation_id='create',inputs=headless_fixture.inputs())
        parts, checksum=chunks(data)
        cancelled=None
        if mode=='wrong_hash': checksum='0'*64
        if mode=='reordered':
            payload=b''.join(parts); parts=[payload[100:],payload[:100]]
        if mode=='oversized': parts=[b' '*524289]
        if mode=='cancelled': cancelled=lambda: True
        if mode=='duplicate':
            parts=[b'{"revision_contract":1,"revision_contract":1}'];checksum=hashlib.sha256(parts[0]).hexdigest()
        if mode=='total_bytes': monkeypatch.setattr(ingestion,'MAX_INPUT_BYTES',1)
        with pytest.raises(IngestionError):
            service.create_chunks(parts,expected_sha256=checksum,cancelled=cancelled)
        assert service.catalogue()==[]


def test_quotas_and_cancellation_preserve_head_and_idempotent_apply(tmp_path):
    with Store(tmp_path) as store:
        service=Revisions(store,registry=headless_fixture.registry())
        initial=headless_fixture.create(service)
        original=service.evidence(initial.context)
        request=headless_fixture.preview(initial.context,headless_fixture.inputs())
        candidate=service.preview(request)
        apply=ApplyRequest(revision_contract=1,operation_id='apply',preview=request,candidate_digest=candidate.candidate_digest)
        # Abort after writes have been staged, before confirming the operation.
        def progress(stage):
            if stage=='confirming': raise WorkStopped('work_cancelled')
        service.limits=WorkLimits(progress=progress)
        with pytest.raises(WorkStopped,match='work_cancelled'): service.apply(apply)
        assert service.branch(initial.context).context==initial.context
        assert service.status('apply',apply) is None
        assert service.evidence(initial.context)==original
        service.limits=WorkLimits(snapshot_bytes=1)
        with pytest.raises(WorkStopped,match='byte_quota'): service.preview(request)
        service.limits=None
        accepted=service.apply(apply)
        assert service.apply(apply)==accepted
        assert service.evidence(initial.context)==original
        # Complete cache hits still obey cancellation and cannot publish.
        service.limits=WorkLimits(cancelled=lambda:True)
        with pytest.raises(WorkStopped,match='work_cancelled'): service.preview(request)


def test_deadline_stops_inside_solver_and_context_is_reset():
    times=iter([0,0,0,0,0,2])
    limits=WorkLimits(seconds=1,clock=lambda:next(times,2))
    host=headless_fixture.registry();data=headless_fixture.inputs()
    with pytest.raises(WorkStopped,match='time_quota'):
        with limited(limits): evaluate(graph(data,'civ'),data.design,(),host.model,registry=host)
    assert evaluate(graph(data,'civ'),data.design,(),host.model,registry=host).outcome=='insufficient'


def test_indexed_world_lookup_is_detached_and_serialization_preserved():
    from copy import deepcopy
    from dataclasses import asdict
    from poliscope_engine.evaluation.identity import digest
    from poliscope_engine.world import WorldError
    data=headless_fixture.inputs()
    world=graph(data,'civ').registry
    canonical=asdict(world)
    entity=world.entity('water')
    entity.provenance.source_refs.append('mutated')
    assert world.entity('water').provenance.source_refs==[]
    assert asdict(deepcopy(world))==canonical
    assert digest(world)==digest(canonical)
    assert not any('index' in key for key in canonical)
    with pytest.raises(WorldError,match='missing_entity'):world.entity('absent')


def test_unsupported_scaled_feedback_stays_explicitly_unresolved():
    counts=dict(scopes=4,cohorts=4,assets=4,decision_instances=16,active_typed_edges=24)
    host,data,expected=fixture(counts)
    design=data.design.model_copy(update={'execution':data.design.execution.model_copy(update={'solvers':[]})})
    result=evaluate(graph(data,'scale:civ'),design,(),host.model,registry=host)
    assert result.outcome=='unresolved'
    assert all(o.reason=='missing_solver' for o in result.observations if o.node[1].startswith('scale:feedback:'))
    assert result.accounts is None


def test_chunked_large_revision_replay_pages_and_migration_recovery(tmp_path):
    from poliscope_engine.contracts.world import WorldInspectParams
    from poliscope_engine.contracts.recovery import ModelMigration
    from poliscope_engine.storage.store import StorageError
    counts=dict(scopes=4,cohorts=4,assets=4,decision_instances=16,active_typed_edges=4000)
    host,data,expected=fixture(counts)
    with Store(tmp_path) as store:
        service=Revisions(store,registry=host)
        request=CreateRequest(revision_contract=1,data_store_id=service.data_store_id,civilization_id='scale:civ',branch_id='main',name='Large chunks',operation_id='create',inputs=data)
        assert len(request.model_dump_json().encode())>1048576
        parts,checksum=chunks(request)
        opened=service.create_chunks(parts,expected_sha256=checksum)
        assert service.create_chunks(parts,expected_sha256=checksum)==opened
        assert service.status('create',request)==opened
        verify(service.evidence(opened.context).evaluation,expected)
        q=WorldInspectParams(world_schema=1,context=opened.context,collection='relationships',cursor=None,limit=100)
        page=service.inspect(q)
        assert len(page.page.items)==100 and page.page.next_cursor
        assert len(page.model_dump_json().encode())<1048576
        changed=request.model_copy(update={'name':'Different payload'})
        with pytest.raises(StorageError):service.create(changed)
        migration=ModelMigration(operation_id='migrate',context=opened.context,new_branch_id='migrated',name='Synthetic migration',inputs=data)
        migrated=service.migrate_model(migration)
        service.registry=None
        assert service.migration_status(opened.context,'migrate','migrated','Synthetic migration')==migrated
        with pytest.raises(ValueError,match='binding_mismatch'):
            service.migration_status(opened.context,'migrate','foreign','Synthetic migration')


def test_workspace_quota_response_is_typed_and_contains_no_private_diagnostic(monkeypatch,tmp_path):
    from io import BytesIO
    from types import SimpleNamespace
    from poliscope_engine import workspace
    from poliscope_engine.contracts.workspace import WorkFailure
    def stopped(*args):raise WorkStopped('work_snapshot_byte_quota')
    monkeypatch.setattr(workspace,'dispatch',stopped)
    monkeypatch.setattr(sys,'argv',['workspace','--directory',str(tmp_path),'--operation','catalogue'])
    output=BytesIO()
    monkeypatch.setattr(sys,'stdin',SimpleNamespace(buffer=BytesIO(b'{}\n')))
    monkeypatch.setattr(sys,'stdout',SimpleNamespace(buffer=output))
    assert workspace.main()==0
    assert WorkFailure.model_validate_json(output.getvalue()).reason=='work_snapshot_byte_quota'


def test_indexed_pages_match_canonical_rows_and_legacy_reader_and_detect_corruption(tmp_path,monkeypatch):
    from poliscope_engine.contracts.world import WorldInspectParams
    from poliscope_engine.evaluation.identity import digest
    from poliscope_engine.revisions import RevisionError
    counts=dict(scopes=4,cohorts=4,assets=4,decision_instances=16,active_typed_edges=401)
    host,data,_=fixture(counts)
    with Store(tmp_path) as store:
        service=Revisions(store,registry=host)
        request=CreateRequest(revision_contract=1,data_store_id=service.data_store_id,civilization_id='scale:civ',branch_id='main',name='Pages',operation_id='create',inputs=data)
        accepted=service.create(request)
        q=WorldInspectParams(world_schema=1,context=accepted.context,collection='relationships',cursor=None,limit=37)
        rows=[];cursor=None
        while True:
            page=service.inspect(q.model_copy(update={'cursor':cursor}))
            assert len(page.page.items)<=37 and len(page.model_dump_json().encode())<1048576
            rows+=page.page.items;cursor=page.page.next_cursor
            if cursor is None:break
        assert rows==sorted(service.read(accepted.context).inputs.relationships,key=lambda r:r.id)
        first=service.inspect(q)
        scope=service._context(accepted.context)
        kind='world-page:'+digest([accepted.context.revision_id,'relationships'])
        # Simulate pre-index retained history and compare its public contract.
        original=store.read_record
        mode='legacy'
        def projected(context,collection,identity):
            if collection==kind:
                if mode=='legacy' and identity=='metadata':return None
                if mode=='corrupt' and identity=='000000':return '[]'
            return original(context,collection,identity)
        monkeypatch.setattr(store,'read_record',projected)
        assert service.inspect(q)==first
        mode='corrupt'
        with pytest.raises(RevisionError,match='unavailable_world_projection'):service.inspect(q)
        assert len(service.read(accepted.context).inputs.relationships)==401


def test_verified_evidence_cache_is_detached_clearable_and_never_hides_missing_chunks(tmp_path,monkeypatch):
    import poliscope_engine.revisions as module
    with Store(tmp_path) as store:
        service=Revisions(store,registry=headless_fixture.registry())
        opened=headless_fixture.create(service)
        verify_original=module.read_retained
        calls=[]
        def counted(text):calls.append(1);return verify_original(text)
        monkeypatch.setattr(module,'read_retained',counted)
        original=service.evidence(opened.context)
        altered=service.evidence(opened.context)
        altered.report.traces[0].dependency_refs.append('unavailable')
        assert service.evidence(opened.context)==original
        assert len(calls)==1
        service.clear_caches()
        assert service.evidence(opened.context)==original and len(calls)==2
        read=store.read_record
        def missing(scope,kind,identity):
            return None if kind=='chunk:accepted' else read(scope,kind,identity)
        monkeypatch.setattr(store,'read_record',missing)
        with pytest.raises(ValueError,match='unavailable_snapshot_chunk'):service.evidence(opened.context)


def test_outer_limit_cannot_be_masked_by_nested_host_work():
    from poliscope_engine.work_limits import checkpoint
    flag=[False]
    with limited(WorkLimits(cancelled=lambda:flag[0])):
        flag[0]=True
        with pytest.raises(WorkStopped,match='work_cancelled'):
            with limited(WorkLimits()):checkpoint('nested')


def test_preview_deadline_is_checked_after_historical_evidence_read(tmp_path,monkeypatch):
    with Store(tmp_path) as store:
        service=Revisions(store,registry=headless_fixture.registry())
        opened=headless_fixture.create(service)
        request=headless_fixture.preview(opened.context,headless_fixture.inputs())
        current=[0]
        evidence=service.evidence
        def delayed(context):
            saved=evidence(context);current[0]=2;return saved
        monkeypatch.setattr(service,'evidence',delayed)
        service.limits=WorkLimits(seconds=1,clock=lambda:current[0])
        with pytest.raises(WorkStopped,match='work_time_quota'):service.preview(request)
        assert service.branch(opened.context).context==opened.context
