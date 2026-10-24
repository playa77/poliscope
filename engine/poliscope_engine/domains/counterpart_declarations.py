"""Fixed authored declarations shared by hosts; never callbacks or reviews.

Add a pair's data file here once. Catalog completeness does not activate it:
each host still supplies only its own implementations and explicit reviews.
Cache immutable JSON, returning fresh DTOs to preserve mutation isolation.
"""
from functools import cache
import json
from pathlib import Path

from poliscope_engine.contracts.mechanisms import MechanismDefinition

FILES = (
    'static-system-v1.json',
    'provisioning/counterpart-v1.json',
    'provisioning/care-counterpart-v1.json',
    'provisioning/education-counterpart-v1.json',
    'provisioning/health-counterpart-v1.json',
    'provisioning/infrastructure-counterpart-v1.json',
    'provisioning/continuity-counterpart-v1.json',
    'provisioning/environment-counterpart-v1.json',
    'economy/governance-counterpart-v1.json',
    'economy/adjudication-counterpart-v1.json',
    'economy/care-counterpart-v1.json',
    'economy/education-counterpart-v1.json',
    'economy/health-counterpart-v1.json',
    'economy/infrastructure-counterpart-v1.json',
    'governance/adjudication-counterpart-v1.json',
    'governance/education-counterpart-v1.json',
    'governance/communication-counterpart-v1.json',
    'governance/participation-counterpart-v1.json',
    'governance/continuity-counterpart-v1.json',
    'governance/infrastructure-counterpart-v1.json',
    'law_conflict/care-counterpart-v1.json',
    'law_conflict/education-counterpart-v1.json',
    'law_conflict/health-counterpart-v1.json',
    'law_conflict/communication-counterpart-v1.json',
    'law_conflict/participation-counterpart-v1.json',
    'law_conflict/continuity-counterpart-v1.json',
    'social_organization/education-counterpart-v1.json',
)


@cache
def _retained():
    root = Path(__file__).parent
    values = [MechanismDefinition.model_validate(item)
              for name in FILES for item in json.loads((root / name).read_text())]
    keys = [(d.id, d.version) for d in values]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate_counterpart_declaration')
    return (
        tuple(d.model_dump_json() for d in values),
        tuple(sorted({ref for d in values for ref in d.source_refs})),
        tuple(sorted({(f.fixture.id, f.fixture.version) for d in values for f in d.fixtures})),
    )


def definitions():
    return tuple(map(MechanismDefinition.model_validate_json, _retained()[0]))


def sources():
    return _retained()[1]


def fixtures():
    return _retained()[2]
