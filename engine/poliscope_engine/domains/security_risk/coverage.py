"""Exact standalone source-gap reconciliation; no source model activation."""
from poliscope_engine.accounts import fail
from poliscope_engine.contracts.security_risk import ContinuityCoverage

MODEL_REFS = ['authored:continuity-prerequisites-v1', 'authored:continuity/precedence']
SCOPES = ['settlement', 'region']
# Response-slot prerequisites only, without empirical hazards or outcomes.
SUPPORTED = {'society:domain/12/1', 'society:domain/12/1/3',
             'society:domain/12/2', 'society:domain/12/2/1', 'society:domain/12/2/2'}

def validate_coverage(data, source):
    coverage = ContinuityCoverage.model_validate(data)
    if (coverage.source_revision != source['revision']
            or coverage.source_archive_digest != source['archive_digest']):
        fail('continuity_source_drift')
    expected = {}
    domain = next(d for d in source['domains'] if d['id'] == 'society:domain/12')
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
        fail('continuity_coverage_inventory')
    for sid, row in rows.items():
        if (row.title, row.documents, row.option_refs, row.classification) != expected[sid]:
            fail('continuity_source_references')
        available = sid in SUPPORTED
        if (row.static_available != available
                or row.implementation_refs != (MODEL_REFS if available else [])
                or row.supported_scope_kinds != (SCOPES if available else [])
                or row.status != ('partial' if available else 'unsupported')
                or row.evidence_status != ('hypothetical' if available else 'unreviewed')):
            fail('continuity_coverage_availability')
    return coverage
