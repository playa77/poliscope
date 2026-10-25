"""Portable archives exercise real revisions, evidence, experiments and SQLite."""
import hashlib
import json
from pathlib import Path
import stat
import zipfile
import pytest
from poliscope_engine.archives import (ArchiveError, export_archive, validate_archive,
    import_archive, list_archives, read_item, ARCHIVES)
from poliscope_engine.contracts.archives import ArchiveOptions, ArchiveRevision, ArchiveExperiment
from poliscope_engine.contracts.revisions import BranchRequest
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.revisions import Revisions
from poliscope_engine.storage import Store
from poliscope_engine.workspace import registry, dispatch
from test_experiments import setup, advance, fork_request
from test_workbench import blank, edit, note, commit


def source(directory):
    store = Store(directory)
    service = Revisions(store, registry=registry())
    context = blank(service)
    return store, service, context


def contents(path):
    with zipfile.ZipFile(path) as archive:
        return {n: archive.read(n) for n in archive.namelist()}


def rewrite(path, entries):
    with zipfile.ZipFile(path, 'w') as archive:
        for name, raw in entries.items():
            archive.writestr(name, raw)


def test_real_roundtrip_branches_evidence_reopen_no_model_or_cache(tmp_path):
    store, service, context = source(tmp_path/'source')
    fork = service.change_branch(BranchRequest(revision_contract=1, operation_id='fork',
        context=context,expected_sequence=0,action='fork',new_branch_id='alternative',name='Alternative'))
    saved = service.evidence(context)
    with store.transaction():
        store.clear_caches()
    path = tmp_path/'portable.zip'
    summary = export_archive(service,path)
    assert summary.revisions == 1 and summary.branches == 2
    manifest, items = validate_archive(path)
    revision = next(x for x in items if isinstance(x,ArchiveRevision))
    assert revision.inputs == service.read(context).inputs
    assert revision.evidence.saved.report.measurements == saved.report.measurements
    assert revision.evidence.saved.report.traces == saved.report.traces
    assert revision.evidence.saved.evaluation.observations == saved.evaluation.observations
    assert context.revision_id.encode() not in b''.join(contents(path).values())
    store.close()
    with Store(tmp_path/'target') as target:
        imported = import_archive(target,path)
        assert imported.execution == 'unavailable'
        assert import_archive(target,path) == imported
        assert len(list_archives(target)) == 1
        index = next(i for i,x in enumerate(items) if isinstance(x,ArchiveRevision))
    with Store(tmp_path/'target') as target:
        loaded, _ = read_item(target,summary.id,index)
        assert loaded == revision
        with target.transaction():
            target.clear_caches()
        assert read_item(target,summary.id,index)[0] == revision


def test_real_stochastic_experiment_and_retrospective_fork(tmp_path):
    with Store(tmp_path/'source') as store:
        experiments, opening, _ = setup(store)
        head = experiments.advance(advance(opening)).head
        past = experiments.boundaries.read(opening.context,2)
        from poliscope_engine.boundaries import outcome
        experiments.fork(fork_request(experiments,outcome(past.record)))
        path = tmp_path/'experiments.zip'
        export_archive(experiments.reducer.revisions,path)
        _, items = validate_archive(path)
        histories = [x for x in items if isinstance(x,ArchiveExperiment)]
        controlled = next(x for x in histories if x.id == 'controlled')
        fork = next(x for x in histories if x.id == 'fork')
        assert [b.day for b in controlled.boundaries] == [0,1,2,3,4]
        assert controlled.checkpoint_sequences == [0,2,4]
        retained=experiments.boundaries.read(head.context).state.transition
        projected=controlled.boundaries[-1].transition
        assert projected.request.procedure == retained.request.procedure
        assert projected.request.claim_order == retained.request.claim_order
        assert [(c.id,c.requested) for c in projected.request.batch.claims] == [(c.id,c.requested) for c in retained.request.batch.claims]
        assert projected.allocation.actuals == retained.allocation.actuals
        assert [(o.claim_id,o.instance_id,o.original_requested,o.fulfilled_prior) for o in projected.claim_owners] == [(o.claim_id,o.instance_id,o.original_requested,o.fulfilled_prior) for o in retained.claim_owners]
        assert fork.origin_id == 'controlled' and fork.origin_sequence == 2
        assert controlled.boundaries[-1].transition.balances == experiments.boundaries.read(head.context).state.transition.balances
    with Store(tmp_path/'target') as target:
        assert import_archive(target,path).experiments == len(histories)


