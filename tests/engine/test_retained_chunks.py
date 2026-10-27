"""Shared chunks preserve complete immutable blobs and the legacy reader."""
import json
import pytest
from poliscope_engine.evaluation.identity import digest, serialized
from poliscope_engine.storage import Store, StorageError
from poliscope_engine.storage.blobs import RetainedBlobs


def test_boundary_chunks_share_equal_content_without_repairing_corruption(tmp_path, monkeypatch):
    with Store(tmp_path) as store:
        blobs = RetainedBlobs(store)
        with store.transaction():
            store.add_context('test', '{}')
            blobs.put('test', 'boundary-state', 'first', {'text': 'a' * 220000 + 'one'})
            blobs.put('test', 'boundary-state', 'second', {'text': 'a' * 220000 + 'two'})
        a = json.loads(store.read_record('test', 'boundary-state', 'first'))
        b = json.loads(store.read_record('test', 'boundary-state', 'second'))
        assert a['blob_version'] == b['blob_version'] == 2
        assert a['refs'][:2] == b['refs'][:2]
        assert a['refs'][-1] != b['refs'][-1]
        assert json.loads(blobs.read('test', 'boundary-state', 'first'))['text'].endswith('one')
        original = store.read_record
        def damaged(context, kind, identity):
            return '"changed"' if kind == 'chunk-content:v1' and identity == a['refs'][0] else original(context, kind, identity)
        monkeypatch.setattr(store, 'read_record', damaged)
        with pytest.raises(StorageError, match='boundary_chunk_identity_mismatch'):
            blobs.read('test', 'boundary-state', 'first')
        with pytest.raises(StorageError, match='immutable_chunk_conflict'):
            with store.transaction():
                blobs.put('test', 'boundary-state', 'third', {'text': 'a' * 220000 + 'three'})
        assert original('test', 'boundary-state', 'third') is None


def test_legacy_boundary_manifest_remains_readable(tmp_path):
    with Store(tmp_path) as store:
        text = serialized({'text': 'legacy 🌱'})
        with store.transaction():
            store.add_context('test', '{}')
            store.add_record('test', 'chunk:boundary-state', 'legacy:0', serialized(text))
            store.add_record('test', 'boundary-state', 'legacy',
                serialized(dict(chunks=1, digest=digest(text))))
        assert RetainedBlobs(store).read('test', 'boundary-state', 'legacy') == text
