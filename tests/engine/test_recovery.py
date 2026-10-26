"""WP-041: real SQLite interruption, exact replay and retained model evidence."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import pytest
from poliscope_engine.storage import Store, database_path, StorageError
from poliscope_engine.storage.store import APPLICATION_ID, _SCHEMA_V1, check_schema
from poliscope_engine import recovery
from poliscope_engine.contracts.recovery import ModelMigration, RecoveryRequest
from poliscope_engine.revisions import Revisions, RevisionError
from poliscope_engine.recovery_host import request
from test_revisions import mechanism_registry, create_request, output, apply_request, value


def legacy(path):
    with sqlite3.connect(path) as connection:
        for statement in _SCHEMA_V1:
            connection.execute(statement)
        connection.execute(f'PRAGMA application_id={APPLICATION_ID}')
        connection.execute('PRAGMA user_version=1')
        connection.execute("INSERT INTO contexts VALUES ('c', '{}')")
        connection.execute("INSERT INTO evidence VALUES ('c', 'e', '{}')")
        connection.execute("INSERT INTO operations VALUES ('c', 'op', '{}', '{}')")


def test_explicit_schema_upgrade_preserves_history_and_backup(tmp_path):
    source = database_path(tmp_path); legacy(source)
    before = source.read_bytes()
    with pytest.raises(StorageError):
        Store(tmp_path)  # Writer must not silently upgrade.
    assert source.read_bytes() == before
    destination = tmp_path / 'before.sqlite3'
    recovery.migrate_schema(source, destination)
    with recovery.reader(destination) as connection:
        assert check_schema(connection) == 1
        assert connection.execute("SELECT * FROM operations").fetchall() == [('c', 'op', '{}', '{}')]
    with Store(tmp_path) as store:
        assert store.read_evidence('c','e') == '{}'
        assert store.operation_outcome('c','op','{}') == '{}'
        assert check_schema(store._connection) == 2
        receipt=json.loads(store._connection.execute("SELECT payload FROM recovery_metadata WHERE id='schema-1-to-2'").fetchone()[0])
        assert receipt['from_schema']==1 and receipt['to_schema']==2 and receipt['history']=='preserved'
    with recovery.reader(destination) as connection:
        assert check_schema(connection) == 1
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("DELETE FROM caches")


def test_interrupted_schema_ddl_rolls_back_and_keeps_backup(tmp_path):
    source = database_path(tmp_path); legacy(source)
    destination = tmp_path / 'before.sqlite3'
    def fail(connection):
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='recovery_metadata'").fetchone()
        raise OSError('synthetic disk full')
    with pytest.raises(OSError):
        recovery.migrate_schema(source, destination, fault=fail)
    with recovery.reader(source) as connection:
        assert check_schema(connection) == 1
        assert connection.execute('SELECT count(*) FROM operations').fetchone() == (1,)
    with recovery.reader(destination) as connection:
        assert check_schema(connection) == 1
        assert connection.execute("SELECT * FROM operations").fetchall() == [('c', 'op', '{}', '{}')]


def test_process_killed_mid_migration_recovers_confirmed_rows(tmp_path):
    source = database_path(tmp_path); legacy(source)
    destination = tmp_path / 'backup.sqlite3'
    code = "from pathlib import Path; import os; from poliscope_engine.recovery import migrate_schema; migrate_schema(Path(%r), Path(%r), fault=lambda c: os._exit(17))" % (str(source),str(destination))
    result = subprocess.run([sys.executable,'-c',code],capture_output=True)
    assert result.returncode == 17
    with recovery.reader(source) as connection:
        assert check_schema(connection) == 1
        assert connection.execute('SELECT count(*) FROM evidence').fetchone() == (1,)
    with recovery.reader(destination) as connection:
        assert check_schema(connection) == 1


def test_snapshot_restore_replays_and_retains_evidence_after_cache_deletion(tmp_path):
    original = tmp_path / 'original'
    with Store(original) as store:
        service = Revisions(store, registry=mechanism_registry())
        create = create_request(service)
        created = service.create(create)
        apply = apply_request(service, created.context)
        applied = service.apply(apply)
        assert output(service.evidence(applied.context)) == '15'
        with store.transaction():
            store.cache(service._context(created.context), 'throwaway', '{}')
            store.clear_caches()
        backup = tmp_path / 'backup.sqlite3'
        recovery.backup(store.path, backup)  # Includes committed WAL while live.
    restored = tmp_path / 'restored'
    recovery.restore(backup,restored)
    with Store(restored) as store:
        cold = Revisions(store,registry=None)
        assert cold.status('apply',apply) == applied
        assert cold.apply(apply) == applied  # replay before runtime/head checks
        assert cold.create(create) == created
        assert output(cold.evidence(applied.context)) == '15'
        assert cold.branch(created.context).context == applied.context
    with pytest.raises(StorageError): recovery.restore(backup,restored)
    with pytest.raises(FileExistsError): recovery.backup(backup,backup)


def test_new_model_branch_never_rewrites_source_and_replays(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store,registry=mechanism_registry())
        created = service.create(create_request(service))
        old = service.read(created.context).model_dump_json()
        retained = service.evidence(created.context).model_dump_json()
        inputs = service.read(created.context).inputs.model_copy(deep=True)
        # Explicit same-model comparison is valid; change a declared input.
        inputs = inputs.model_copy(update={'values': [value('7')]})
        migration = ModelMigration(operation_id='migration', context=created.context,
            new_branch_id='comparison',name='Compatible comparison',inputs=inputs)
        migrated = service.migrate_model(migration)
        assert output(service.evidence(migrated.context)) == '21'
        assert service.branch(created.context).context == created.context
        assert service.read(created.context).model_dump_json() == old
        assert service.evidence(created.context).model_dump_json() == retained
        assert service.branch(migrated.context).forked_from == created.context
        assert service.read(migrated.context).parent_id == created.context.revision_id
        cold = Revisions(store,registry=None)
        assert cold.migrate_model(migration) == migrated
        with pytest.raises(RevisionError):
            cold.migrate_model(migration.model_copy(update={'operation_id':'other', 'new_branch_id':'bad'}))
        assert len(cold.catalogue()) == 2


def test_cold_discovery_and_read_do_not_need_executable_model_or_cache(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store,registry=mechanism_registry())
        created = service.create(create_request(service))
    before = database_path(tmp_path).read_bytes()
    found = recovery.inspect(database_path(tmp_path))
    assert found.branches[0].execution == 'unavailable'
    assert found.branches[0].model_id == 'synthetic:model'
    page = recovery.read_revision(database_path(tmp_path),created.context)
    assert 'not freshly reproduced' in page.detail
    assert any(r.label == 'Model and runtime' and 'synthetic:model' in r.detail for r in page.rows)
    assert database_path(tmp_path).read_bytes() == before


@pytest.mark.parametrize('variant', ['corrupt', 'future', 'forged'])
def test_reject_preserve_unsafe_sources(tmp_path,variant):
    source = database_path(tmp_path)
    if variant == 'corrupt': source.write_bytes(b'not a sqlite database')
    else:
        legacy(source)
        with sqlite3.connect(source) as connection:
            connection.execute('PRAGMA user_version=999' if variant == 'future' else 'CREATE VIEW hostile AS SELECT 1')
    before = source.read_bytes()
    with pytest.raises((StorageError,sqlite3.DatabaseError)):
        recovery.backup(source,tmp_path/'never.sqlite3')
    assert source.read_bytes() == before
    assert not (tmp_path/'never.sqlite3').exists()


def test_backup_failure_does_not_remove_existing_destination_or_history(tmp_path,monkeypatch):
    source=database_path(tmp_path); legacy(source)
    destination=tmp_path/'existing.sqlite3';destination.write_bytes(b'keep')
    with pytest.raises(FileExistsError): recovery.backup(source,destination)
    assert destination.read_bytes()==b'keep'
    original=source.read_bytes()
    def fail(_): raise OSError('synthetic disk full')
    monkeypatch.setattr(os,'fsync',fail)
    with pytest.raises(OSError): recovery.backup(source,tmp_path/'failed.sqlite3')
    assert source.read_bytes()==original
    assert not (tmp_path/'failed.sqlite3').exists()


def test_changed_model_identity_is_explicit_and_failed_save_rolls_back(tmp_path,monkeypatch):
    from poliscope_engine.mechanisms import MechanismRegistry
    from poliscope_engine.workspace import starting_inputs
    with Store(tmp_path) as store:
        source_registry=MechanismRegistry(model=('old:model','v1'),units=mechanism_registry().units)
        service=Revisions(store,registry=source_registry)
        base_inputs=starting_inputs(dict(name='Old',setup='blank',scope_name='Home',population=None,land_area=None),'civ')
        base_inputs=base_inputs.model_copy(update={'versions':base_inputs.versions.model_copy(update={'model_id':'old:model'})})
        created=service.create(create_request(service,inputs=base_inputs))
        original=service.evidence(created.context).model_dump_json()
        service.registry=MechanismRegistry(model=('new:model','v2'),units=source_registry.units)
        new_inputs=base_inputs.model_copy(update={'versions':base_inputs.versions.model_copy(update={'model_id':'new:model'})})
        migration=ModelMigration(operation_id='upgrade',context=created.context,new_branch_id='new',name='New model',inputs=new_inputs)
        persist=service._persist
        def fail(*args):
            persist(*args)
            raise sqlite3.OperationalError('database or disk is full')
        monkeypatch.setattr(service,'_persist',fail)
        with pytest.raises(sqlite3.OperationalError): service.migrate_model(migration)
        assert len(service.catalogue())==1
        assert service.evidence(created.context).model_dump_json()==original
        monkeypatch.setattr(service,'_persist',persist)
        migrated=service.migrate_model(migration)
        assert service.read(migrated.context).inputs.versions.model_id=='new:model'
        assert service.read(created.context).inputs.versions.model_id=='old:model'
        assert service.evidence(created.context).model_dump_json()==original


@pytest.mark.parametrize('reduced',[False,True])
def test_cold_portable_inspection_and_explicit_migration_preserve_projection(tmp_path,reduced):
    from test_archives import source
    from poliscope_engine.archives import export_archive,validate_archive
    from poliscope_engine.contracts.archives import ArchiveOptions,ArchiveRevision
    store,service,context=source(tmp_path/'original')
    archive=tmp_path/'history.poliscope'
    export_archive(service,archive,ArchiveOptions(evidence='reduced' if reduced else 'complete'))
    store.close()
    before=archive.read_bytes()
    manifest,items=validate_archive(archive)
    offset=next(i for i,item in enumerate(items) if isinstance(item,ArchiveRevision))
    query=RecoveryRequest(action='archive-read',offset=offset)
    reply=request(archive,query)
    assert reply.status=='complete'
    assert any(r.label=='Evidence' and ('omitted' if reduced else 'not freshly reproduced') in r.detail for r in reply.rows)
    target=tmp_path/'new'
    migrated=request(archive,RecoveryRequest(action='archive-migrate',offset=offset),target,'archive-upgrade')
    assert migrated.status=='complete'
    with Store(target) as saved:
        cold=Revisions(saved,registry=None)
        assert len(cold.catalogue())==1
        branch=cold.catalogue()[0]
        assert cold.read(branch.context).inputs == items[offset].inputs
        assert cold.store.read_record(cold._context(branch.context),'migration-origin','archive-upgrade') is not None
        assert cold.evidence(branch.context).report is not None
    request(archive,RecoveryRequest(action='archive-migrate',offset=offset),target,'archive-upgrade')
    with Store(target) as saved:
        assert len(Revisions(saved,registry=None).catalogue())==1
    assert archive.read_bytes()==before


def test_original_history_interface_reads_schema_one_after_writer_upgrade(tmp_path):
    from test_history import saved
    from poliscope_engine.contracts.history import HistoryRequest
    from poliscope_engine.history import read
    source=database_path(tmp_path);legacy(source)
    payload=saved()
    query=HistoryRequest(history_protocol=1,context=payload['summary']['context'],
        result_id=payload['summary']['result_id'],collection='summary',offset=0,limit=1)
    with sqlite3.connect(source) as connection:
        connection.execute('INSERT INTO evidence VALUES (?,?,?)',('c',query.result_id,json.dumps(payload)))
    assert read(source,'c',query,query).result.model_dump()==payload['summary']
    recovery.migrate_schema(source,tmp_path/'before.sqlite3')
    assert read(source,'c',query,query).result.model_dump()==payload['summary']


def test_absent_mechanism_archive_is_inspectable_but_not_executable(tmp_path):
    from poliscope_engine.archives import export_archive,validate_archive
    from poliscope_engine.contracts.archives import ArchiveRevision
    with Store(tmp_path/'original') as store:
        service=Revisions(store,registry=mechanism_registry())
        created=service.create(create_request(service))
        archive=tmp_path/'absent.poliscope'
        export_archive(service,archive)
    _,items=validate_archive(archive)
    offset=next(i for i,x in enumerate(items) if isinstance(x,ArchiveRevision))
    before=archive.read_bytes()
    assert request(archive,RecoveryRequest(action='archive-read',offset=offset)).status=='complete'
    with pytest.raises(ValueError):
        request(archive,RecoveryRequest(action='archive-migrate',offset=offset),tmp_path/'target','attempt')
    assert not (tmp_path/'target').exists()
    assert archive.read_bytes()==before


def test_backup_restore_does_not_resurrect_deleted_private_payloads(tmp_path):
    from poliscope_engine import private_notes,workbench
    from poliscope_engine.workspace import registry
    from test_workbench import blank,edit,note,commit,query
    original=tmp_path/'original'
    with Store(original) as store:
        service=Revisions(store,registry=registry())
        base=blank(service)
        _,saved=commit(service,edit(base,note('PRIVATE_RECOVERY_CANARY')), 'note')
        context=saved.state.context
        reference=service.read(context).inputs.notes[0]
        location=private_notes.location(service,context,reference.id)
        (location/'derivatives').mkdir()
        (location/'derivatives'/'index').write_text('PRIVATE_RECOVERY_DERIVED')
        workbench.delete(service,dict(context=context,scope_id='home',id=reference.id))
        assert not (location/'payloads').exists() and not (location/'derivatives').exists()
        assert private_notes.read(service,context,reference)[0]=='deleted'
        backup=tmp_path/'backup.sqlite3'
        recovery.backup(store.path,backup)
    target=tmp_path/'restored'
    recovery.restore(backup,target)
    with Store(target) as store:
        reader=Revisions(store,registry=None)
        status,kind,text=private_notes.read(reader,context,reference)
        assert (status,kind,text)==('unavailable',None,None)
        assert 'PRIVATE_RECOVERY' not in '\n'.join(store._connection.iterdump())
        assert reader.evidence(context).report is not None
        assert reader.read(context).inputs.notes[0]==reference
    assert not (target/'private-notes').exists()


@pytest.mark.parametrize('action,body,diagnostic',[
    ('inspect',b'broken database','corrupt_database'),
    ('archive-read',b'broken archive','corrupt_archive'),
])
def test_distinct_bounded_corruption_diagnostics(tmp_path,action,body,diagnostic):
    source=tmp_path/'user-selected';source.write_bytes(body)
    process=subprocess.run([sys.executable,'-I','-m','poliscope_engine.recovery_host','--source',str(source)],
        input=RecoveryRequest(action=action).model_dump_json()+'\n',capture_output=True,text=True,timeout=10)
    assert process.returncode==0 and not process.stderr
    reply=json.loads(process.stdout)
    assert reply['status']=='failed' and reply['diagnostic']==diagnostic
    assert str(source) not in process.stdout
    assert source.read_bytes()==body


def test_backup_directory_flush_failure_prevents_schema_commit(tmp_path,monkeypatch):
    if os.name=='nt':
        return  # POSIX directory durability primitive; native Windows is separate.
    source=database_path(tmp_path);legacy(source)
    calls=0
    real=os.fsync
    def fail_directory(fd):
        nonlocal calls
        calls+=1
        if calls==2: raise OSError('directory flush failed')
        return real(fd)
    monkeypatch.setattr(os,'fsync',fail_directory)
    backup=tmp_path/'backup.sqlite3'
    with pytest.raises(OSError): recovery.migrate_schema(source,backup)
    assert not backup.exists()
    with recovery.reader(source) as connection: assert check_schema(connection)==1


def test_native_migration_recovery_does_not_require_installed_model(tmp_path,monkeypatch):
    from poliscope_engine import workspace
    from test_workbench import blank
    with Store(tmp_path) as store:
        service=Revisions(store,registry=workspace.registry())
        context=blank(service)
    query=RecoveryRequest(action='migrate-model',context=context,name='Upgrade')
    first=request(database_path(tmp_path),query,identity='one')
    def unavailable(): raise RuntimeError('new runtime unavailable')
    monkeypatch.setattr(workspace,'registry',unavailable)
    assert request(database_path(tmp_path),query,identity='one')==first


def test_import_migration_recovery_does_not_require_installed_model(tmp_path,monkeypatch):
    from poliscope_engine import workspace
    from test_archives import source
    from poliscope_engine.archives import export_archive,validate_archive
    from poliscope_engine.contracts.archives import ArchiveRevision
    store,service,context=source(tmp_path/'source')
    archive=tmp_path/'portable';export_archive(service,archive);store.close()
    _,items=validate_archive(archive)
    offset=next(i for i,x in enumerate(items) if isinstance(x,ArchiveRevision))
    query=RecoveryRequest(action='archive-migrate',offset=offset)
    target=tmp_path/'target'
    assert request(archive,query,target,'one').status=='complete'
    def unavailable(): raise RuntimeError('new runtime unavailable')
    monkeypatch.setattr(workspace,'registry',unavailable)
    replay=request(archive,query,target,'one')
    assert replay.status=='complete' and 'no recomputation' in replay.detail
