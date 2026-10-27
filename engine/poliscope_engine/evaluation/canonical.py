"""Byte-compatible v1 encoding with bounded memoization of physical fragments.

The reference normalizer remains in identity.py for compatibility checks. Keys
contain complete source bytes, never object identity or a dirty flag. Private
provider requests, transcripts and interview payloads are not memoized here.
"""
from collections import OrderedDict
from dataclasses import dataclass, fields, is_dataclass
from decimal import Decimal
import json
from json.encoder import encode_basestring
from hashlib import sha256
from threading import RLock
from poliscope_engine.contracts.base import Contract
from poliscope_engine.numeric import canonical, parse
from .identity import UNORDERED, DECIMALS, normalize, encode


class Memo:
    def __init__(self, maximum, entries=50000):
        self.maximum, self.maximum_entries = maximum, entries
        self.values, self.size, self.lock = OrderedDict(), 0, RLock()

    def get(self, key):
        with self.lock:
            entry = self.values.get(key)
            if entry is not None:
                self.values.move_to_end(key)
                return entry[0]

    def put(self, key, value, size):
        if size > self.maximum:
            return
        with self.lock:
            previous = self.values.pop(key, None)
            if previous is not None:
                self.size -= previous[1]
            while self.values and (self.size + size > self.maximum or
                    len(self.values) >= self.maximum_entries):
                _, entry = self.values.popitem(last=False)
                self.size -= entry[1]
            self.values[key] = value, size
            self.size += size

    def clear(self):
        with self.lock:
            self.values.clear()
            self.size = 0


MODELS = frozenset('''EntityDTO ScopeDTO RelationshipDTO PartitionValueDTO
WorldProvenance NodeObservation TraceEdge MechanismInstance PortRef
NumericalBinding FixedInput ClaimBinding AccountProducer ContextRelationship
MechanismDefinition OwnerDTO PopulationDTO CalculationTrace MechanismRef EffectiveTime'''.split())
ARRAYS = frozenset('''entities scopes relationships values owners populations
observations trace_edges instances bindings fixed_inputs claims account_producers'''.split())
_models = Memo(8 * 1024 * 1024)
_arrays = Memo(64 * 1024 * 1024, entries=128)
_documents = Memo(64 * 1024 * 1024, entries=64)
_timed = Memo(16 * 1024 * 1024, entries=4096)
TIMED = frozenset(('EvaluationDesign', 'CalculationTrace'))
DOCUMENTS = frozenset('''RevisionInputs EvaluationDesign ExecutionRequest DependencyRequest EvaluationResult MeasurementReport AcceptedEvidence
BoundaryState TransitionReceipt RevisionRecord Candidate PreviewRequest ConfirmBoundary'''.split())


@dataclass(frozen=True, init=False)
class Fragment:
    """An internally encoded value, never raw JSON supplied by a caller."""
    text: str

    def __init__(self, value, field=None):
        object.__setattr__(self, 'text', encoded(value, field))


def clear():
    _models.clear()
    _arrays.clear()
    _documents.clear()
    _timed.clear()


def _dump(value):
    if isinstance(value, str):
        return encode_basestring(value)
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _parts(value, *, model=False):
    # These two additive fields deliberately preserve pre-WP-035 identities.
    omit_plan = value.get('random_plan', False) is None and 'carry_priority' in value and 'instance_order' in value
    draws = value.get('random_draws')
    omit_draws = 'transition_contract' in value and (draws == [] or model and isinstance(draws, tuple) and not draws)
    overrides = {}
    if value.get('kind') == 'quantity' and 'value' in value:
        overrides['value'] = canonical(parse(value['value']))
    elif 'node' in value and isinstance(value.get('value'), str):
        overrides['value'] = canonical(parse(value['value']))
    ordered_inputs = value.get('aggregation') == 'same_scope' and 'procedure' in value
    result = []
    for key in sorted(value):
        if key == 'random_plan' and omit_plan or key == 'random_draws' and omit_draws:
            continue
        item = overrides.get(key, value[key])
        result.append((key, _dump(key) + ':' + encoded(item, key,
            ordered=key == 'inputs' and ordered_inputs)))
    return result


def _object(value, *, model=False):
    return '{' + ','.join(part for _, part in _parts(value, model=model)) + '}'


