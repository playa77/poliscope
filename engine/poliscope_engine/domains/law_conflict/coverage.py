"""Strict source reconciliation of standalone research coverage; no activation."""
from poliscope_engine.accounts import fail
from poliscope_engine.contracts.law_conflict import AdjudicationCoverage

MODEL_REFS = ['authored:law-adjudication-v1', 'authored:adjudication/queue']
SCOPES = ['settlement', 'region']
SUPPORTED = {'society:domain/04/1', 'society:domain/04/1/2', 'society:domain/04/3', 'society:domain/04/3/1'}


def validate_coverage(data, source):
    coverage = AdjudicationCoverage.model_validate(data)
    if (coverage.source_revision != source['revision']
            or coverage.source_archive_digest != source['archive_digest']):
        fail('law_conflict_source_drift')
    expected = {}
    domain = next(d for d in source['domains'] if d['id'] == 'society:domain/04')
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
        fail('law_conflict_coverage_inventory')
    for sid, row in rows.items():
        if (row.title, row.documents, row.option_refs, row.classification) != expected[sid]:
            fail('law_conflict_source_references')
        available = sid in SUPPORTED
        if (row.static_available != available
                or row.implementation_refs != (MODEL_REFS if available else [])
                or row.supported_scope_kinds != (SCOPES if available else [])
                or row.status != ('partial' if available else 'unsupported')
                or row.evidence_status != ('hypothetical' if available else 'unreviewed')):
            fail('law_conflict_coverage_availability')
    return coverage
