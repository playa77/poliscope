"""Exact standalone source-gap reconciliation; no source model activation."""
from poliscope_engine.accounts import fail
from poliscope_engine.contracts.infrastructure import InfrastructureCoverage

MODEL_REFS = ['authored:infrastructure-reach-v1', 'authored:infrastructure/precedence']
SCOPES = ['settlement', 'region']
# Only explicit slot reach; no freight, construction or delivered service.
SUPPORTED = {'society:domain/08/1', 'society:domain/08/1/2'}

def validate_coverage(data, source):
    coverage = InfrastructureCoverage.model_validate(data)
    if (coverage.source_revision != source['revision']
            or coverage.source_archive_digest != source['archive_digest']):
        fail('infrastructure_source_drift')
    expected = {}
    domain = next(d for d in source['domains'] if d['id'] == 'society:domain/08')
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
        fail('infrastructure_coverage_inventory')
    for sid, row in rows.items():
        if (row.title, row.documents, row.option_refs, row.classification) != expected[sid]:
            fail('infrastructure_source_references')
        available = sid in SUPPORTED
        if (row.static_available != available
                or row.implementation_refs != (MODEL_REFS if available else [])
                or row.supported_scope_kinds != (SCOPES if available else [])
                or row.status != ('partial' if available else 'unsupported')
                or row.evidence_status != ('hypothetical' if available else 'unreviewed')):
            fail('infrastructure_coverage_availability')
    return coverage