def test_old_private_notes_alternatives_and_unrelated_files_never_read(tmp_path):
    store, service, context = source(tmp_path/'source')
    _, first = commit(service,edit(context,note('OLD_PRIVATE_CANARY',kind='expectation')),'one')
    ref = service.read(first.state.context).inputs.notes[0]
    _, second = commit(service,edit(first.state.context,note('NEW_PRIVATE_CANARY',ref.id,'observation')),'two')
    (tmp_path/'source'/'keys.json').write_text('SECRET_KEY_CANARY')
    path = tmp_path/'default.zip'
    export_archive(service,path)
    raw = b''.join(contents(path).values())
    for canary in (b'OLD_PRIVATE_CANARY',b'NEW_PRIVATE_CANARY',b'SECRET_KEY_CANARY',ref.id.encode()):
        assert canary not in raw
    included = tmp_path/'private.zip'
    export_archive(service,included,ArchiveOptions(include_private_notes=True))
    raw = b''.join(contents(included).values())
    assert b'OLD_PRIVATE_CANARY' in raw and b'NEW_PRIVATE_CANARY' in raw
    assert b'SECRET_KEY_CANARY' not in raw
    from poliscope_engine import private_notes
    private_notes.delete(service,second.state.context,ref)
    deleted=tmp_path/'deleted-notes.zip'
    export_archive(service,deleted,ArchiveOptions(include_private_notes=True))
    raw=b''.join(contents(deleted).values())
    assert b'OLD_PRIVATE_CANARY' not in raw and b'NEW_PRIVATE_CANARY' not in raw
    store.close()


def test_reduced_explicit_omissions_and_distinct_collision_identity(tmp_path):
    store, service, _ = source(tmp_path/'source')
    full, reduced = tmp_path/'full.zip', tmp_path/'reduced.zip'
    export_archive(service,full)
    export_archive(service,reduced,ArchiveOptions(evidence='reduced'))
    manifest, items = validate_archive(reduced)
    assert manifest.omitted_evidence == ['revision:0']
    assert next(x for x in items if isinstance(x,ArchiveRevision)).evidence is None
    with Store(tmp_path/'target') as target:
        assert import_archive(target,full).id != import_archive(target,reduced).id
        assert len(list_archives(target)) == 2
    store.close()


@pytest.mark.parametrize('name',['../escape','/absolute','data\\escape','x.py','data/000000.json/','C:/bad'])
def test_unsafe_paths_leave_destination_untouched(tmp_path,name):
    path = tmp_path/'bad.zip'
    rewrite(path,{'manifest.json':b'{}',name:b'{}'})
    with Store(tmp_path/'target') as store:
        with pytest.raises(ArchiveError):
            import_archive(store,path)
        assert store.read_context(ARCHIVES) is None
    assert not (tmp_path/'escape').exists()


@pytest.mark.parametrize('mode',[stat.S_IFLNK|0o777,stat.S_IFREG|0o755,stat.S_IFDIR|0o755])
def test_entry_types_rejected(tmp_path,mode):
    path=tmp_path/'bad.zip'
    with zipfile.ZipFile(path,'w') as archive:
        info=zipfile.ZipInfo('manifest.json');info.create_system=3;info.external_attr=mode<<16
        archive.writestr(info,b'{}')
    with pytest.raises(ArchiveError,match='unsafe_archive_entry'):
        validate_archive(path)


