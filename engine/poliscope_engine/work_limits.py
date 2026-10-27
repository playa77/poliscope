"""Host-local cooperative limits; never part of scientific result identity.

The outer host still owns process termination for a callback that does not return.
Memory limits here count serialized working snapshots, not process RSS.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from time import monotonic

_current = ContextVar('poliscope_work_limits', default=())


class WorkStopped(RuntimeError):
    """No partial result is an accepted evaluation or a confirmed revision."""


class WorkLimits:
    def __init__(self, *, seconds=60, snapshot_bytes=64 * 1024 * 1024,
                 cancelled=None, progress=None, clock=monotonic):
        if not 0 < seconds <= 3600 or type(snapshot_bytes) is not int or not 1 <= snapshot_bytes <= 256 * 1024 * 1024:
            raise ValueError('invalid_work_limits')
        self.clock, self.deadline = clock, clock() + seconds
        self.snapshot_bytes, self.cancelled, self.progress = snapshot_bytes, cancelled, progress

    def check(self, stage, *, size=0):
        if self.cancelled is not None and self.cancelled():
            raise WorkStopped('work_cancelled')
        if self.clock() >= self.deadline:
            raise WorkStopped('work_time_quota')
        if size > self.snapshot_bytes:
            raise WorkStopped('work_snapshot_byte_quota')
        if self.progress is not None:
            self.progress(stage)


def checkpoint(stage, *, size=0):
    limits = _current.get()
    if callable(size):
        size = size() if limits else 0
    for active in limits:
        active.check(stage, size=size)


@contextmanager
def limited(limits):
    # Nested services share the caller's deadline and cancellation token.
    parents = _current.get()
    token = _current.set((*parents, limits)) if limits is not None and limits not in parents else None
    try:
        checkpoint('starting')
        yield
    finally:
        if token is not None:
            _current.reset(token)
