"""Trusted-host chunk admission, separate from the one-frame renderer protocol.

No temporary files, execution authority or writes. A complete payload is checked
before any revision service method runs. Retained snapshots use revision blobs;
public reads continue to use bounded, context-bound pages.
"""
from hashlib import sha256
import json
from tempfile import SpooledTemporaryFile

MAX_CHUNK_BYTES = 512 * 1024
MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_CHUNKS = 4096


class IngestionError(ValueError):
    pass


def decode_chunks(chunks, *, expected_sha256, model, cancelled=None):
    """Consume an ordered byte stream once, with bounded staging and exact hash.

    The host supplies the expected hash from its selected source. Chunk order,
    truncation and alteration therefore cannot publish a different revision.
    Memory spooling is capped at 1 MiB; validated materialization is at most
    32 MiB, below the retained snapshot ceiling. No renderer path is accepted.
    """
    size, checksum = 0, sha256()
    with SpooledTemporaryFile(max_size=1024 * 1024) as staged:
        for number, part in enumerate(chunks):
            if cancelled is not None and cancelled():
                raise IngestionError('ingestion_cancelled')
            if type(part) is not bytes or not 0 < len(part) <= MAX_CHUNK_BYTES:
                raise IngestionError('invalid_ingestion_chunk')
            if number >= MAX_CHUNKS:
                raise IngestionError('ingestion_chunk_quota')
            size += len(part)
            if size > MAX_INPUT_BYTES:
                raise IngestionError('ingestion_byte_quota')
            checksum.update(part)
            staged.write(part)
        if cancelled is not None and cancelled():
            raise IngestionError('ingestion_cancelled')
        if checksum.hexdigest() != expected_sha256:
            raise IngestionError('ingestion_digest_mismatch')
        staged.seek(0)
        # Pydantic's JSON parser accepts duplicate object keys. Reject those
        # before validation so no ambiguous declaration crosses this boundary.
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise IngestionError('duplicate_ingestion_key')
                result[key] = value
            return result
        try:
            value = json.load(staged, object_pairs_hook=unique,
                parse_constant=lambda _: (_ for _ in ()).throw(IngestionError('invalid_json_number')))
        except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
            raise IngestionError('invalid_ingestion_json') from error
        return model.model_validate(value)
