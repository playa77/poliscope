"""Reconcile research annotations with the pinned source; never activate them."""
from poliscope_engine.accounts import fail
from poliscope_engine.contracts.provisioning import ProvisioningCoverage


def validate_coverage(data, source):
    coverage = ProvisioningCoverage.model_validate(data)
    if (coverage.source_revision != source['revision']
            or coverage.source_archive_digest != source['archive_digest']):
        fail('provisioning_source_drift')
    expected = {}
    for branch in source['domains'][0]['branches']:
        expected[branch['id']] = ([], [])
        for leaf in branch['leaves']:
            expected[leaf['id']] = (leaf['documents'], [])
    for decision in source['decisions']:
        expected['society:' + decision['id']] = (decision['amends'], decision['option_ids'])
    for decision in source['system_decisions']:
        expected['society:' + decision['id']] = ([], [])
    rows = {r.source_id: r for r in coverage.entries}
    if len(rows) != len(coverage.entries) or set(rows) != set(expected):
        fail('provisioning_coverage_inventory')
    for sid, row in rows.items():
        if (row.documents, row.option_refs) != expected[sid]:
            fail('provisioning_source_references')
        if row.static_available:
            if (row.classification != 'catalog' or row.status != 'partial'
                    or row.evidence_status != 'hypothetical'
                    or not row.implementation_refs or not row.supported_scope_kinds):
                fail('provisioning_coverage_availability')
        elif row.implementation_refs or row.supported_scope_kinds:
            fail('provisioning_coverage_availability')
        if sid.startswith('society:DEC-') and (row.static_available or row.evidence_status != 'unreviewed'):
            fail('provisioning_source_activation')
    return coverage
