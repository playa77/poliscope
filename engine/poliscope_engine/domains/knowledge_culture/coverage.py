"""Exact standalone source-gap reconciliation; no source model activation."""
from poliscope_engine.accounts import fail
from poliscope_engine.contracts.knowledge_culture import EducationCoverage

MODEL_REFS = ['authored:education-capacity-v1', 'authored:education/precedence']
SCOPES = ['settlement', 'region']
# Only explicit education prerequisites; no learning or cultural outcomes.
SUPPORTED = {'society:domain/06/2', 'society:domain/06/2/1', 'society:domain/06/2/2'}

def validate_coverage(data, source):
    coverage = EducationCoverage.model_validate(data)
    if (coverage.source_revision != source['revision']
            or coverage.source_archive_digest != source['archive_digest']):
        fail('knowledge_culture_source_drift')
    expected = {}
    domain = next(d for d in source['domains'] if d['id'] == 'society:domain/06')
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
        fail('knowledge_culture_coverage_inventory')
    for sid, row in rows.items():
        if (row.title, row.documents, row.option_refs, row.classification) != expected[sid]:
            fail('knowledge_culture_source_references')
        available = sid in SUPPORTED
        if (row.static_available != available
                or row.implementation_refs != (MODEL_REFS if available else [])
                or row.supported_scope_kinds != (SCOPES if available else [])
                or row.status != ('partial' if available else 'unsupported')
                or row.evidence_status != ('hypothetical' if available else 'unreviewed')):
            fail('knowledge_culture_coverage_availability')
    return coverage
