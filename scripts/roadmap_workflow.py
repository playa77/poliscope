"""Validate local allocation snapshots; these checks do not allocate real agents."""

from pathlib import PurePosixPath

PLAN_FIELDS = ("owner", "controller", "collaborators", "division", "scope", "route", "base_sha")


def overlaps(left, right):
    a, b = PurePosixPath(left), PurePosixPath(right)
    return a == b or a in b.parents or b in a.parents


def validate_transition(before, after):
    agents = after["available_agents"]
    if not 1 <= len(agents) <= 3 or len(set(agents)) != len(agents):
        raise ValueError("Capacity must contain one to three unique agents")
    old, new = before["packages"], after["packages"]
    active = []
    for pid, record in new.items():
        for field in PLAN_FIELDS:
            if field not in record:
                raise ValueError(f"{pid}: missing start-contract field {field}")
        if record["route"] not in ("SV", "agent-review"):
            raise ValueError(f"{pid}: unknown validation route")
        if not record["owner"] or not record["controller"] or not record["scope"]:
            raise ValueError(f"{pid}: owner, controller and reserved scope required")
        if record["status"] not in ("in progress", "blocked", "verified"):
            raise ValueError(f"{pid}: unknown execution status")
        previous = old.get(pid)
        if previous:
            if any(previous[field] != record[field] for field in PLAN_FIELDS):
                raise ValueError(f"{pid}: active/completed execution plan changed")
            if previous["status"] == "verified" and previous != record:
                raise ValueError(f"{pid}: completed evidence changed")
        else:
            if record["status"] != "in progress" or not record.get("prerequisites_verified"):
                raise ValueError(f"{pid}: new allocation needs ready prerequisites")
        if record["status"] == "verified":
            if not record.get("evidence"):
                raise ValueError(f"{pid}: completion evidence required")
            if record["route"] == "SV" and record.get("review_status") != "solo-validated; agent review deferred":
                raise ValueError(f"{pid}: SV deferral record required")
        if record["status"] == "blocked" and not record.get("recovery"):
            raise ValueError(f"{pid}: interrupted package needs recovery/checkpoint record")
        if record["status"] == "in progress":
            if record["owner"] not in agents:
                raise ValueError(f"{pid}: departing owner must complete or checkpoint first")
            active.append((pid, record))
    if set(old) - set(new):
        raise ValueError("Existing package/evidence disappeared")
    owners = [record["owner"] for _, record in active]
    if len(owners) != len(set(owners)):
        raise ValueError("One executing package per agent")
    # Blocked scopes stay reserved until explicit closure/recovery; no takeover.
    reserved = [(pid, row) for pid, row in new.items() if row["status"] != "verified"]
    for index, (pid, record) in enumerate(reserved):
        for other, other_record in reserved[index + 1:]:
            if any(overlaps(a, b) for a in record["scope"] for b in other_record["scope"]):
                raise ValueError(f"Overlapping write scopes: {pid}, {other}")
