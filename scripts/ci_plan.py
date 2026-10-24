"""Choose validation cost by event; keep one stable, fail-closed checks job."""
import json
import os
from pathlib import Path
import subprocess


def documentation_only(paths):
    return bool(paths) and all(path.endswith('.md') for path in paths)


def mode_for(event, paths):
    if event == 'push':
        return 'smoke'
    if event == 'pull_request' and documentation_only(paths):
        return 'docs'
    return 'full'


def check_results(mode, results):
    expected = {'full': {'engine', 'desktop'}, 'docs': {'docs'}, 'smoke': {'smoke'}}
    if mode not in expected or results.get('plan', {}).get('result') != 'success':
        raise ValueError('Validation plan failed or is missing')
    for job in ('engine', 'desktop', 'docs', 'smoke'):
        wanted = 'success' if job in expected[mode] else 'skipped'
        if results.get(job, {}).get('result') != wanted:
            raise ValueError(f'{job}: expected {wanted}')


def changed_paths(base, head='HEAD'):
    return subprocess.check_output([
        'git', 'diff', '--name-only', '-z', base, head,
    ]).decode().split('\0')[:-1]


def main():
    if os.environ.get('CI_RESULTS'):
        check_results(os.environ['CI_MODE'], json.loads(os.environ['CI_RESULTS']))
        return
    event = os.environ['GITHUB_EVENT_NAME']
    payload = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    base = (payload['pull_request']['base']['sha'] if event == 'pull_request' else
            payload['merge_group']['base_sha'] if event == 'merge_group' else
            payload.get('before', 'HEAD'))
    paths = changed_paths(base) if event in ('pull_request', 'merge_group') else []
    mode = mode_for(event, paths)
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        output.write(f'mode={mode}\nbase={base}\n')
    print(f'Validation mode: {mode}; {len(paths)} changed paths')


if __name__ == '__main__':
    main()
