"""Require a changed package record declaring the validation route.

Checks a declaration, not reviewer identity or proof of human inspection.
Repository approval rules remain authoritative and are never modified here.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(root=ROOT):
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root).strip()
    baseline = subprocess.check_output(['git', 'rev-parse', 'origin/main'], cwd=root).strip()
    base = 'HEAD^' if head == baseline else 'origin/main'
    changed = subprocess.check_output(['git', 'diff', '--name-only', base, 'HEAD'], cwd=root, text=True).splitlines()
    records = [root / name for name in changed
               if name.startswith('docs/roadmap/execution/WP-') and name.endswith('.md')]
    if not any(path.is_file() and ('solo-validated; agent review deferred' in path.read_text()
               or 'nonauthor review:' in path.read_text()) for path in records):
        raise ValueError('Candidate needs a changed WP record declaring SV/deferred or nonauthor review')


if __name__ == '__main__':
    check()
    print('Validation route declared; actual inspection and repository approvals remain required.')
