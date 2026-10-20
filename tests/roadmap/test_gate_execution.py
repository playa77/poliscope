"""Exact G2 mapping and candidate report selection fail closed."""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from check_gate_evidence import validate
from check_roadmap import validate_selection

ROOT = Path(__file__).resolve().parents[2]

class GateExecutionTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / 'docs/roadmap/execution/gates.json').read_text())
        self.selection = json.loads((ROOT / 'docs/roadmap/execution/WP-024-selection.json').read_text())
        self.record = {'results': {'cases': [{'name': name} for case in self.selection['cases'] for name in case['tests']]}}

    def test_exact_g2_has_one_or_more_executed_targets_for_every_subcase(self):
        validate(self.selection, [self.record], self.manifest)
        self.assertEqual({case['id'] for case in self.selection['cases']}, set(self.manifest['gates']['G2']))

    def test_every_omitted_subcase_and_future_subcase_is_rejected(self):
        for index in range(len(self.selection['cases'])):
            missing = dict(self.selection, cases=self.selection['cases'][:index] + self.selection['cases'][index+1:])
            with self.subTest(index=index), self.assertRaises(ValueError):
                validate_selection(self.manifest, missing)
        for case in set(self.manifest['cases']) - set(self.manifest['gates']['G2']):
            future = dict(self.selection, cases=self.selection['cases'] + [dict(id=case, service='production', tests=[case + ' future'])])
            with self.subTest(case=case), self.assertRaises(ValueError):
                validate_selection(self.manifest, future)

    def test_missing_duplicate_and_wrong_case_named_execution_rejected(self):
        for cases in ([], self.record['results']['cases'] * 2):
            with self.assertRaises(ValueError):
                validate(self.selection, [{'results': {'cases': cases}}], self.manifest)
        bad = json.loads(json.dumps(self.selection))
        bad['cases'][0]['tests'] = ['unrelated E2E-001 text']
        with self.assertRaises(ValueError):
            validate(bad, [self.record], self.manifest)

if __name__ == '__main__':
    unittest.main()
