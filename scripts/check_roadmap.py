"""Validate the versioned roadmap manifest; never certify application behavior."""

import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def source_cases(text):
    section = text.split("### 5.1 Exact subcases and first-required gates", 1)[1]
    section = section.split("### 5.2", 1)[0]
    cases = {}
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 3 and re.fullmatch(r"E2E-\d{3}(?:\.[a-z])?", cells[0]):
            gate = re.match(r"G[1-7]\b", cells[2])
            if not gate or cells[0] in cases:
                raise ValueError(f"Invalid source case: {line}")
            cases[cells[0]] = {"scope": cells[1], "first_gate": gate[0],
                               "prerequisite": cells[2]}
    if not cases:
        raise ValueError("Source case table is empty")
    return cases


def validate_manifest(manifest, root=ROOT):
    if manifest.get("version") != 1:
        raise ValueError("Unsupported roadmap manifest version")
    expected = source_cases((root / "docs/roadmap/verification_matrix.md").read_text())
    if manifest.get("cases") != expected:
        raise ValueError("Case manifest drift: reconcile verification matrix §5.1")
    for gate in range(8):
        required = sorted(case for case, spec in expected.items()
                          if int(spec["first_gate"][1:]) <= gate)
        if manifest.get("gates", {}).get(f"G{gate}") != required:
            raise ValueError(f"G{gate} omits, duplicates or adds a mandatory case")
    if set(manifest.get("gates", {})) != {f"G{n}" for n in range(8)}:
        raise ValueError("Unexpected gate IDs")
    return expected


def validate_selection(manifest, selection):
    """Check cumulative full-gate selections, not outcomes or impact-based reuse."""
    if not isinstance(selection, dict):
        raise ValueError("Selection must be a JSON object")
    if selection.get("version") != 1:
        raise ValueError("Unsupported selection version")
    gate = selection.get("gate")
    if gate not in manifest["gates"] or gate == "G0":
        raise ValueError("Select an application gate G1–G7; G0 has no application tests")
    entries = selection.get("cases", [])
    if not isinstance(entries, list):
        raise ValueError("Selected cases must be a list")
    if not entries:
        raise ValueError("Zero selected application cases")
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise ValueError("Each selected case requires a string ID")
        case = entry["id"]
        if case in seen or case not in manifest["cases"]:
            raise ValueError(f"Duplicate or unknown case: {case}")
        seen.add(case)
        if entry.get("service") != "production":
            raise ValueError(f"{case}: a mock cannot replace required production services")
        tests = entry.get("tests")
        if not isinstance(tests, list) or not tests or any(
            not isinstance(test, str) or not test.strip() for test in tests
        ):
            raise ValueError(f"{case}: concrete test targets required")
    missing = set(manifest["gates"][gate]) - seen
    future = seen - set(manifest["gates"][gate])
    if missing or future:
        raise ValueError(f"Invalid {gate} selection; missing={sorted(missing)}, "
                         f"future={sorted(future)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path,
                        help="Validate a full cumulative G1–G7 test-selection JSON")
    args = parser.parse_args()
    try:
        manifest = json.loads((ROOT / "docs/roadmap/execution/gates.json").read_text())
        cases = validate_manifest(manifest)
        if args.selection:
            validate_selection(manifest, json.loads(args.selection.read_text()))
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(1, f"Roadmap check failed: {error}\n")
    print(f"Roadmap manifest valid: {len(cases)} cases, 8 gates. "
          "Application outcomes remain unrun; selection checks do not execute tests.")


if __name__ == "__main__":
    main()
