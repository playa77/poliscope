"""Product audit rejects stale, tampered and incomplete evidence."""
import hashlib
import gzip
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from audit_product_gate import audit, validate_evidence


class ProductGateTests(unittest.TestCase):
    def test_baseline_leaves_and_cumulative_scenarios_stay_unrun(self):
        report = audit()
        self.assertEqual(len(report['requirements']), 1053)
        self.assertEqual(len(report['cases']), 30)
        self.assertEqual(len(report['regressions']), 14)
        self.assertEqual(len(report['model_inventory']), 12)
        self.assertEqual(report['requirement_counts']['unrun'], 1053)
        self.assertEqual(report['acceptance'], 'not_established')
        self.assertTrue(all(r['owner'] and r['verification_package'] for r in report['requirements']))

    def test_candidate_and_unknown_ids_are_rejected(self):
        for evidence in (
            {'requirements': {'D-1-001': {}}},
            {'candidate': 'abc', 'requirements': {'invented': {}}},
            {'candidate': 'abc', 'cases': {'E2E-999': {}}},
            {'candidate': 'abc', 'regressions': {'RT-99': {}}},
        ):
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                audit(evidence=evidence)

    def test_executed_evidence_requires_matching_artifact_candidate_and_inspection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'report.xml'
            path.write_text('<testsuite><testcase name="production workflow"/></testsuite>')
            entry = dict(outcome='passed', owner='QA', reason='Production path inspected',
                candidate='frozen', production_inspection='Actual SQLite mutation/restart inspected',
                tests=['production workflow'], artifacts=[dict(path='report.xml', format='junit', sha256=hashlib.sha256(path.read_bytes()).hexdigest())])
            validate_evidence(entry, 'frozen', root)
            compressed = root / 'report.xml.gz'
            compressed.write_bytes(gzip.compress(path.read_bytes(), mtime=0))
            compressed_entry = dict(entry, artifacts=[dict(path=compressed.name, format='junit-gzip', sha256=hashlib.sha256(compressed.read_bytes()).hexdigest())])
            validate_evidence(compressed_entry, 'frozen', root)
            for changes in ({'candidate': 'old'}, {'artifacts': []}, {'production_inspection': ''},
                            {'outcome': 'success'}, {'owner': ''}, {'tests': []},
                            {'tests': ['absent']}, {'tests': ['production workflow'] * 2},
                            {'artifacts': [dict(path='../absent', sha256='a')]}):
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    validate_evidence(dict(entry, **changes), 'frozen', root)
            path.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'digest'):
                validate_evidence(entry, 'frozen', root)

    def test_one_disposition_cannot_certify_other_leaves_or_product(self):
        evidence = dict(candidate='frozen', requirements={'D-1-001': dict(
            outcome='unrun', owner='QA', reason='No workflow evidence available')})
        report = audit(evidence=evidence)
        self.assertEqual(report['requirement_counts']['unrun'], 1053)
        self.assertEqual(report['scenario_counts']['unrun'], 30)
        self.assertEqual(report['acceptance'], 'not_established')

    def test_regression_pass_needs_its_linked_scenarios(self):
        from evidence import candidate
        root = Path(__file__).resolve().parents[2]
        scratch = root / 'artifacts'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            path = Path(directory) / 'report.xml'
            path.write_text('<testsuite><testcase name="workflow"/></testsuite>')
            identity = candidate(root)
            entry = dict(outcome='passed', owner='QA', reason='Inspection', candidate=identity,
                production_inspection='Reviewed', tests=['workflow'],
                artifacts=[dict(path=path.relative_to(root).as_posix(), format='junit',
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest())])
            with self.assertRaisesRegex(ValueError, 'linked scenario'):
                audit(evidence=dict(candidate=identity, regressions={'RT-01': entry}))
            with self.assertRaisesRegex(ValueError, 'Stale candidate'):
                audit(evidence=dict(candidate='old', regressions={'RT-01': entry}))

    def test_failed_skipped_duplicate_and_empty_reports_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for body in ('', '<testcase name="target"><failure/></testcase>',
                         '<testcase name="target"><skipped/></testcase>',
                         '<testcase name="target"/>' * 2):
                path = root / 'report.xml'
                path.write_text('<testsuite>' + body + '</testsuite>')
                entry = dict(outcome='passed', owner='QA', reason='Inspection',
                    candidate='frozen', production_inspection='Actual workflow', tests=['target'],
                    artifacts=[dict(path='report.xml', format='junit',
                        sha256=hashlib.sha256(path.read_bytes()).hexdigest())])
                with self.subTest(body=body), self.assertRaises(ValueError):
                    validate_evidence(entry, 'frozen', root)


if __name__ == '__main__':
    unittest.main()
