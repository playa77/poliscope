"""WP-001 negative oracles and allocation dry runs, with synthetic agents only."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import check_baseline as baseline
from roadmap_workflow import PLAN_FIELDS, validate_transition
from roadmap_sources import specification_clauses


class SourceClauseTests(unittest.TestCase):
    def test_sentences_semicolons_and_list_items_are_separate_leaves(self):
        source = "## 1. Contract\n\nFirst obligation. Second obligation; third obligation.\n\n- Fourth obligation.\n"
        self.assertEqual([row["text"] for row in specification_clauses(source)],
                         ["First obligation.", "Second obligation", "third obligation.",
                          "Fourth obligation."])

    def test_table_labels_preserved_and_fenced_examples_excluded(self):
        source = "## 1. Contract\n\n| Field | Rule |\n|---|---|\n| Capacity | Finite supply |\n\n```json\n{}\n```\n\nNo implicit supply.\n"
        self.assertEqual([row["text"] for row in specification_clauses(source)],
                         ["Capacity: Finite supply", "No implicit supply."])

    def test_service_operations_have_individual_leaves(self):
        source = "### 10.2 Service surface\n\n| Group | Operations |\n|---|---|\n| History | undo/redo, compare, migrate-model branch |\n"
        self.assertEqual([row["text"] for row in specification_clauses(source)],
                         ["History: undo/redo", "History: compare", "History: migrate-model branch"])


class BaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = baseline.read("delivery-plan.json")
        cls.requirements = baseline.read("requirements.json")

    def test_full_baseline(self):
        leaves, parents, children = baseline.validate_baseline()
        self.assertGreater(leaves, 500)
        self.assertEqual(parents, 68)
        self.assertGreater(children, 68)

    def test_missing_leaf_fails(self):
        ledger = deepcopy(self.requirements)
        ledger["requirements"].pop()
        with self.assertRaisesRegex(ValueError, "Missing, duplicate"):
            baseline.validate_requirements(ledger, self.plan["children"])

    def test_duplicate_stable_id_fails(self):
        ledger = deepcopy(self.requirements)
        ledger["requirements"][1]["id"] = ledger["requirements"][0]["id"]
        with self.assertRaisesRegex(ValueError, "Duplicate requirement"):
            baseline.validate_requirements(ledger, self.plan["children"])

    def test_missing_negative_oracle_fails(self):
        ledger = deepcopy(self.requirements)
        ledger["requirements"][0]["negative_oracle"] = ""
        with self.assertRaisesRegex(ValueError, "missing negative_oracle"):
            baseline.validate_requirements(ledger, self.plan["children"])

    def test_unknown_delivering_child_fails(self):
        ledger = deepcopy(self.requirements)
        ledger["requirements"][0]["delivering_child"] = "WP-999-missing"
        with self.assertRaisesRegex(ValueError, "unknown delivering child"):
            baseline.validate_requirements(ledger, self.plan["children"])

    def test_no_application_pass_from_documentation(self):
        ledger = deepcopy(self.requirements)
        ledger["requirements"][0]["evidence_status"] = "passed"
        with self.assertRaisesRegex(ValueError, "cannot certify application"):
            baseline.validate_requirements(ledger, self.plan["children"])

    def test_source_digest_drift_fails(self):
        ledger = deepcopy(self.requirements)
        ledger["sources"]["D"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source changed"):
            baseline.validate_requirements(ledger, self.plan["children"])

    def test_missing_parent_package_fails(self):
        inventory = baseline.read("packages.json")
        del inventory["packages"]["DOM-11"]
        with self.assertRaisesRegex(ValueError, "All 68"):
            baseline.validate_package_inventory(inventory)

    def test_cycle_fails(self):
        plan = deepcopy(self.plan)
        plan["children"]["WP-005-wire"]["requires"].append("WP-010-transport")
        with self.assertRaisesRegex(ValueError, "cycle"):
            baseline.validate_dependencies(plan)

    def test_full_parent_cannot_replace_early_provider(self):
        plan = deepcopy(self.plan)
        plan["children"]["WP-036-boundary-store"]["requires"] = ["WP-036"]
        with self.assertRaisesRegex(ValueError, "full parents cannot substitute"):
            baseline.validate_dependencies(plan)

    def test_consumer_cannot_be_hidden_provider_dependency(self):
        plan = deepcopy(self.plan)
        # history-read -> recovery is acyclic but forbidden by the reader contract.
        plan["children"]["WP-041-recovery"]["requires"] = []
        plan["children"]["WP-010-history-read"]["requires"].append("WP-041-recovery")
        with self.assertRaisesRegex(ValueError, "hidden future consumer"):
            baseline.validate_dependencies(plan)

    def test_independent_first_gate_witnesses(self):
        rows = {row["text"]: row for row in self.requirements["requirements"]}
        witnesses = {
            "**Assistant and provider settings**: Ask questions and manage BYOK/model/routing": ("G6", "WP-049-assistant-ui"),
            "**Timeline and experiments**: Advance, schedule, replay, and inspect change": ("G4", "WP-037-timeline-ui"),
            "**Dependency matrix**: Explore relationships across domains, scopes, and decisions": ("G3", "WP-029-matrix-ui"),
            "History: migrate-model branch": ("G5", "WP-041-migration"),
            "Runtime: operation-status lookup": ("G2", "WP-018-apply"),
            "The reader validates schemas and returns bounded data-only evidence, and exposes no computation or mutation methods.": ("G2", "WP-010-history-read"),
            "Changing branches during streaming leaves the reply attached to its original state.": ("G6", "WP-047-reasoning"),
        }
        for text, expected in witnesses.items():
            with self.subTest(text=text):
                row = rows[text]
                self.assertEqual((row["first_gate"], row["delivering_child"]), expected)


def contract(owner, scope):
    return {"owner": owner, "controller": "synthetic-controller", "collaborators": [],
            "division": "sole implementer; SV inspection", "scope": [scope], "route": "SV",
            "base_sha": "4b9cac6fd994491db92518fccebf4e9142b42e03",
            "status": "in progress", "prerequisites_verified": True}


def complete(record):
    record.update(status="verified", evidence=["synthetic-dry-run-evidence"],
                  review_status="solo-validated; agent review deferred")


class AllocationTests(unittest.TestCase):
    def snapshot(self, count):
        agents = [f"fixture-agent-{n}" for n in range(count)]
        return {"available_agents": agents,
                "packages": {f"fixture-{n}": contract(agent, f"fixture/area-{n}")
                             for n, agent in enumerate(agents)}}

    def test_all_six_capacity_changes_preserve_unrelated_active_plan(self):
        for old_count, new_count in [(1, 2), (1, 3), (2, 1), (2, 3), (3, 1), (3, 2)]:
            with self.subTest(change=f"{old_count}->{new_count}"):
                before = self.snapshot(old_count)
                after = deepcopy(before)
                active = deepcopy(before["packages"]["fixture-0"])
                for n in range(new_count, old_count):
                    complete(after["packages"][f"fixture-{n}"])
                after["available_agents"] = [f"fixture-agent-{n}" for n in range(new_count)]
                for n in range(old_count, new_count):
                    after["packages"][f"joining-{n}"] = contract(f"fixture-agent-{n}", f"fixture/join-{n}")
                validate_transition(before, after)
                self.assertEqual(active, after["packages"]["fixture-0"])

    def test_same_count_replacement_after_completion(self):
        before = self.snapshot(2)
        after = deepcopy(before)
        complete(after["packages"]["fixture-1"])
        after["available_agents"][1] = "replacement"
        after["packages"]["next"] = contract("replacement", "fixture/area-1")
        validate_transition(before, after)
        self.assertEqual(before["packages"]["fixture-0"], after["packages"]["fixture-0"])

    def test_independent_completion_and_next_start_need_no_team_barrier(self):
        before = self.snapshot(2)
        after = deepcopy(before)
        complete(after["packages"]["fixture-1"])
        after["packages"]["next"] = contract("fixture-agent-1", "fixture/area-1")
        validate_transition(before, after)
        self.assertEqual(before["packages"]["fixture-0"], after["packages"]["fixture-0"])

    def test_each_frozen_plan_field_cannot_change(self):
        before = self.snapshot(2)
        for field in PLAN_FIELDS:
            with self.subTest(field=field):
                after = deepcopy(before)
                after["packages"]["fixture-0"][field] = "changed"
                with self.assertRaisesRegex(ValueError, "plan changed|unknown validation route"):
                    validate_transition(before, after)

    def test_departing_agent_cannot_abandon_active_package(self):
        before = self.snapshot(2)
        after = deepcopy(before)
        after["available_agents"].pop()
        with self.assertRaisesRegex(ValueError, "departing owner"):
            validate_transition(before, after)

    def test_interruption_retains_owner_and_checkpoint(self):
        before = self.snapshot(2)
        after = deepcopy(before)
        after["available_agents"].pop()
        after["packages"]["fixture-1"].update(status="blocked", recovery="Retain assignment; resume exact checkpoint")
        validate_transition(before, after)
        takeover = deepcopy(after)
        takeover["packages"]["fixture-1"]["owner"] = "fixture-agent-0"
        with self.assertRaisesRegex(ValueError, "plan changed"):
            validate_transition(after, takeover)

    def test_missing_recovery_record_fails(self):
        before = self.snapshot(1)
        after = deepcopy(before)
        after["packages"]["fixture-0"]["status"] = "blocked"
        with self.assertRaisesRegex(ValueError, "recovery/checkpoint"):
            validate_transition(before, after)

    def test_overlapping_scopes_fail(self):
        before = self.snapshot(1)
        after = deepcopy(before)
        after["available_agents"].append("new")
        after["packages"]["new"] = contract("new", "fixture/area-0/nested")
        with self.assertRaisesRegex(ValueError, "Overlapping write scopes"):
            validate_transition(before, after)

    def test_blocked_scope_cannot_be_taken_over(self):
        before = self.snapshot(2)
        before["packages"]["fixture-1"].update(status="blocked", recovery="Keep checkpoint")
        after = deepcopy(before)
        after["packages"]["new"] = contract("fixture-agent-1", "fixture/area-1")
        with self.assertRaisesRegex(ValueError, "Overlapping write scopes"):
            validate_transition(before, after)

    def test_completed_evidence_cannot_disappear(self):
        before = self.snapshot(1)
        complete(before["packages"]["fixture-0"])
        after = deepcopy(before)
        after["packages"] = {}
        with self.assertRaisesRegex(ValueError, "disappeared"):
            validate_transition(before, after)

    def test_new_package_must_be_ready(self):
        before = self.snapshot(1)
        after = deepcopy(before)
        complete(after["packages"]["fixture-0"])
        after["packages"]["new"] = contract("fixture-agent-0", "fixture/area-0")
        after["packages"]["new"]["prerequisites_verified"] = False
        with self.assertRaisesRegex(ValueError, "ready prerequisites"):
            validate_transition(before, after)

    def test_sv_completion_retains_deferral_record(self):
        before = self.snapshot(1)
        after = deepcopy(before)
        complete(after["packages"]["fixture-0"])
        del after["packages"]["fixture-0"]["review_status"]
        with self.assertRaisesRegex(ValueError, "SV deferral"):
            validate_transition(before, after)


if __name__ == "__main__":
    unittest.main()
