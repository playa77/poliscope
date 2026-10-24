"""The audit must expose gaps and reject missing or substituted declarations."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('static_readiness', ROOT / 'scripts/audit_static_readiness.py')
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


class StaticReadinessTests(unittest.TestCase):
    def test_retained_audit_and_unaccepted_gate(self):
        report = audit_module.audit()
        self.assertEqual(report, json.loads(audit_module.SNAPSHOT.read_text()))
        self.assertEqual(report['gate_acceptance'], 'not_assessed')
        self.assertEqual(len(report['domains']), 12)
        self.assertEqual(len(report['counterparts']), 44)
        self.assertEqual([p['id'] for p in report['counterparts']
                          if p['status'] == 'ready_for_conformance'], ['pair:DOM-01:DOM-02', 'pair:DOM-01:DOM-05', 'pair:DOM-01:DOM-06', 'pair:DOM-01:DOM-07', 'pair:DOM-01:DOM-08', 'pair:DOM-01:DOM-10', 'pair:DOM-01:DOM-12', 'pair:DOM-02:DOM-03', 'pair:DOM-02:DOM-04', 'pair:DOM-02:DOM-05', 'pair:DOM-02:DOM-06', 'pair:DOM-02:DOM-07', 'pair:DOM-02:DOM-08', 'pair:DOM-03:DOM-04', 'pair:DOM-03:DOM-06', 'pair:DOM-03:DOM-09', 'pair:DOM-03:DOM-11', 'pair:DOM-03:DOM-12'])
        self.assertEqual(sum(p['status'] == 'pending_counterpart'
                             for p in report['counterparts']), 26)

    def mutate(self, path, change):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('content', 'docs/roadmap', 'engine/poliscope_engine/domains'):
                shutil.copytree(ROOT / name, root / name)
            target = root / path
            data = json.loads(target.read_text())
            change(data)
            target.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                audit_module.audit(root)

    def test_missing_module(self):
        self.mutate('engine/poliscope_engine/domains/catalog-v1.json', lambda d: d['modules'].pop())

    def test_missing_pair(self):
        self.mutate('engine/poliscope_engine/domains/catalog-v1.json', lambda d: d['pairs'].pop())

    def test_substituted_pair_domains(self):
        self.mutate('engine/poliscope_engine/domains/catalog-v1.json',
                    lambda d: d['pairs'][0].update(domains=['provisioning', 'health']))

    def test_missing_branch(self):
        self.mutate('engine/poliscope_engine/domains/catalog-v1.json',
                    lambda d: d['modules'][0]['coverage'].pop())

    def test_false_ready_pair(self):
        self.mutate('engine/poliscope_engine/domains/catalog-v1.json',
                    lambda d: d['pairs'][0].update(status='ready_for_conformance'))

    def test_source_drift(self):
        self.mutate('content/security-risk/coverage-v1.json',
                    lambda d: d.update(source_revision='0' * 40))

    def test_missing_source_row(self):
        self.mutate('content/meaning-identity/coverage-v1.json', lambda d: d['entries'].pop())


if __name__ == '__main__':
    unittest.main()