def seal(value, digest_field, *, container=None, identity=None):
    """Hash a canonical body and insert its digest without encoding it twice."""
    parts = _parts(value)
    body = '{' + ','.join(part for _, part in parts) + '}'
    checksum = 'sha256:' + sha256(body.encode()).hexdigest()
    name = container or digest_field
    added = dict(identity, **{digest_field: checksum}) if container else checksum
    parts.append((name, _dump(name) + ':' + encoded(added)))
    parts.sort(key=lambda part: part[0])
    return checksum, '{' + ','.join(part for _, part in parts) + '}'


def remember_document(value, text):
    if type(value).__name__ in DOCUMENTS:
        key = (type(value), sha256(value.model_dump_json().encode()).digest())
        _documents.put(key, text, len(text.encode()) + 64)


def _source(value):
    if isinstance(value, Contract):
        return 'model:' + type(value).__module__ + '.' + type(value).__name__ + '\0' + value.model_dump_json()
    if isinstance(value, dict):
        try:
            # JSON alone erases tuple/list distinctions before the v1 additive
            # field rules run. Bind both the complete JSON bytes and Python
            # container representation, and distinguish DTO JSON-mode input.
            return 'dict:' + _dump(value) + '\0' + repr(value)
        except (TypeError, ValueError):
            return None
    return None


def encoded(value, field=None, *, ordered=False):
    if isinstance(value, Fragment):
        return value.text
    if value is None:
        return 'null'
    if isinstance(value, str):
        return encode_basestring(canonical(parse(value)) if field in DECIMALS else value)
    if type(value) is bool:
        return 'true' if value else 'false'
    if type(value) is int:
        return str(value)
    if isinstance(value, Contract):
        if type(value).__name__ in TIMED:
            # Time changes do not invalidate immutable topology or trace members.
            # The complete remaining DTO bytes still bind every cached field.
            raw = value.model_dump_json(exclude={'effective_time'})
            timed_key = type(value), raw
            parts = _timed.get(timed_key)
            if parts is None:
                parts = _parts({name: getattr(value, name) for name in type(value).model_fields
                                if name != 'effective_time'}, model=True)
                before = ','.join(part for key, part in parts if key < 'effective_time')
                after = ','.join(part for key, part in parts if key > 'effective_time')
                parts = (before + ',' if before else '', ',' + after if after else '')
                _timed.put(timed_key, parts, len(raw.encode()) + sum(len(p.encode()) for p in parts))
            return '{' + parts[0] + '"effective_time":' + encoded(value.effective_time) + parts[1] + '}'
        key = None
        document_key = None
        if type(value).__name__ in DOCUMENTS:
            document_key = (type(value), sha256(value.model_dump_json().encode()).digest())
            hit = _documents.get(document_key)
            if hit is not None:
                return hit
        if type(value).__name__ in MODELS and type(value).__module__.startswith('poliscope_engine.contracts.'):
            raw = value.model_dump_json()
            key = (type(value), raw)
            hit = _models.get(key)
            if hit is not None:
                return hit
        data = {name: getattr(value, name) for name in type(value).model_fields}
        result = _object(data, model=True)
        if key is not None:
            _models.put(key, result, len(raw.encode()) + len(result.encode()))
        if document_key is not None:
            _documents.put(document_key, result, len(result.encode()) + 64)
        return result
    if is_dataclass(value):
        return _object({f.name: getattr(value, f.name) for f in fields(value)})
    if isinstance(value, Decimal):
        return _dump(canonical(value))
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            return encode(normalize(value, field))
        return _object(value)
    if isinstance(value, (tuple, list, set, frozenset)):
        sorting = not ordered and (field in UNORDERED or isinstance(value, (set, frozenset)))
        key = None
        if field in ARRAYS and len(value) >= 8 and not isinstance(value, (set, frozenset)):
            sources = tuple(_source(item) for item in value)
            if all(source is not None for source in sources):
                key = (field, sorting, sources)
                hit = _arrays.get(key)
                if hit is not None:
                    return hit
        parts = [encoded(item) for item in value]
        if sorting:
            parts.sort()
        result = '[' + ','.join(parts) + ']'
        if key is not None:
            _arrays.put(key, result, sum(len(source.encode()) for source in sources) + len(result.encode()))
        return result
    if hasattr(value, 'model_dump'):
        return encode(normalize(value, field))
    return _dump(value)
