"""Independent gate witnesses from verification §5.1 (stdlib bootstrap only)."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("check_roadmap", ROOT / "scripts/check_roadmap.py")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / "docs/roadmap/execution/gates.json").read_text())

    def selection(self, ids, gate="G1"):
        return {"version": 1, "gate": gate, "cases": [
            {"id": case, "service": "production", "tests": [f"tests/{case}"]}
            for case in ids]}

    def test_current_source_matches(self):
        checker.validate_manifest(self.manifest)

    def test_g1_needs_only_renderer_security_application_case(self):
        checker.validate_selection(self.manifest, self.selection(["E2E-012.a"]))

    def test_g2_exact_independent_witness(self):
        ids = ["E2E-012.a", "E2E-001", "E2E-002.a", "E2E-002.b", "E2E-003.a",
               "E2E-004.a", "E2E-005", "E2E-006.a", "E2E-010.a", "E2E-012.b",
               "E2E-015.a", "E2E-016.a"]
        checker.validate_selection(self.manifest, self.selection(ids, "G2"))

    def test_missing_required_case(self):
        with self.assertRaisesRegex(ValueError, "missing=.*E2E-012.a"):
            checker.validate_selection(self.manifest, self.selection(["E2E-001"], "G2"))

    def test_zero_tests(self):
        with self.assertRaisesRegex(ValueError, "Zero selected"):
            checker.validate_selection(self.manifest, self.selection([]))

    def test_future_stream_case_is_not_g2_requirement(self):
        selection = self.selection(self.manifest["gates"]["G2"] + ["E2E-006.b"], "G2")
        with self.assertRaisesRegex(ValueError, "future=.*E2E-006.b"):
            checker.validate_selection(self.manifest, selection)

    def test_mock_cannot_certify_real_service(self):
        selection = self.selection(["E2E-012.a"])
        selection["cases"][0]["service"] = "mock"
        with self.assertRaisesRegex(ValueError, "mock cannot replace"):
            checker.validate_selection(self.manifest, selection)

    def test_missing_test_target(self):
        selection = self.selection(["E2E-012.a"])
        selection["cases"][0]["tests"] = []
        with self.assertRaisesRegex(ValueError, "concrete test targets"):
            checker.validate_selection(self.manifest, selection)

    def test_duplicate_case(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            checker.validate_selection(self.manifest, self.selection(["E2E-012.a"] * 2))

    def test_manifest_cannot_silently_drop_requirement(self):
        broken = deepcopy(self.manifest)
        broken["gates"]["G2"].remove("E2E-005")
        with self.assertRaisesRegex(ValueError, "G2 omits"):
            checker.validate_manifest(broken)

    def test_source_scope_drift(self):
        self.manifest["cases"]["E2E-005"]["scope"] = "Only happy path"
        with self.assertRaisesRegex(ValueError, "Case manifest drift"):
            checker.validate_manifest(self.manifest)

    def test_g0_cannot_claim_application_tests(self):
        with self.assertRaisesRegex(ValueError, "G0 has no application"):
            checker.validate_selection(self.manifest, self.selection(["E2E-012.a"], "G0"))

    def test_malformed_selection(self):
        for selection in [[], {"version": 1, "gate": "G1", "cases": {}},
                          {"version": 1, "gate": "G1", "cases": [None]},
                          {"version": 1, "gate": "G1", "cases": [{"id": []}]}]:
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                checker.validate_selection(self.manifest, selection)


if __name__ == "__main__":
    unittest.main()
