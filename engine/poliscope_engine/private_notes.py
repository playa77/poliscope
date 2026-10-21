"""Classified active payloads with owned derivatives, outside immutable SQLite.

No search index is built. The derivatives directory is reserved to this owner;
deletion removes its entire active contents. Backups/filesystem recovery are not
securely erased. Paths use only host-derived hashes of noncontent references.
"""
import json
import os
from pathlib import Path
import shutil
import tempfile
from poliscope_engine.evaluation.identity import digest, serialized


def location(service, context, identity):
    service.read(context)
    scope = digest([context.data_store_id, context.civilization_id]).split(':')[1]
    key = digest(identity).split(':')[1]
    return service.store.path.parent / 'private-notes' / scope / key


def atomic(path, payload):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.pending-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(serialized(payload).encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name != 'nt':
            descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def save(service, context, reference, kind, text):
    directory = location(service, context, reference.id)
    if (directory / 'deleted.json').exists():
        raise ValueError('note_deleted')
    path = directory / 'payloads' / (digest(reference.version).split(':')[1] + '.json')
    payload = dict(classification='private', reference=reference.model_dump(),
        context=context.model_dump(), kind=kind, text=text)
    if path.exists():
        with path.open('rb') as stream:
            existing = stream.read(30001)
        if existing != serialized(payload).encode():
            raise ValueError('private_note_binding_mismatch')
        return
    atomic(path, payload)


def read(service, context, reference):
    directory = location(service, context, reference.id)
    if (directory / 'deleted.json').exists():
        return 'deleted', None, None
    try:
        path = directory / 'payloads' / (digest(reference.version).split(':')[1] + '.json')
        with path.open('rb') as stream:
            raw = stream.read(30001)
        if len(raw) > 30000:
            raise ValueError('private_note_size')
        payload = json.loads(raw)
        if (set(payload) != {'classification', 'reference', 'context', 'kind', 'text'} or
                payload['classification'] != 'private' or payload['reference'] != reference.model_dump() or
                payload['context']['data_store_id'] != context.data_store_id or
                payload['context']['civilization_id'] != context.civilization_id or
                payload['kind'] not in ('inquiry', 'expectation', 'observation', 'model_gap', 'proposal') or
                not isinstance(payload['text'], str) or not 1 <= len(payload['text']) <= 2048):
            raise ValueError('private_note_binding_mismatch')
        return 'available', payload['kind'], payload['text']
    except (OSError, ValueError, KeyError, TypeError):
        return 'unavailable', None, None


def delete(service, context, reference):
    directory = location(service, context, reference.id)
    # Tombstone first: interruption cannot expose a partly deleted version set.
    atomic(directory / 'deleted.json', dict(classification='private', status='deleted'))
    for name in ('payloads', 'derivatives'):
        target = directory / name
        if target.is_symlink():
            target.unlink()
        elif target.exists():
            shutil.rmtree(target)


def project_history(records, evidences):
    """Standalone evidence projection, deliberately not a portable archive.

    Do not copy revision IDs/digests, private note IDs, rationale refs, alternatives,
    input snapshots or private goal text. Each result uses the existing tested
    public evidence projection and preserves its physical output identity.
    """
    from poliscope_engine.explanation import public_projection
    if len(records) != len(evidences):
        raise ValueError('projection_history_mismatch')
    items = []
    for record, evidence in zip(records, evidences, strict=True):
        if record.evidence_digest != evidence.closure_digest:
            raise ValueError('projection_evidence_mismatch')
        items.append(dict(private_notes='redacted', private_rationale='redacted',
            evidence=public_projection(evidence)))
    payload = dict(projection_version=1, history=items, private_payloads_included=False,
        completeness='Evidence projection only; revision inputs and private material omitted')
    return payload | dict(projection_digest=digest(payload))
