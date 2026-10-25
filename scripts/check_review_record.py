"""Require a changed package record declaring the validation route.

Checks a declaration, not reviewer identity or proof of human inspection.
Repository approval rules remain authoritative and are never modified here.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path
from ci_plan import documentation_only

ROOT = Path(__file__).resolve().parents[1]


DELIVERY = 'docs/roadmap/execution/delivery.json'
ACTIVE = 'docs/roadmap/execution/active-package.json'


def validate_delivery(changed, receipt, active, record):
    if documentation_only(changed):
        return
    package = receipt.get('package', '')
    if not re.fullmatch(r'(?:WP-\d{3}|DOM-\d{2})', package):
        raise ValueError('Deliver the full top-level work package, not a child')
    expected = f'docs/roadmap/execution/{package}.md'
    if DELIVERY not in changed or expected not in changed or receipt.get('record') != expected:
        raise ValueError('Change the delivery receipt and its full parent record')
    if not any(route in record.casefold() for route in (
            'solo-validated; agent review deferred', 'nonauthor review:')):
        raise ValueError('Declare the actual validation route in the parent record')
    if receipt.get('status') != 'complete' or not receipt.get('scope', '').strip():
        raise ValueError('Incomplete delivery: retain the active package and concrete blockers')
    criteria = receipt.get('acceptance', [])
    ids = [c.get('id') for c in criteria]
    if (not criteria or any(not i for i in ids) or len(set(ids)) != len(ids)
            or any(c.get('status') != 'passed' or not c.get('evidence') for c in criteria)):
        raise ValueError('Every declared acceptance item needs passing evidence')
    if receipt.get('kind') == 'work_package':
        if (ACTIVE not in changed or active.get('package') != package
                or active.get('status') != 'complete'
                or {c['id'] for c in active.get('acceptance', [])} != set(ids)
                or any(c.get('status') != 'passed' for c in active.get('acceptance', []))):
            raise ValueError('The active parent and every acceptance item must be complete')
    elif receipt.get('kind') == 'authorized_child':
        child = receipt.get('child', '')
        authorization = receipt.get('authorization', {})
        child_record = f'docs/roadmap/execution/{child}.md'
        if (not re.fullmatch(re.escape(package) + r'-[a-z0-9]+(?:-[a-z0-9]+)*', child)
                or child_record not in changed
                or authorization.get('source') != 'user' or authorization.get('scope') != child
                or not authorization.get('instruction', '').strip()
                or ACTIVE not in changed or active.get('package') != package
                or active.get('status') != 'in_progress' or active.get('execution_unit') != child
                or active.get('authorization') != authorization
                or not any(c.get('status') == 'pending' for c in active.get('acceptance', []))):
            raise ValueError('Child delivery requires explicit scoped user authorization and an open parent')
    elif receipt.get('kind') != 'maintenance':
        raise ValueError('Declare work_package, authorized_child or explicitly scoped corrective maintenance')


def check(root=ROOT, base=None):
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root).strip()
    baseline = subprocess.check_output(['git', 'rev-parse', 'origin/main'], cwd=root).strip()
    base = base or ('HEAD^' if head == baseline else 'origin/main')
    changed = subprocess.check_output(['git', 'diff', '--name-only', base, 'HEAD'], cwd=root, text=True).splitlines()
    if documentation_only(changed):
        return
    receipt = json.loads((root / DELIVERY).read_text())
    active = json.loads((root / ACTIVE).read_text())
    # Validate the path before opening a candidate-supplied record.
    package = receipt.get('package', '')
    record = (root / f'docs/roadmap/execution/{package}.md').read_text() if re.fullmatch(
        r'(?:WP-\d{3}|DOM-\d{2})', package) else ''
    validate_delivery(changed, receipt, active, record)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base')
    check(base=parser.parse_args().base)
    print('Delivery scope declared; actual acceptance and repository approvals remain required.')