def test_digest_corruption_duplicate_names_duplicate_keys_and_unknown_schema(tmp_path):
    store,service,_=source(tmp_path/'source')
    path=tmp_path/'valid.zip';export_archive(service,path)
    original=contents(path)
    for mutation in ('digest','duplicate-key','schema','reference'):
        data=dict(original)
        if mutation=='digest': data['data/000000.json']+=b' '
        elif mutation=='duplicate-key':data['manifest.json']=b'{"version":1,"version":1}'
        elif mutation=='schema':
            obj=json.loads(data['manifest.json']);obj['version']=99;data['manifest.json']=json.dumps(obj).encode()
        else:
            obj=json.loads(data['data/000000.json']);obj['parent_id']='missing'
            data['data/000000.json']=json.dumps(obj).encode()
            m=json.loads(data['manifest.json']);m['entries'][0]['size']=len(data['data/000000.json']);m['entries'][0]['sha256']=hashlib.sha256(data['data/000000.json']).hexdigest();m['projection_digest']=digest({k:v for k,v in m.items() if k!='projection_digest'});data['manifest.json']=json.dumps(m).encode()
        hostile=tmp_path/(mutation+'.zip');rewrite(hostile,data)
        with Store(tmp_path/('target-'+mutation)) as target:
            with pytest.raises((ArchiveError,ValueError)):
                import_archive(target,hostile)
            assert target.read_context(ARCHIVES) is None
    duplicate=tmp_path/'duplicate.zip'
    with zipfile.ZipFile(duplicate,'w') as archive:
        archive.writestr('manifest.json',b'{}')
        with pytest.warns(UserWarning,match='Duplicate name'):
            archive.writestr('manifest.json',b'{}')
    with pytest.raises(ArchiveError):validate_archive(duplicate)
    store.close()


def test_import_write_failure_and_cancellation_roll_back_everything(tmp_path,monkeypatch):
    source_store,service,_=source(tmp_path/'source')
    path=tmp_path/'good.zip';export_archive(service,path)
    with Store(tmp_path/'target') as store:
        original=store.add_record
        def fail(scope,kind,key,payload):
            original(scope,kind,key,payload)
            if kind=='chunk:archive-item':raise OSError('disk full')
        monkeypatch.setattr(store,'add_record',fail)
        with pytest.raises(OSError):import_archive(store,path)
        assert store.read_context(ARCHIVES) is None
        monkeypatch.setattr(store,'add_record',original)
        with pytest.raises(ArchiveError,match='cancelled'):import_archive(store,path,cancelled=lambda:True)
        assert store.read_context(ARCHIVES) is None
    source_store.close()


def test_export_cancellation_no_partial_file_or_overwrite(tmp_path):
    store,service,_=source(tmp_path/'source')
    path=tmp_path/'export.zip'
    with pytest.raises(ArchiveError):export_archive(service,path,cancelled=lambda:True)
    assert not path.exists()
    path.write_bytes(b'preserve')
    with pytest.raises(ArchiveError):export_archive(service,path)
    assert path.read_bytes()==b'preserve'
    store.close()


def test_full_evidence_private_descriptor_redacted_but_numeric_assumption_preserved(tmp_path):
    from test_workbench import finite, workbench_registry
    from poliscope_engine.contracts.revisions import CreateRequest, RevisionInputs
    with Store(tmp_path/'template') as store:
        r=Revisions(store,registry=workbench_registry());ctx=finite(r)
        raw=r.read(ctx).inputs.model_dump(mode='json')
    raw['references'][0]['visibility']='private'
    raw['references'][0]['description']='PRIVATE_SOURCE_DESCRIPTION_CANARY'
    raw['references'][0]['assumption']['rationale']='PRIVATE_SOURCE_RATIONALE_CANARY'
    with Store(tmp_path/'source') as store:
        r=Revisions(store,registry=workbench_registry())
        ctx=r.create(CreateRequest(revision_contract=1,data_store_id=r.data_store_id,
            civilization_id='civ',branch_id='main',name='Private evidence',operation_id='create',
            inputs=RevisionInputs.model_validate(raw))).context
        expected=r.evidence(ctx).report.measurements
        path=tmp_path/'evidence.zip';export_archive(r,path)
        archive_bytes=b''.join(contents(path).values())
        assert b'PRIVATE_SOURCE_DESCRIPTION_CANARY' not in archive_bytes
        assert b'PRIVATE_SOURCE_RATIONALE_CANARY' not in archive_bytes
        _,items=validate_archive(path)
        saved=next(x for x in items if isinstance(x,ArchiveRevision)).evidence.saved
        assert saved.report.measurements[0].value == expected[0].value
        assert saved.report.measurements[0].assumption_refs == []
        assert saved.references[0].availability == 'redacted'
        assert saved.references[0].description is None
        assert saved.report.traces


