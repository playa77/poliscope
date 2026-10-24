"""Prevent missing validation and partial-child handoffs from passing checks."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from ci_plan import check_results, mode_for
from check_review_record import ACTIVE, DELIVERY, validate_delivery


class DeliveryWorkflowTests(unittest.TestCase):
    def test_event_routes_keep_full_queue_and_release_checks(self):
        self.assertEqual(mode_for('pull_request', ['README.md', 'docs/guide.md']), 'docs')
        self.assertEqual(mode_for('push', ['engine/main.py']), 'smoke')
        for event, paths in [('pull_request', []), ('pull_request', ['README.md', 'contracts/x.json']),
                             ('pull_request', ['.github/workflows/validation.yml']),
                             ('merge_group', ['README.md']), ('schedule', []),
                             ('workflow_dispatch', []), ('unknown', [])]:
            self.assertEqual(mode_for(event, paths), 'full')

    def test_aggregate_rejects_failure_cancellation_omission_and_wrong_skips(self):
        for mode, selected in [('full', {'engine', 'desktop'}), ('docs', {'docs'}), ('smoke', {'smoke'})]:
            results = {'plan': {'result': 'success'}} | {
                job: {'result': 'success' if job in selected else 'skipped'}
                for job in ('engine', 'desktop', 'docs', 'smoke')}
            check_results(mode, results)
            for job in results:
                for bad in ('failure', 'cancelled', 'missing'):
                    changed = deepcopy(results)
                    if bad == 'missing':
                        del changed[job]
                    else:
                        changed[job]['result'] = bad
                    with self.assertRaises(ValueError):
                        check_results(mode, changed)
            for job in selected:
                changed = deepcopy(results)
                changed[job]['result'] = 'skipped'
                with self.assertRaises(ValueError):
                    check_results(mode, changed)

    def setUp(self):
        self.changed = [DELIVERY, ACTIVE, 'docs/roadmap/execution/WP-032.md', 'engine/module.py']
        self.receipt = dict(kind='work_package', package='WP-032', status='complete',
            scope='Entire static integration', record='docs/roadmap/execution/WP-032.md',
            acceptance=[dict(id='integration', status='passed', evidence='actual candidate evidence')])
        self.active = dict(package='WP-032', status='complete',
            acceptance=[dict(id='integration', status='passed')])
        self.route = 'Solo-validated; agent review deferred'

    def test_full_parent_and_explicit_maintenance_are_accepted(self):
        validate_delivery(self.changed, self.receipt, self.active, self.route)
        self.receipt['kind'] = 'maintenance'
        self.active['status'] = 'in_progress'
        validate_delivery(self.changed, self.receipt, self.active, self.route)
        validate_delivery(['README.md'], {}, {}, '')

    def test_child_stale_receipt_and_missing_parent_are_rejected(self):
        child = self.receipt | {'package': 'WP-032-counterparts-care-health'}
        with self.assertRaises(ValueError):
            validate_delivery(self.changed, child, self.active, self.route)
        for omitted in (DELIVERY, ACTIVE, self.receipt['record']):
            with self.assertRaises(ValueError):
                validate_delivery([p for p in self.changed if p != omitted], self.receipt, self.active, self.route)

    def test_incomplete_parent_and_omitted_acceptance_are_rejected(self):
        for active in [self.active | {'status': 'in_progress'},
                       self.active | {'acceptance': [dict(id='integration', status='pending')]},
                       self.active | {'acceptance': self.active['acceptance'] + [dict(id='database', status='pending')]}]:
            with self.assertRaises(ValueError):
                validate_delivery(self.changed, self.receipt, active, self.route)
        for receipt in [self.receipt | {'status': 'blocked'}, self.receipt | {'acceptance': []},
                        self.receipt | {'acceptance': [dict(id='integration', status='passed')]}]:
            with self.assertRaises(ValueError):
                validate_delivery(self.changed, receipt, self.active, self.route)


if __name__ == '__main__':
    unittest.main()
