"""One-shot main-granted recovery host; independent of engine handshake."""
import argparse
from pathlib import Path
import sys
from .contracts.recovery import RecoveryRequest, RecoveryReply, ModelMigration
from .storage import Store
from . import recovery


def compatible_inputs(inputs, registry):
    # Imported declarations are not implementation authority. Only installed
    # definitions can be selected, even if an unresolved evaluation is readable.
    for instance in inputs.design.execution.dependencies.instances:
        registry.definition(instance.mechanism_id, instance.mechanism_version)
    from .numeric import RUNTIME_ID
    return inputs.model_copy(update={'versions': inputs.versions.model_copy(update={
        'model_id': registry.model[0], 'numeric_runtime_id': RUNTIME_ID})})


def request(source, query, destination=None, identity='unused'):
    if query.action == 'inspect':
        return recovery.inspect(source)
    if query.action == 'read':
        if query.context is None:
            raise ValueError('context required')
        return recovery.read_revision(source, query.context, query.detail_offset)
    if query.action == 'archive-migrate':
        from .archives import validate_archive
        from .contracts.archives import ArchiveRevision
        from .contracts.revisions import CreateRequest
        from .workspace import registry
        from .storage import database_path
        from .revisions import Revisions
        manifest, items = validate_archive(source)
        item = items[query.offset]
        if not isinstance(item, ArchiveRevision):
            raise ValueError('select a retained design revision')
        from .evaluation.identity import digest
        if not database_path(destination).exists():
            compatible_inputs(item.inputs, registry())
        with Store(destination) as store:
            service = Revisions(store, registry=None)
            scope = service._scope(service.data_store_id, item.civilization_id)
            key = digest(dict(kind='archive-migration', operation_id=identity))
            row = store._connection.execute('SELECT binding,outcome FROM operations WHERE context_id=? AND id=?', (scope,key)).fetchone()
            if row is not None:
                import json
                from .contracts.revisions import MutationOutcome
                binding = json.loads(row[0])
                old_request = binding['request']
                if (binding['store'] != service.data_store_id or old_request['origin']['archive_id'] != manifest.projection_digest or
                        old_request['origin']['revision_id'] != item.id or old_request['create']['name'] != query.name):
                    raise ValueError('migration recovery binding mismatch')
                result = MutationOutcome.model_validate_json(row[1])
                service.read(result.context)
                return RecoveryReply(status='complete', detail='Archive comparison already confirmed. Original archive and retained historical evidence preserved; no recomputation.')
            service.registry = registry()
            inputs = compatible_inputs(item.inputs, service.registry)
            from .evaluation.identity import serialized, digest
            from .contracts.revisions import RevisionRecord, BranchState, MutationOutcome
            from .contracts.world import RevisionContext
            from .revisions import EMPTY_DECISION
            create = CreateRequest(revision_contract=1, data_store_id=service.data_store_id,
                civilization_id=item.civilization_id, branch_id='comparison', name=query.name,
                operation_id=identity, inputs=inputs)
            scope = service._scope(create.data_store_id, create.civilization_id)
            origin = dict(archive_id=manifest.projection_digest, revision_id=item.id,
                evidence='retained privacy projection; new branch is newly computed')
            with store.transaction():
                key, binding, old = service._operation(scope, 'archive-migration', identity, dict(create=create, origin=origin))
                if old is None:
                    if store.read_context(scope) is not None:
                        raise ValueError('migration civilization exists')
                    evidence = service._evaluate(inputs, create.civilization_id)
                    context = RevisionContext(data_store_id=service.data_store_id,
                        civilization_id=create.civilization_id, branch_id='comparison', revision_id=digest(dict(create=create,origin=origin)))
                    store.add_context(scope, serialized(dict(civilization_id=create.civilization_id)))
                    service._persist(scope, RevisionRecord(revision_contract=1, context=context, parent_id=None,
                        inputs=inputs, decision=EMPTY_DECISION, evidence_digest=evidence.closure_digest, applied_preview=None), evidence)
                    service._save_branch(scope, BranchState(revision_contract=1, context=context, name=query.name,
                        sequence=0, redo=[], forked_from=None))
                    store.add_record(scope, 'migration-origin', identity, serialized(origin))
                    store.complete_operation(scope, key, binding,
                        MutationOutcome(revision_contract=1,context=context,branch_sequence=0).model_dump_json())
        return RecoveryReply(status='complete', detail='Archive retained unchanged. Newly computed comparison saved in the chosen sandbox; private redactions remain excluded. Open that folder to inspect the new branch.')
    if query.action in ('archive-open', 'archive-read'):
        from .archives import validate_archive, display_item
        manifest, items = validate_archive(source)
        if not 0 <= query.offset < len(items):
            raise ValueError('archive offset')
        heading, rows, next_offset = display_item(items[query.offset], query.detail_offset)
        return RecoveryReply(status='complete', detail=heading + '; retained archive data, read only; no computation or imported code.',
            rows=rows, next_offset=next_offset)
    if query.action == 'backup':
        recovery.backup(source, destination)
    elif query.action == 'restore':
        recovery.restore(source, destination)
    elif query.action == 'migrate-schema':
        recovery.migrate_schema(source, destination)
    elif query.action == 'migrate-model':
        from .revisions import Revisions
        if Path(source).name != 'poliscope.sqlite3':
            raise ValueError('restore the selected backup into a sandbox before migrating its model')
        with Store(Path(source).parent) as store:
            service = Revisions(store, registry=None)
            result = service.migration_status(query.context, identity, 'migration:' + identity, query.name)
            if result is None:
                from .workspace import registry
                service.registry = registry()
                base = service.read(query.context)
                inputs = compatible_inputs(base.inputs, service.registry)
                result = service.migrate_model(ModelMigration(operation_id=identity, context=query.context,
                    new_branch_id='migration:' + identity, name=query.name, inputs=inputs))
            versions = service.read(result.context).inputs.versions
            return RecoveryReply(status='complete', detail='New comparison branch saved with newly computed results. Original branch and evidence retained.',
                branches=[dict(context=result.context, name=query.name, model_id=versions.model_id, numeric_runtime_id=versions.numeric_runtime_id, execution='requires_explicit_migration')])
    else:
        raise ValueError('unknown action')
    return RecoveryReply(status='complete', detail='Confirmed. Original history and prior backups preserved. Database snapshot includes replay identities and redaction status; separate private payload stores and keys are excluded.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--identity', default='unused')
    args = parser.parse_args()
    query = None
    try:
        raw = sys.stdin.buffer.readline(16385)
        if not raw.endswith(b'\n') or len(raw) > 16384 or sys.stdin.buffer.read(1):
            raise ValueError('invalid frame')
        query = RecoveryRequest.model_validate_json(raw)
        if not args.source.is_absolute() or (args.destination is not None and not args.destination.is_absolute()):
            raise ValueError('invalid grant')
        if (query.action in ('backup','restore','migrate-schema','archive-migrate')) != (args.destination is not None):
            raise ValueError('invalid destination grant')
        reply = request(args.source, query, args.destination, args.identity)
    except Exception as exc:
        import sqlite3
        from .storage import StorageError
        diagnostic = 'unreadable_source'
        if query is not None:
            if query.action in ('archive-open', 'archive-read'): diagnostic = 'corrupt_archive'
            elif query.action in ('backup', 'restore'): diagnostic = 'save_failed'
            elif query.action in ('migrate-schema', 'migrate-model', 'archive-migrate'): diagnostic = 'migration_failed'
            elif isinstance(exc, sqlite3.DatabaseError): diagnostic = 'corrupt_database'
            elif isinstance(exc, StorageError): diagnostic = 'unsupported_schema'
        reply = RecoveryReply(status='failed', diagnostic=diagnostic,
            detail='Request unconfirmed. Preserve the original and any backup. Use a compatible reader for unsupported schemas, or restore a verified backup into a new empty folder. No automatic reset occurred.')
    frame = reply.model_dump_json().encode() + b'\n'
    if len(frame) > 1048576:
        frame = RecoveryReply(status='failed', diagnostic='unreadable_source', detail='Historical response exceeds the safe display limit. Original preserved.').model_dump_json().encode() + b'\n'
    sys.stdout.buffer.write(frame)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