def test_real_named_draws_survive_archive_without_sampler(tmp_path,monkeypatch):
    from test_stochastic import setup_random
    with Store(tmp_path/'source') as store:
        reducer,opening,_=setup_random(store)
        reducer.advance_boundary(opening,1,operation_id='draw:advance')
        expected=reducer.store.read(opening.context).state.transition.random_draws
        assert expected
        path=tmp_path/'draws.zip';export_archive(reducer.revisions,path)
    import poliscope_engine.stochastic as stochastic
    monkeypatch.setattr(stochastic,'sample',lambda *a,**k: (_ for _ in ()).throw(AssertionError('must not sample')))
    _,items=validate_archive(path)
    experiment=next(x for x in items if isinstance(x,ArchiveExperiment))
    actual=experiment.boundaries[1].transition.draws[0]
    assert actual.spec.key==expected[0].spec.key
    assert actual.spec.distribution==expected[0].spec.distribution
    assert (actual.value,actual.accepted_block,actual.seed,actual.runtime)==(expected[0].value,expected[0].accepted_block,expected[0].seed,expected[0].runtime)
    with Store(tmp_path/'target') as store:
        assert import_archive(store,path).experiments==1


def test_bounded_display_paging_and_unknown_item(tmp_path):
    from poliscope_engine.archives import display_item
    store,service,_=source(tmp_path/'source')
    path=tmp_path/'good.zip';summary=export_archive(service,path)
    _,items=validate_archive(path)
    title,rows,cursor=display_item(items[0])
    assert title.startswith('Revision') and len(rows)<=25
    assert any('Retained historical' in r.detail for r in rows)
    with Store(tmp_path/'target') as target:
        import_archive(target,path)
        with pytest.raises(ArchiveError):read_item(target,summary.id,999)
        with pytest.raises(ArchiveError):read_item(target,'sha256:'+'0'*64,0)
        with target.transaction():
            with pytest.raises(ArchiveError):list_archives(target)
    store.close()


def test_size_and_count_budgets_are_enforced_before_mutation(tmp_path,monkeypatch):
    import poliscope_engine.archives as module
    store,service,_=source(tmp_path/'source')
    path=tmp_path/'good.zip';export_archive(service,path)
    with Store(tmp_path/'target') as target:
        monkeypatch.setattr(module,'MAX_ARCHIVE',20)
        with pytest.raises(ArchiveError):import_archive(target,path)
        assert target.read_context(ARCHIVES) is None
        monkeypatch.setattr(module,'MAX_ARCHIVE',256*1024*1024)
        monkeypatch.setattr(module,'MAX_ENTRY',20)
        with pytest.raises(ArchiveError):import_archive(target,path)
        assert target.read_context(ARCHIVES) is None
        monkeypatch.setattr(module,'MAX_ENTRY',64*1024*1024)
        monkeypatch.setattr(module,'MAX_ENTRIES',1)
        with pytest.raises(ArchiveError):import_archive(target,path)
        assert target.read_context(ARCHIVES) is None
    store.close()


def test_imported_collection_reexport_preserves_evidence_and_can_reduce(tmp_path):
    store,service,_=source(tmp_path/'source')
    original=tmp_path/'original.zip';export_archive(service,original);store.close()
    with Store(tmp_path/'target') as target:
        summary=import_archive(target,original)
        reader=Revisions(target,registry=None)
        exported=tmp_path/'reexport.zip'
        export_archive(reader,exported,archive_id=summary.id)
        assert validate_archive(exported)==validate_archive(original)
        reduced=tmp_path/'reduced.zip'
        export_archive(reader,reduced,ArchiveOptions(evidence='reduced'),archive_id=summary.id)
        reduction=import_archive(target,reduced)
        with pytest.raises(ArchiveError,match='cannot_be_restored'):
            export_archive(reader,tmp_path/'false-complete.zip',archive_id=reduction.id)


@pytest.mark.parametrize('after_commit',[False,True])
def test_real_import_process_exit_before_and_after_commit(tmp_path,after_commit):
    import subprocess,sys
    store,service,_=source(tmp_path/'source')
    path=tmp_path/'portable.zip';summary=export_archive(service,path);store.close()
    target=tmp_path/'target'
    with Store(target):pass
    code='''
import os,sys
from pathlib import Path
from contextlib import contextmanager
from poliscope_engine.storage import Store
from poliscope_engine.archives import import_archive,ARCHIVES
store=Store(Path(sys.argv[1]))
transaction=store.transaction
@contextmanager
def crashing():
    with transaction():
        yield
        if sys.argv[3]=='before':os._exit(91)
    os._exit(92)
store.transaction=crashing
import_archive(store,Path(sys.argv[2]))
'''
    result=subprocess.run([sys.executable,'-c',code,str(target),str(path),'after' if after_commit else 'before'],capture_output=True)
    assert result.returncode==(92 if after_commit else 91),result.stderr
    with Store(target) as store:
        assert len(list_archives(store))==int(after_commit)
        assert import_archive(store,path).id==summary.id
        assert len(list_archives(store))==1


