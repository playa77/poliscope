"""Check WP-001 traceability and planning contracts, never application outcomes."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roadmap import validate_manifest
from roadmap_sources import specification_clauses

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs/roadmap/execution"


def read(name, directory=DATA):
    return json.loads((directory / name).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_requirements(ledger, children, root=ROOT):
    require(ledger.get("version") == 1, "Unknown requirement ledger version")
    ids = set()
    expected = Counter()
    for doc, count in (("D", 16), ("T", 18)):
        spec = ledger["sources"][doc]
        text = (root / spec["path"]).read_text()
        require(hashlib.sha256(text.encode()).hexdigest() == spec["sha256"],
                f"{doc}: source changed; reconcile stable IDs explicitly")
        for clause in specification_clauses(text):
            expected[(doc, clause["section"], clause["line"], clause["text"])] += 1
        sections = {f"{doc}-{number:02}" for number in range(1, count + 1)}
        require(sections <= ledger["sections"].keys(), f"{doc}: missing section traceability")
    actual = Counter()
    for row in ledger["requirements"]:
        rid = row["id"]
        require(rid not in ids, f"Duplicate requirement ID: {rid}")
        ids.add(rid)
        require(bool(re.fullmatch(r"[DT]-\d+(?:-\d+)?-\d{3}", rid)), f"Invalid leaf ID: {rid}")
        actual[(row["source"], row["section"], row["line"], row["text"])] += 1
        require(row["delivering_child"] in children, f"{rid}: unknown delivering child")
        require(row["verification_package"] in children, f"{rid}: unknown verification child")
        require(row["first_gate"] in {f"G{n}" for n in range(8)}, f"{rid}: missing first gate")
        for field in ("verification_owner", "positive_oracle", "negative_oracle", "assertion"):
            require(isinstance(row.get(field), str) and bool(row[field].strip()),
                    f"{rid}: missing {field}")
        require(row["assertion"] == row["text"], f"{rid}: assertion differs from source clause")
        require(row["sha256"] == hashlib.sha256(row["text"].encode()).hexdigest(),
                f"{rid}: clause digest differs")
        require(row["kind"] in ("requirement", "context"), f"{rid}: unclassified clause")
        require(row["evidence_status"] == "unrun" and row["evidence"] == [],
                f"{rid}: WP-001 cannot certify application behavior")
    require(actual == expected, "Missing, duplicate or changed specification clauses")
    require(len(ledger["sections"]) == 34, "Exactly 34 top-level mappings required")
    for sid, section in ledger["sections"].items():
        selected = {row["verification_package"] for row in ledger["requirements"]
                    if row["source"] == section["source"] and
                    row["section"].split(".")[0] == section["section"]}
        require(set(section["verification_children"]) == selected and selected,
                f"{sid}: missing section verification ownership")


def validate_dependencies(plan):
    require(plan.get("version") == 1, "Unknown delivery-plan version")
    children = plan["children"]
    early = plan["early_dag"]
    require(len(set(early)) == len(early), "Duplicate early child")
    visited, visiting = set(), set()

    def visit(cid):
        require(cid in children, f"Unknown child dependency: {cid}; full parents cannot substitute")
        require(cid not in visiting, f"Dependency cycle at {cid}")
        if cid in visited:
            return
        visiting.add(cid)
        requires = children[cid]["requires"]
        require(isinstance(requires, list), f"{cid}: concrete prerequisites missing")
        for dependency in requires:
            visit(dependency)
        visiting.remove(cid)
        visited.add(cid)

    for child in early:
        visit(child)
    # These production children must never depend on their full integration consumer.
    forbidden = {
        "WP-009-store": "WP-018-apply", "WP-010-transport": "WP-018-apply",
        "WP-010-history-read": "WP-041-recovery",
        "WP-018-world": "WP-020-creation",
        "WP-036-boundary-store": "WP-034-reducer",
        "WP-046-envelope": "WP-045-dispatch",
        "WP-048-reservation": "WP-045-dispatch",
    }

    def ancestors(cid):
        return {item for dep in children[cid]["requires"] for item in ({dep} | ancestors(dep))}

    for provider, consumer in forbidden.items():
        require(consumer not in ancestors(provider), f"{provider}: hidden future consumer dependency")
    for cid, child in children.items():
        require(child["capabilities"] and child["scope"] and child["acceptance_ref"],
                f"{cid}: missing child planning contract")
        sha = child["merged_sha"]
        require(sha is None or bool(re.fullmatch(r"[0-9a-f]{40}", sha)), f"{cid}: invalid merged SHA")


def validate_package_inventory(inventory, root=ROOT):
    packages = inventory["packages"]
    expected = {f"WP-{n:03}" for n in range(1, 57)} | {f"DOM-{n:02}" for n in range(1, 13)}
    require(set(packages) == expected, "All 68 planning packages must be inventoried")
    for pid, row in packages.items():
        source = (root / row["source"]).read_text()
        match = re.search(rf"^### {pid} — (.+)$", source, re.M)
        require(match is not None and match[1] == row["title"], f"{pid}: missing source package")
        body = source[match.end():].split("\n### ", 1)[0].split("\n## ", 1)[0]
        require(row["capabilities"] and row["acceptance_dependencies"] and row["acceptance"],
                f"{pid}: missing capabilities/dependencies/acceptance")
        if pid.startswith("WP"):
            require(f"**Specialties:** {row['capabilities']}." in body, f"{pid}: capability drift")
            require(f"**Depends:** {row['acceptance_dependencies']}." in body, f"{pid}: dependency drift")
            require(body.split("**Acceptance/evidence:**", 1)[1].strip() == row["acceptance"],
                    f"{pid}: acceptance drift")
        else:
            static, dynamic = body.split("**Static acceptance:**", 1)[1].split("**Dynamic acceptance:**")
            require(row["acceptance"] == {"static": static.strip(), "dynamic": dynamic.strip()},
                    f"{pid}: static/dynamic acceptance drift")
    require(Counter(row["size"] for row in packages.values()) == {"M": 26, "L": 42},
            "Planning package size inventory differs")


def validate_baseline(directory=DATA, root=ROOT):
    gates = read("gates.json", directory)
    validate_manifest(gates, root)
    packages = read("packages.json", directory)
    validate_package_inventory(packages, root)
    plan = read("delivery-plan.json", directory)
    validate_dependencies(plan)
    children = plan["children"]
    require(all(row["parent"] in packages["packages"] for row in children.values()), "Unknown child parent")
    ledger = read("requirements.json", directory)
    validate_requirements(ledger, children, root)
    owners = read("case-owners.json", directory)["cases"]
    require(owners.keys() == gates["cases"].keys(), "Mandatory case verification ownership missing")
    for case, row in owners.items():
        require(row["verification_child"] in children and row["delivering_children"], f"{case}: missing owner")
        require(all(cid in children for cid in row["delivering_children"]), f"{case}: unknown provider")
        require(row["evidence_status"] == "unrun", f"{case}: application evidence must remain unrun")
    regressions = read("regressions.json", directory)["findings"]
    require(set(regressions) == {f"RT-{n:02}" for n in range(1, 15)}, "RT obligations missing")
    source = (root / "docs/roadmap/verification_matrix.md").read_text()
    for rid, row in regressions.items():
        require(f"| {rid} | {row['contract_decision']} | {row['source_owners']} |" in source,
                f"{rid}: source regression drift")
        require(row["regression_children"] and all(cid in children for cid in row["regression_children"]),
                f"{rid}: unknown regression owner")
        require(all(case in owners for case in row["cases"]), f"{rid}: unknown case")
        gate = "G0" if rid == "RT-14" else min(gates["cases"][case]["first_gate"] for case in row["cases"])
        require(row["first_gate"] == gate, f"{rid}: incorrect first gate")
    content = read("release-inventory.json", directory)
    require(set(content["domains"]) == {f"DOM-{n:02}" for n in range(1, 13)}, "Missing release domain")
    for pid, row in content["domains"].items():
        require(row["branches"] == packages["packages"][pid]["branches"], f"{pid}: branch coverage drift")
        require(row["initial_selected_mechanism"] and row["static_child"] in children and
                row["transition_child"] in children and row["review_child"] in children,
                f"{pid}: missing substantive behavior/review owner")
    benchmark = read("benchmarks.json", directory)
    require(benchmark["measurement"]["samples_min"] >= 30 and benchmark["reference"]["blocker"],
            "Unmeasurable benchmark/reference status")
    require(benchmark["budgets"]["ipc_max_bytes"] == 1048576, "IPC limit cannot be relaxed")
    return len(ledger["requirements"]), len(packages["packages"]), len(children)


if __name__ == "__main__":
    try:
        leaves, parents, children = validate_baseline()
    except (ValueError, KeyError, TypeError, OSError) as error:
        raise SystemExit(f"Baseline check failed: {error}") from None
    print(f"WP-001 baseline valid: {leaves} clauses, {parents} parents, {children} child scopes; "
          "30 case owners, RT-01–14. Application evidence unrun.")
