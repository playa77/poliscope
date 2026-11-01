"""Audit cumulative product evidence without inferring behavior from test names.

The baseline leaf ledger is intentionally immutable. This overlay preserves every
leaf, owner and first gate and exposes gaps rather than certifying documentation.
Only candidate-bound, inspected evidence can satisfy a production obligation.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from check_roadmap import validate_manifest
from evidence import candidate as current_candidate

ROOT = Path(__file__).resolve().parents[1]
DATA = Path('docs/roadmap/execution')
OUTCOMES = {'passed', 'failed', 'skipped', 'expected-failure', 'unrun'}


def read(root, name):
    return json.loads((root / DATA / name).read_text())


def validate_evidence(entry, candidate, root):
    """Require retained, bounded local artifacts and independent inspection notes."""
    if entry.get('outcome') not in OUTCOMES:
        raise ValueError('Unknown evidence outcome')
    if not entry.get('owner') or not entry.get('reason'):
        raise ValueError('Evidence needs an owner and reason')
    if entry['outcome'] == 'unrun':
        return
    if entry.get('candidate') != candidate:
        raise ValueError('Evidence candidate mismatch')
    artifacts = entry.get('artifacts', [])
    if not artifacts:
        raise ValueError('Executed evidence needs retained artifacts')
    for artifact in artifacts:
        path = (root / artifact['path']).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError('Missing or out-of-root artifact')
        if hashlib.sha256(path.read_bytes()).hexdigest() != artifact['sha256']:
            raise ValueError('Artifact digest mismatch')
    if entry['outcome'] == 'passed':
        if not entry.get('production_inspection'):
            raise ValueError('Passing evidence needs production-service inspection')
        targets = entry.get('tests', [])
        reports = [a for a in artifacts if a.get('format') == 'junit']
        if not targets or len(set(targets)) != len(targets) or not reports:
            raise ValueError('Passing production evidence needs exact executed JUnit targets')
        executed = []
        for artifact in reports:
            tree = ET.parse(root / artifact['path'])
            if any(int(s.get('errors', '0')) for s in tree.iter('testsuite')):
                raise ValueError('Report contains collection errors')
            executed.extend(tree.iter('testcase'))
        for target in targets:
            matches = [t for t in executed if t.get('name') == target]
            if len(matches) != 1 or any(c.tag in {'failure', 'error', 'skipped'} for c in matches[0]):
                raise ValueError('Target missing, duplicated, failed or skipped')


def audit(root=ROOT, evidence=None):
    manifest = read(root, 'gates.json')
    validate_manifest(manifest, root)
    ledger = read(root, 'requirements.json')
    regressions = read(root, 'regressions.json')['findings']
    for source in ledger['sources'].values():
        if hashlib.sha256((root / source['path']).read_bytes()).hexdigest() != source['sha256']:
            raise ValueError('Requirement source identity drift')
    evidence = evidence or {'candidate': None, 'requirements': {}, 'cases': {}}
    candidate = evidence.get('candidate')
    if not candidate and (evidence.get('requirements') or evidence.get('cases') or evidence.get('regressions')):
        raise ValueError('Evidence needs a frozen candidate')
    leaves = {r['id']: r for r in ledger['requirements']}
    if len(leaves) != len(ledger['requirements']):
        raise ValueError('Duplicate requirement leaf')
    if set(evidence.get('requirements', {})) - leaves.keys():
        raise ValueError('Unknown requirement evidence')
    if set(evidence.get('cases', {})) - manifest['cases'].keys():
        raise ValueError('Unknown scenario evidence')
    if set(evidence.get('regressions', {})) - regressions.keys():
        raise ValueError('Unknown regression evidence')
    groups = ('requirements', 'cases', 'regressions')
    if any(e.get('outcome') != 'unrun' for g in groups for e in evidence.get(g, {}).values()):
        if candidate != current_candidate(root):
            raise ValueError('Stale candidate evidence')
    for entries in (evidence.get('requirements', {}), evidence.get('cases', {}),
                    evidence.get('regressions', {})):
        for entry in entries.values():
            validate_evidence(entry, candidate, root)
    for cid, entry in evidence.get('cases', {}).items():
        if entry['outcome'] == 'passed' and any(not re.match(
                r'^(?:test_offline_gate\[)?' + re.escape(cid) + r'[ :]', target)
                for target in entry['tests']):
            raise ValueError(f'{cid}: exact mandatory case ID missing from target')
    rows = []
    for rid, row in leaves.items():
        if not row.get('verification_owner') or not row.get('first_gate'):
            raise ValueError(f'{rid}: missing owner/first gate')
        current = evidence.get('requirements', {}).get(rid)
        parent = re.match(r'(WP-\d{3}|DOM-\d{2})', row['verification_package'])
        record = DATA / (parent[0] + '.md') if parent else None
        supporting = [record.as_posix()] if record and (root / record).is_file() else []
        rows.append(dict(id=rid, owner=row['verification_owner'], supporting_records=supporting,
            first_gate=row['first_gate'], verification_package=row['verification_package'],
            outcome=current['outcome'] if current else 'unrun',
            evidence=current or None,
            disposition='Current production evidence required' if not current else current['reason']))
    owners = read(root, 'case-owners.json')['cases']
    cases = []
    for cid in manifest['gates']['G7']:
        current = evidence.get('cases', {}).get(cid)
        cases.append(dict(id=cid, owner=owners[cid]['verification_child'], first_gate=manifest['cases'][cid]['first_gate'],
            scope=manifest['cases'][cid]['scope'],
            outcome=current['outcome'] if current else 'unrun', evidence=current or None))
    by_case = {r['id']: r for r in cases}
    rt = []
    if set(regressions) != {f'RT-{n:02}' for n in range(1, 15)}:
        raise ValueError('Incomplete RT-01–14 inventory')
    for rid, row in regressions.items():
        if set(row['cases']) - by_case.keys():
            raise ValueError(f'{rid}: unknown mandatory case')
        current = evidence.get('regressions', {}).get(rid)
        if current and current['outcome'] == 'passed' and not all(
                by_case[c]['outcome'] == 'passed' for c in row['cases']):
            raise ValueError(f'{rid}: linked scenario evidence missing')
        rt.append(dict(id=rid, first_gate=row['first_gate'], cases=row['cases'],
            outcome=current['outcome'] if current else 'unrun', evidence=current or None,
            limitation='Requires inspection of this specific obligation, not just linked scenario names'))
    # Inspect the current source coverage, not the obsolete initial release plan.
    domains = []
    for path in sorted((root / 'content').glob('*/coverage-v1.json')):
        coverage = json.loads(path.read_text())
        entries = coverage['entries']
        domains.append(dict(domain=path.parent.name, path=path.relative_to(root).as_posix(),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(), activation=coverage['activation'],
            source_revision=coverage['source_revision'], source_archive_digest=coverage['source_archive_digest'],
            rows=len(entries), statuses=dict(Counter(e['status'] for e in entries)),
            evidence_statuses=dict(Counter(e['evidence_status'] for e in entries)),
            static_rows=sum(e['static_available'] for e in entries),
            transition_rows=sum(e['transition_available'] for e in entries)))
    if len(domains) != 12 or len({d['domain'] for d in domains}) != 12:
        raise ValueError('Incomplete twelve-domain coverage inventory')
    counts = dict(Counter(r['outcome'] for r in rows))
    scenario_counts = dict(Counter(r['outcome'] for r in cases))
    return dict(version=1, package='WP-055', candidate=candidate,
        acceptance='not_established', review_route='solo-validated; agent review deferred',
        limitation='Evidence completeness is necessary, not sufficient for model validity or product acceptance. Native and live-provider outcomes require separate records.',
        requirement_counts={k: counts.get(k, 0) for k in sorted(OUTCOMES)},
        scenario_counts={k: scenario_counts.get(k, 0) for k in sorted(OUTCOMES)},
        requirements=rows, cases=cases, regressions=rt, model_inventory=domains)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(evidence=json.loads(args.evidence.read_text()) if args.evidence else None)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('acceptance', 'requirement_counts', 'scenario_counts')}))


if __name__ == '__main__':
    main()
