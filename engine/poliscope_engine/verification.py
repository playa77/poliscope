"""Bounded process-local proofs for exact DTO bytes already verified here.

No payloads, executable authority, durable truth or imported cache entries. A
mutation changes the key and takes the full verifier. Stored chunks are still
read and hash-checked by their owner before these semantic proofs are consulted.
"""
from collections import OrderedDict
from hashlib import sha256
from threading import RLock

_entries = OrderedDict()
_lock = RLock()


def _key(kind, values):
    checksum = sha256()
    for value in values:
        payload = value.model_dump_json().encode()
        checksum.update(len(payload).to_bytes(8, 'big'))
        checksum.update(payload)
    return kind, checksum.digest()


def contains(kind, *values):
    key = _key(kind, values)
    with _lock:
        if key in _entries:
            _entries.move_to_end(key)
            return True
    return False


def remember(kind, *values):
    key = _key(kind, values)
    with _lock:
        _entries[key] = True
        _entries.move_to_end(key)
        while len(_entries) > 64:
            _entries.popitem(last=False)


def clear():
    with _lock:
        _entries.clear()
