"""Reconcile static-domain declarations; never certify WP-032 execution."""
import argparse
from collections import Counter
import importlib
import json
from pathlib import Path

from poliscope_engine.domains import conformance_catalog

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'docs/roadmap/execution/static-readiness.json'
DOMAINS = (
    'provisioning', 'economy', 'governance', 'law_conflict',
    'social_organization', 'knowledge_culture', 'health', 'infrastructure',
    'communication', 'environment', 'meaning_identity', 'security_risk',
)


def read(path):
    return json.loads(path.read_text())


def audit(root=ROOT):
    source = read(root / 'docs/roadmap/execution/society/inventory.json')
    registry = conformance_catalog(root / 'engine/poliscope_engine/domains')
    modules, pairs = registry.modules, registry.pairs
    if {m.domain for m in registry.modules} != set(DOMAINS):
        raise ValueError('incomplete_domain_inventory')
    # Compare the topology to the maintained domain register, rather than only
    # counting pairs: a substituted edge must not conceal an omitted counterpart.
    import re
    register = (root / 'docs/roadmap/domain_work_packages.md').read_text()
    expected_pairs = set()
    for section in register.split('### DOM-')[1:]:
        owner = int(section[:2])
        counterparts = section.split('**Integration counterparts:**', 1)[1].split('\n', 1)[0]
        targets = (range(1, 13) if 'all other domains' in counterparts
                   else map(int, re.findall(r'DOM-(\d+)', counterparts)))
        expected_pairs.update(f'pair:DOM-{min(owner, target):02}:DOM-{max(owner, target):02}'
                              for target in targets if owner != target)
    if {p.id for p in pairs} != expected_pairs:
        raise ValueError('counterpart_inventory_drift')
    interfaces = {i.id for m in modules for i in m.interfaces}
    for pair in pairs:
        numbers = [int(n) for n in re.findall(r'DOM-(\d+)', pair.id)]
        if set(pair.domains) != {DOMAINS[n - 1] for n in numbers}:
            raise ValueError('counterpart_domain_mismatch')
        if not set(pair.interface_refs) <= interfaces:
            raise ValueError('undeclared_counterpart_interface')
    rows = []
    for domain in DOMAINS:
        validate = importlib.import_module(
            f'poliscope_engine.domains.{domain}.coverage').validate_coverage
        coverage = validate(read(root / 'content' / domain.replace('_', '-') /
                                 'coverage-v1.json'), source)
        module = next(m for m in modules if m.domain == domain)
        domain_number = DOMAINS.index(domain) + 1
        source_domain = next(d for d in source['domains']
                             if d['id'] == f'society:domain/{domain_number:02}')
        if {c.branch_id for c in module.coverage} != {b['id'] for b in source_domain['branches']}:
            raise ValueError('module_branch_inventory_drift')
        rows.append(dict(domain=domain, source_rows=len(coverage.entries),
            source_statuses=dict(sorted(Counter(r.status for r in coverage.entries).items())),
            static_source_rows=sum(r.static_available for r in coverage.entries),
            transition_source_rows=sum(r.transition_available for r in coverage.entries),
            source_activation=coverage.activation,
            declared_mechanisms=len(module.mechanisms),
            declared_interfaces=len(module.interfaces),
            catalog_statuses=dict(sorted(Counter(c.status for c in module.coverage).items()))))
    return dict(version=1, assessment='declarations_only', gate_acceptance='not_assessed',
        source_revision=source['revision'], source_archive_digest=source['archive_digest'],
        domains=rows, counterparts=[dict(id=p.id, domains=p.domains,
            owner=p.integration_owner, status=p.status,
            interfaces=p.interface_refs,
            fixtures=[f'{f.id}@{f.version}' for f in p.fixture_refs])
            for p in sorted(pairs, key=lambda p: p.id)],
        remaining_acceptance=[
            'Reviewed static mechanisms and typed ports registered for all twelve modules',
            'Actual counterpart fixtures with canonical identities, units, accounts and provenance',
            'All-domain education path and an entry choice originating in each domain',
            'Cross-view context and retained evidence through the actual engine/database',
            'Independent model/product review and complete WP-032 gate execution',
        ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check retained audit for drift')
    args = parser.parse_args()
    encoded = json.dumps(audit(), indent=2) + '\n'
    if args.check:
        if not SNAPSHOT.exists() or SNAPSHOT.read_text() != encoded:
            raise SystemExit('Static readiness audit drift; review and regenerate explicitly')
        print('Static declarations reconcile; WP-032 execution acceptance is not assessed')
    else:
        print(encoded, end='')


if __name__ == '__main__':
    main()