def rehash_entries(data):
    m=json.loads(data['manifest.json'])
    for entry in m['entries']:
        raw=data[entry['path']];entry['size']=len(raw);entry['sha256']=hashlib.sha256(raw).hexdigest()
    m['projection_digest']=digest({k:v for k,v in m.items() if k!='projection_digest'})
    data['manifest.json']=json.dumps(m).encode()


@pytest.mark.parametrize('attack',['duplicate-identity','cycle','missing-evidence','wrong-input','formula','nested-duplicate-json','private-reference','extra-file'])
def test_rehashed_hostile_semantics_fail_before_transaction(tmp_path,attack):
    store,service,_=source(tmp_path/'source')
    path=tmp_path/'portable.zip';export_archive(service,path);store.close()
    data=contents(path)
    revision=json.loads(data['data/000000.json'])
    if attack=='cycle':revision['parent_id']=revision['id']
    elif attack=='missing-evidence':revision['evidence']=None
    elif attack=='wrong-input':revision['inputs']['values'][0]['value']['value']='999'
    elif attack=='private-reference':revision['inputs']['notes']=[dict(id='private',version='v1',scope_id='home',classification='private')]
    elif attack in ('formula','nested-duplicate-json'):
        saved=revision['evidence']['saved'];e=saved['evaluation'];model=json.loads(e['model_json']);
        if attack=='formula':model['formula']='__import__("os").system("touch NEVER")'
        e['model_json']=json.dumps(model)
        if attack=='nested-duplicate-json':e['model_json']=e['model_json'][:-1]+',"numeric":'+json.dumps(model['numeric'])+'}'
        i=e['identities'];i['model_digest']=digest(model);i['cache_key']=digest({k:v for k,v in i.items() if k not in ('cache_key','output_digest')});i['output_digest']=digest({k:v for k,v in e.items() if k!='identities'})
        r=saved['report'];r['physical_output_digest']=i['output_digest'];r['report_digest']=digest({k:v for k,v in r.items() if k!='report_digest'});saved['closure_digest']=digest({k:v for k,v in saved.items() if k!='closure_digest'})
    elif attack=='extra-file':data['extra.py']=b'executable'
    else:
        m=json.loads(data['manifest.json']);m['entries'].append(dict(path='data/000002.json',size=1,sha256='0'*64));data['manifest.json']=json.dumps(m).encode();data['data/000002.json']=data['data/000000.json']
    data['data/000000.json']=json.dumps(revision).encode();rehash_entries(data)
    hostile=tmp_path/'hostile.zip';rewrite(hostile,data)
    with Store(tmp_path/'target') as target:
        with pytest.raises((ArchiveError,ValueError,KeyError)):
            import_archive(target,hostile)
        assert target.read_context(ARCHIVES) is None
    assert not (tmp_path/'NEVER').exists()


def test_rationale_opt_in_original_alternatives_and_deleted_payload(tmp_path):
    from test_interviews import setup as interview_setup, edit as interview_edit
    from poliscope_engine import interviews
    store,service,state=interview_setup(tmp_path/'source')
    change=interview_edit(state,population='125')
    preview=interviews.stage(service,change,'operation')[3]
    state=interviews.apply(service,dict(edit=change,candidate_digest=preview.candidate_digest),'operation').state
    expected=service.read(state.context)
    default=tmp_path/'default.zip';export_archive(service,default)
    assert b'Private rationale canary' not in b''.join(contents(default).values())
    included=tmp_path/'included.zip';export_archive(service,included,ArchiveOptions(include_private_rationale=True))
    _,items=validate_archive(included)
    assert b'Private rationale canary' in b''.join(contents(included).values())
    assert next(x for x in items if isinstance(x,ArchiveRevision) and x.selected_id).alternatives==expected.decision.alternatives
    reference=expected.decision.rationale_ref
    private=tmp_path/'source'/'private-interviews'/(digest(reference.id).split(':')[1]+'.json')
    private.with_suffix('.deleted').write_text('{}')
    deleted=tmp_path/'deleted.zip';export_archive(service,deleted,ArchiveOptions(include_private_rationale=True))
    assert b'Private rationale canary' not in b''.join(contents(deleted).values())
    store.close()


