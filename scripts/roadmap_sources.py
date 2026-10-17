"""Read specification clauses for coverage checks, without assigning new IDs.

The checked-in ledger owns stable IDs. Reconciliation after source edits is an
explicit review, never automatic regeneration of requirement identity or status.
"""

import re


def specification_clauses(text):
    """Conservatively include every prose/list/table clause below numbered headings.

    Fenced examples and table/header syntax are not normative clauses. Table cells
    retain their row label; sentences and semicolon clauses are separate leaves.
    Related comma/conjunction lists remain in their defining clause.
    """
    section = None
    fenced = False
    pending = []
    start = None
    result = []

    def emit():
        if not pending:
            return
        content = " ".join(pending)
        if section == "10.2" and ": " in content:
            label, operations = content.split(": ", 1)
            # Service inventory mixes early operations with later migration,
            # timeline and assistant operations. Give each its own first gate.
            if label in {"Runtime", "Catalog/model", "World", "Design", "History",
                         "Timeline", "Exploration", "Goals/notes", "Content proposals",
                         "Portability", "Assistant context"}:
                for operation in operations.split(", "):
                    result.append({"section": section, "line": start,
                                   "text": f"{label}: {operation}"})
                pending.clear()
                return
        for part in re.split(r"(?<=[.!?])\s+(?=[A-Z“`])|;\s+", content):
            part = part.strip()
            if part:
                result.append({"section": section, "line": start, "text": part})
        pending.clear()

    for number, line in enumerate(text.splitlines(), 1):
        heading = re.match(r"^#{2,3} (\d+(?:\.\d+)?)\.?\s+", line)
        if heading:
            emit()
            section = heading[1]
            continue
        if line.startswith("```"):
            emit()
            fenced = not fenced
            continue
        if fenced or section is None:
            continue
        if not line.strip():
            emit()
            continue
        if line.startswith("|"):
            emit()
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if all(re.fullmatch(r"[-: ]+", cell) for cell in cells):
                continue
            # Header is immediately followed by the Markdown separator row.
            lines = text.splitlines()
            if number < len(lines) and re.match(r"^\|\s*:?-", lines[number]):
                continue
            for cell in cells[1:]:
                pending.append(f"{cells[0]}: {cell}")
                start = number
                emit()
            continue
        if re.match(r"^(?:- |\d+\. )", line):
            emit()
        if not pending:
            start = number
        pending.append(re.sub(r"^(?:- |\d+\. )", "", line).strip())
    emit()
    return result
