# WP-001-baseline — Package record and evidence

- Parent: WP-001; sources: WP-001 scope, delivery §§2–4/6–8 and verification §5.1.
- Owner: Codex `/root`; human controller: requesting repository user, chat contact.
- Start: 2026-10-17; base main: `4b9cac6fd994491db92518fccebf4e9142b42e03`.
- Division of work: sole agent implements, tests and performs separate SV inspection.
- Write reservation: `.github/ISSUE_TEMPLATE/work-package.md`, `.gitignore`,
  `scripts/check_roadmap.py`, `tests/roadmap/`, `docs/roadmap/execution/` and
  status/navigation notes in README and the three planning registers.
- Dependencies: none. Gate metadata v1; no application/model/wire contract changes.
- Exclusions: application scaffold, full leaf ledger, empirical/model approval,
  package allocation simulator and application acceptance. These remain parent or
  later-package work, not hidden completed deliverables.
- Validation route fixed at start: SV. No collaborator or independent review.

## Acceptance and results

Candidate: local working-tree changes on branch `work` against the base above;
no commit/PR/merge has been created. Python 3.12.14, Linux cloud environment.

| Criterion / independent oracle | Command or inspection | Result |
|---|---|---|
| Exact case scopes/first gates/prerequisites from verification §5.1 | `python3 scripts/check_roadmap.py` | Passed: 30 cases, 8 gates |
| G1 requires E2E-012.a alone; G2 requires the 11 new named cases plus G1, never provider streaming | Explicit test witnesses transcribed independently from gate table | Passed |
| Missing/zero/duplicate/future/mock/targetless/malformed selections and source drift fail | `python3 -m unittest discover -s tests/roadmap -v` | 13 passed; 0 failed, skipped or expected failures |
| Whitespace integrity | `git diff --check` | Passed |
| Separate SV inspection | Compared manifest against source table; checked cumulative gates, failure exits, records, and scope claims | Completed; application outcomes remain unrun |

Bootstrap tests use stdlib unittest because WP-002 has not established dependency
manifests; this is not a substitute for WP-003's pytest/Vitest/Electron harnesses.
Failure cases matter here because silently omitting a mandatory case would
otherwise permit false milestone claims (RT-14). These tests certify the metadata
checker only; RT-14's eventual runner integration remains unrun.

Outcome at the first child handoff: **solo-validated; agent review deferred**.
The parent was incomplete at that handoff. It has now been completed with the
remaining children; see [current parent acceptance](WP-001.md). No application,
native, provider or scientific validation has run. Independent review is deferred.

The historical next action (requirements → decisions → parent validation) has
been executed. The next allocation is WP-002-layout under the completed parent
record. The initial child checks remain evidence for the narrow original scope;
current parent checks cover the full change set.
