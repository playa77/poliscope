"""Strict source reconciliation of standalone research coverage; no activation."""
from poliscope_engine.accounts import fail
from poliscope_engine.contracts.economy import EconomyCoverage

MODEL_REFS = ['authored:economy-access-work-v1', 'authored:economy/procedure']
SCOPES = ['settlement', 'region']
SUPPORTED = {'society:domain/02/1', 'society:domain/02/2',
             'society:domain/02/2/1', 'society:domain/02/2/2',
             'society:domain/02/3', 'society:domain/02/4'}


def validate_coverage(data, source):
    coverage = EconomyCoverage.model_validate(data)
    if (coverage.source_revision != source['revision']
            or coverage.source_archive_digest != source['archive_digest']):
        fail('economy_source_drift')
    expected = {}
    domain = next(d for d in source['domains'] if d['id'] == 'society:domain/02')
    for branch in domain['branches']:
        expected[branch['id']] = (branch['title'], [], [], 'catalog')
        for leaf in branch['leaves']:
            expected[leaf['id']] = (leaf['title'], leaf['documents'], [], 'catalog')
    for decision in source['decisions']:
        expected['society:' + decision['id']] = (decision['title'], decision['amends'], decision['option_ids'], 'provenance')
    for decision in source['system_decisions']:
        expected['society:' + decision['id']] = (decision['id'], [], [], 'provenance')
    rows = {r.source_id: r for r in coverage.entries}
    if len(rows) != len(coverage.entries) or set(rows) != set(expected):
        fail('economy_coverage_inventory')
    for sid, row in rows.items():
        if (row.title, row.documents, row.option_refs, row.classification) != expected[sid]:
            fail('economy_source_references')
        available = sid in SUPPORTED
        if (row.static_available != available
                or row.implementation_refs != (MODEL_REFS if available else [])
                or row.supported_scope_kinds != (SCOPES if available else [])
                or row.status != ('partial' if available else 'unsupported')
                or row.evidence_status != ('hypothetical' if available else 'unreviewed')):
            fail('economy_coverage_availability')
    return coverage
