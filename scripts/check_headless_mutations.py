"""Run WP-019 invariant mutations in temporary source copies, preserving checkout.

Each mutant must import from its private source tree and fail its assigned test
with an assertion (not collection/import/setup failure). No test files are edited.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from evidence import candidate

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = {
    'conservation': ('allocations/__init__.py',
        'value = amount * quantity(output.per_unit)',
        'value = 2 * amount * quantity(output.per_unit)',
        'test_complete_headless_workflow_and_retained_futures'),
    'stale-check': ('revisions/__init__.py',
        'if state.context.revision_id != context.revision_id:',
        'if False:  # deliberately permit stale application',
        'test_stale_tampered_conflicting_and_lost_reply'),
    'goal-isolation': ('revisions/__init__.py',
        'result = evaluate(graph(inputs, civilization_id), inputs.design, inputs.assumptions,',
        "result = evaluate(graph(inputs, civilization_id), inputs.design.model_copy(update={'effective_time': inputs.design.effective_time.model_copy(update={'tick': 1})}) if inputs.goals else inputs.design, inputs.assumptions,",
        'test_complete_headless_workflow_and_retained_futures'),
    'shared-identity': ('world/membership.py',
        'coefficients[identity] = Fraction(1)',
        'coefficients[identity] = Fraction(len(rules))',
        'test_overlap_and_policy_conflicts_are_order_invariant'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    before_candidate = candidate(ROOT)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    results = []
    with tempfile.TemporaryDirectory(prefix='poliscope-wp019-mutants-') as directory:
        for name, (file, before, after, test) in MUTATIONS.items():
            base = Path(directory) / name
            package = base / 'poliscope_engine'
            shutil.copytree(ROOT / 'engine/poliscope_engine', package,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            path = package / file
            source = path.read_text()
            if source.count(before) != 1:
                raise SystemExit(f'{name}: mutation site changed; inspect and update explicitly')
            path.write_text(source.replace(before, after))
            env = dict(os.environ, PYTHONPATH=str(base))
            # Confirm editable installation does not shadow the mutated package.
            check = subprocess.run([sys.executable, '-c',
                'import poliscope_engine; print(poliscope_engine.__file__)'], env=env,
                cwd=ROOT, text=True, capture_output=True, check=True)
            if Path(check.stdout.strip()).parent != package:
                raise SystemExit(f'{name}: mutant import was shadowed')
            target = f'tests/engine/test_headless_slice.py::{test}'
            run = subprocess.run([sys.executable, '-m', 'pytest', target, '-q', '--tb=short'],
                cwd=ROOT, env=env, text=True, capture_output=True, timeout=120)
            killed = run.returncode == 1 and '1 failed' in run.stdout and (
                'AssertionError' in run.stdout or 'E   assert ' in run.stdout or 'DID NOT RAISE' in run.stdout)
            results.append(dict(mutation=name, target=target, detected=killed,
                                returncode=run.returncode, stdout=run.stdout, stderr=run.stderr))
    if candidate(ROOT) != before_candidate:
        raise SystemExit('Source candidate changed during mutation checks')
    args.output.write_text(json.dumps(dict(version=1, candidate=before_candidate, head=head, results=results), indent=2) + '\n')
    for result in results:
        print(f"{result['mutation']}: {'detected' if result['detected'] else 'NOT DETECTED'}")
    return 0 if all(r['detected'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
