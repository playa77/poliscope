"""Deep read-only views for trusted host callbacks, not a Python sandbox.

DTOs already reject attribute assignment. Protect their nested containers too,
and share one detached view within a boundary instead of repeatedly copying and
serializing a complete world to detect ordinary mutations after they happen.
"""
from poliscope_engine.contracts.base import Contract
from poliscope_engine.evaluation.canonical import Memo

_leaves = Memo(8 * 1024 * 1024, entries=20000)
_STATIC_LEAVES = frozenset(('EntityDTO', 'ScopeDTO', 'RelationshipDTO'))


def clear():
    _leaves.clear()


class ReadOnlyError(TypeError):
    pass


def _reject(*args, **kwargs):
    raise ReadOnlyError('read_only_callback_input')


class ReadOnlyList(list):
    __setitem__ = __delitem__ = __iadd__ = __imul__ = _reject
    append = clear = extend = insert = pop = remove = reverse = sort = _reject

    def __deepcopy__(self, memo):
        return self


class ReadOnlyDict(dict):
    __setitem__ = __delitem__ = __ior__ = _reject
    clear = pop = popitem = setdefault = update = _reject

    def __deepcopy__(self, memo):
        return self


def freeze(value, memo):
    """The boundary owns memo's lifetime; it never retains another work item."""
    if not isinstance(value, (Contract, list, dict, tuple)):
        return value
    previous = memo.get(id(value))
    if previous is not None:
        return previous[1]
    if isinstance(value, Contract):
        key = None
        if type(value).__name__ in _STATIC_LEAVES:
            raw = value.model_dump_json()
            key = type(value), raw
            cached = _leaves.get(key)
            if cached is not None:
                memo[id(value)] = value, cached
                return cached
        result = value.model_copy(update={name: freeze(getattr(value, name), memo)
            for name in type(value).model_fields})
        if key is not None:
            _leaves.put(key, result, 2 * len(raw.encode()) + 256)
    elif isinstance(value, list):
        result = ReadOnlyList(freeze(item, memo) for item in value)
    elif isinstance(value, dict):
        result = ReadOnlyDict((key, freeze(item, memo)) for key, item in value.items())
    else:
        result = tuple(freeze(item, memo) for item in value)
    # Keep the source alive so its identity cannot be recycled within this memo.
    memo[id(value)] = value, result
    return result
