"""Bind a full mandatory-case selection to fresh executed test reports.

This checks execution evidence, not whether a test exercises production services.
That judgment remains part of the package's SV/nonauthor inspection.
"""
import argparse
import json
import re
from pathlib import Path
from check_roadmap import validate_manifest, validate_selection
from evidence import ROOT, verify


def validate(selection, records, manifest):
    validate_selection(manifest, selection)
    executed = []
    for record in records:
        executed.extend(record['results']['cases'])
    for case in selection['cases']:
        for target in case['tests']:
            # Targets are exact JUnit testcase names. Every application test must
            # carry its exact case ID followed by a space or colon. Pytest uses
            # the explicit parametrized test_offline_gate[case ID ...] name.
            if not re.match(r'^(?:test_offline_gate\[)?' + re.escape(case['id']) + r'[ :]', target):
                raise ValueError(f"{case['id']}: target must carry its case ID")
            matches = [test for test in executed if test['name'] == target]
            if len(matches) != 1:
                raise ValueError(f'{target}: expected exactly one executed test, got {len(matches)}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('selection', type=Path)
    parser.add_argument('evidence', nargs='+', type=Path)
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'docs/roadmap/execution/gates.json').read_text())
    try:
        validate_manifest(manifest)
        validate(json.loads(args.selection.read_text()), [verify(p) for p in args.evidence], manifest)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f'Gate evidence rejected: {error}\n')
    print('Mandatory subcase execution verified; production-service inspection remains required.')


if __name__ == '__main__':
    main()