def test_public_attribution_and_all_write_faults_preserve_existing_data(tmp_path,monkeypatch):
    from test_workbench import finite,workbench_registry
    with Store(tmp_path/'source') as store:
        service=Revisions(store,registry=workbench_registry());context=finite(service)
        path=tmp_path/'public.zip';export_archive(service,path)
        _,items=validate_archive(path)
        revision=next(x for x in items if isinstance(x,ArchiveRevision))
        assert revision.inputs.references==service.read(context).inputs.references
        assert revision.evidence.saved.references==[r for r in service.evidence(context).references if r.visibility=='public']
        assert revision.evidence.saved.report.measurements[0].value==service.evidence(context).report.measurements[0].value
    with Store(tmp_path/'count') as target:
        writes=[]
        for name in ('add_context','add_record'):
            original=getattr(target,name)
            def count(*args,_original=original,_name=name):
                writes.append(_name);return _original(*args)
            monkeypatch.setattr(target,name,count)
        import_archive(target,path)
    for failure_at in range(1,len(writes)+1):
        with Store(tmp_path/f'fault-{failure_at}') as target:
            with target.transaction():target.add_context('existing','{"retained":true}')
            counter=[0]
            for name in ('add_context','add_record'):
                original=getattr(target,name)
                def fault(*args,_original=original):
                    counter[0]+=1
                    _original(*args)
                    if counter[0]==failure_at:raise OSError('injected disk failure')
                monkeypatch.setattr(target,name,fault)
            with pytest.raises(OSError):import_archive(target,path)
            assert target.read_context(ARCHIVES) is None
            assert target.read_context('existing')=='{"retained":true}'


def test_pinned_readable_fixture_is_offline_and_keeps_literal_values(tmp_path):
    fixture=Path(__file__).parents[1]/'fixtures'/'archives'/'accepted-v1'
    path=tmp_path/'fixture.zip'
    rewrite(path,{str(p.relative_to(fixture)):p.read_bytes() for p in fixture.rglob('*.json')})
    _,items=validate_archive(path)
    revision=next(x for x in items if isinstance(x,ArchiveRevision))
    values={v.property_id:v.value.value for v in revision.inputs.values}
    assert values=={'people':'12','area':'3'}
    assert revision.evidence.saved.state=='complete'
    with Store(tmp_path/'target') as store:
        assert import_archive(store,path).mode=='stored_historical'


def test_abandoned_future_branch_hashes_are_projected(tmp_path):
    from poliscope_engine import interviews
    from test_interviews import setup as interview_setup,edit as interview_edit
    from test_comparison import move
    store,service,state=interview_setup(tmp_path/'source')
    def apply(current,identity,number):
        data=interview_edit(current,population=number)
        preview=interviews.stage(service,data,identity)[3]
        return interviews.apply(service,dict(edit=data,candidate_digest=preview.candidate_digest),identity).state
    first=apply(state,'first','12')
    undone=move(service,first.context,'undo','undo')
    apply(undone,'second','20')
    original_ids=[b.context.branch_id for b in service.catalogue() if b.context.branch_id.startswith('retained:')]
    assert original_ids
    path=tmp_path/'futures.zip';export_archive(service,path)
    raw=b''.join(contents(path).values())
    for identity in original_ids:assert identity.encode() not in raw
    _,items=validate_archive(path)
    assert len([x for x in items if x.kind=='branch'])==2
    store.close()


@pytest.mark.parametrize('attack',['directory-count','executable-prefix'])
def test_zip_directory_is_bounded_before_eager_zip_parse(tmp_path,attack):
    store,service,_=source(tmp_path/'source')
    path=tmp_path/'archive.zip';export_archive(service,path);store.close()
    raw=bytearray(path.read_bytes())
    if attack=='directory-count':
        end=raw.rfind(b'PK\x05\x06')
        raw[end+8:end+12]=(65535).to_bytes(2,'little')*2
    else:raw=bytearray(b'MZEXECUTABLE')+raw
    path.write_bytes(raw)
    with Store(tmp_path/'target') as store:
        with pytest.raises(ArchiveError):import_archive(store,path)
        assert store.read_context(ARCHIVES) is None
