"""Run checks into fresh, candidate-bound evidence; never infer milestone readiness."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def candidate(root=ROOT):
    paths = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others',
                                     '--exclude-standard'], cwd=root).split(b'\0')
    digest = hashlib.sha256()
    for raw in sorted(set(paths) - {b''}):
        path = root / os.fsdecode(raw)
        digest.update(raw + b'\0')
        content = os.fsencode(os.readlink(path)) if path.is_symlink() else (path.read_bytes() if path.is_file() else b'DELETED')
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


def summarize(path):
    tree = ET.parse(path)
    cases = list(tree.iter('testcase'))
    if not cases:
        raise ValueError('Zero collected tests')
    counts = dict(tests=len(cases), failed=0, skipped=0)
    reasons = []
    identities = []
    for case in cases:
        identities.append({'file': case.get('file'), 'class': case.get('classname'),
                           'name': case.get('name')})
        for child in case:
            if child.tag in ('failure', 'error'):
                counts['failed'] += 1
            if child.tag == 'skipped':
                counts['skipped'] += 1
                reasons.append(child.get('message') or child.text or 'unspecified')
    # Suite-level collection errors may exist without testcase failures.
    if any(int(suite.get('errors', '0')) for suite in tree.iter('testsuite')):
        counts['failed'] = max(1, counts['failed'])
    return {**counts, 'skip_reasons': reasons, 'cases': identities}


def run(suite, output, root=ROOT):
    output.mkdir(parents=True, exist_ok=False)
    before = candidate(root)
    report = output / 'junit.xml'
    commands = {
        'engine': ['uv', 'run', '--frozen', 'pytest', f'--junitxml={report}'],
        'unit': ['npm', 'exec', '--', 'vitest', 'run', '--reporter=default',
                 '--reporter=junit', f'--outputFile={report}'],
        'desktop': ['npm', 'exec', '--', 'playwright', 'test', '--reporter=junit'],
    }
    env = os.environ.copy()
    env['PLAYWRIGHT_JUNIT_OUTPUT_FILE'] = str(report)
    env['PLAYWRIGHT_OUTPUT_DIR'] = str(output / 'desktop-artifacts')
    record = {'version': 1, 'run_id': str(uuid.uuid4()), 'suite': suite,
              'candidate': before, 'head': subprocess.check_output(
                  ['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
              'started_ns': time.time_ns(), 'command': commands[suite],
              'runtime': {'platform': platform.platform(), 'python': sys.version},
              'fixtures_sha256': hashlib.sha256((root / 'tests/fixtures/synthetic.json').read_bytes()).hexdigest(),
              'readiness': False}
    for tool in ('node', 'npm', 'uv'):
        record['runtime'][tool] = subprocess.check_output([tool, '--version'], text=True).strip()
    # Environment values and command output are not persisted: future failures can
    # contain private payloads. JUnit artifacts must use synthetic fixtures only.
    with tempfile.TemporaryDirectory(prefix='poliscope-check-') as private:
        env['POLISCOPE_USER_DATA'] = private
        result = subprocess.run(commands[suite], cwd=root, env=env, check=False)
    record['exit_code'] = result.returncode
    record['finished_ns'] = time.time_ns()
    try:
        record['results'] = summarize(report)
        record['report_sha256'] = hashlib.sha256(report.read_bytes()).hexdigest()
        if result.returncode or record['results']['failed'] or record['results']['skipped']:
            raise ValueError('Failed or skipped required tests')
        if candidate(root) != before:
            raise ValueError('Candidate changed during execution')
        record['status'] = 'passed'
    except (ValueError, OSError, ET.ParseError) as error:
        record.update(status='failed', error=str(error))
    (output / 'evidence.json').write_text(json.dumps(record, indent=2) + '\n')
    return record['status'] == 'passed'


def verify(directory, root=ROOT):
    record = json.loads((directory / 'evidence.json').read_text())
    report = directory / 'junit.xml'
    if record['status'] != 'passed' or record['exit_code'] != 0:
        raise ValueError('Run did not pass')
    if record['candidate'] != candidate(root):
        raise ValueError('Stale candidate evidence')
    if hashlib.sha256(report.read_bytes()).hexdigest() != record['report_sha256']:
        raise ValueError('Report changed after execution')
    results = summarize(report)
    if results != record['results'] or results['failed'] or results['skipped']:
        raise ValueError('Invalid test results')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('suite', choices=['engine', 'unit', 'desktop', 'verify'])
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.suite == 'verify':
            verify(args.output.resolve())
        elif not run(args.suite, args.output.resolve()):
            return 1
    except (OSError, ValueError, KeyError, ET.ParseError) as error:
        print(f'Evidence rejected: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
