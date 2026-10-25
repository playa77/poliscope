"""Bounded immutable data blobs over schema-1 records and retained evidence.

The caller owns the surrounding transaction. Manifests and every chunk share its
commit. Identical content can be reused; corrupt/missing data is never repaired.
"""
import json
from poliscope_engine.evaluation.identity import digest, serialized
from .store import StorageError

MAX_BYTES = 64 * 1024 * 1024
CHUNK_CHARACTERS = 100000


class RetainedBlobs:
    def __init__(self, store):
        self.store = store

    def _manifest(self, scope, kind, identity, evidence):
        return (self.store.read_evidence(scope, kind + ':' + identity) if evidence
                else self.store.read_record(scope, kind, identity))

    def put(self, scope, kind, identity, payload, *, evidence=False):
        text = serialized(payload)
        if len(text.encode('utf-8')) > MAX_BYTES:
            raise StorageError('boundary_blob_too_large')
        if self._manifest(scope, kind, identity, evidence) is not None:
            if self.read(scope, kind, identity, evidence=evidence) != text:
                raise StorageError('immutable_blob_conflict')
            return
        chunks = [text[i:i + CHUNK_CHARACTERS] for i in range(0, len(text), CHUNK_CHARACTERS)]
        for index, chunk in enumerate(chunks):
            self.store.add_record(scope, 'chunk:' + kind, identity + ':' + str(index), serialized(chunk))
        manifest = serialized(dict(chunks=len(chunks), digest=digest(text)))
        if evidence:
            self.store.retain_evidence(scope, kind + ':' + identity, manifest)
        else:
            self.store.add_record(scope, kind, identity, manifest)

    def read(self, scope, kind, identity, *, evidence=False):
        raw = self._manifest(scope, kind, identity, evidence)
        if raw is None:
            raise StorageError('missing_boundary_blob')
        manifest = json.loads(raw)
        if not isinstance(manifest, dict) or set(manifest) != {'chunks', 'digest'}:
            raise StorageError('invalid_boundary_manifest')
        count = manifest['chunks']
        if type(count) is not int or not 1 <= count <= MAX_BYTES // CHUNK_CHARACTERS + 1:
            raise StorageError('invalid_boundary_manifest')
        chunks, size = [], 0
        for index in range(count):
            raw = self.store.read_record(scope, 'chunk:' + kind, identity + ':' + str(index))
            if raw is None:
                raise StorageError('missing_boundary_chunk')
            chunk = json.loads(raw)
            if not isinstance(chunk, str) or len(chunk) > CHUNK_CHARACTERS:
                raise StorageError('invalid_boundary_chunk')
            size += len(chunk.encode('utf-8'))
            if size > MAX_BYTES:
                raise StorageError('boundary_blob_too_large')
            chunks.append(chunk)
        text = ''.join(chunks)
        if digest(text) != manifest['digest']:
            raise StorageError('boundary_blob_digest_mismatch')
        return text
