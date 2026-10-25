"""Versioned, schema-specific canonical encoding. No timestamps/request IDs exist."""
from dataclasses import asdict, is_dataclass
from decimal import Decimal
from hashlib import sha256
import json
from poliscope_engine.numeric import canonical, parse

# These are declared sets/maps. All other arrays retain semantic order, notably
# claim_order, update_order, event_ids, NodeKey tuples and expression operands.
UNORDERED = frozenset('''entities scopes values owners populations relationships
instances bindings fixed_inputs claims account_producers policies policy_rules
policy_inputs world_inputs assumption_inputs realization_inputs conditions
accounts postings reservations subtotals choices requirements solvers equations
terms starting_state definitions graphs reviews implementations times units
source_ids assumption_ids fixture_ids inputs owned_state preconditions diagnostics
traces fixtures properties scope_kinds entity_kinds read_partitions write_state_refs
source_refs assumption_refs input_refs output_refs state_refs property_refs
participant_ids entity_ids account_refs choice_refs member_ids posting_ids
not_applicable_ids results observations nodes trace_edges
account_bindings claim_owners refined_claim_ids pending_claims'''.split())
DECIMALS = frozenset('''quantum maximum opening amount requested per_unit
access_limit loss_per_unit coefficient constant tolerance closing available
outstanding_reserved actual unmet scale seconds'''.split())


def normalize(value, field=None):
    if hasattr(value, 'model_dump'):
        value = value.model_dump(mode='json')
    elif is_dataclass(value):
        value = asdict(value)
    if isinstance(value, Decimal):
        return canonical(value)
    if isinstance(value, dict):
        result = {k: normalize(v, k) for k, v in value.items()}
        if value.get('kind') == 'quantity' and 'value' in value:
            result['value'] = canonical(parse(value['value']))
        # Measurement procedure operands are semantic sequences, unlike port
        # declarations. Difference and ratio must retain authored input order.
        if value.get('aggregation') == 'same_scope' and 'procedure' in value:
            result['inputs'] = [normalize(v) for v in value['inputs']]
        # StartingValue contains a decimal value without a WorldValue tag.
        if 'node' in value and isinstance(value.get('value'), str):
            result['value'] = canonical(parse(value['value']))
        return result
    if isinstance(value, (tuple, list, set, frozenset)):
        result = [normalize(v) for v in value]
        if field in UNORDERED or isinstance(value, (set, frozenset)):
            result.sort(key=encode)
        return result
    if field in DECIMALS and isinstance(value, str):
        return canonical(parse(value))
    return value


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def serialized(value):
    return encode(normalize(value))


def digest(value):
    return 'sha256:' + sha256(serialized(value).encode('utf-8')).hexdigest()
