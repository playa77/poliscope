# Reading and maintaining the requirement ledger

`requirements.json` v1 contains 1,053 individually identified source clauses and
all 34 D/T top-level mappings. `packages.json` preserves capabilities, acceptance
dependencies and acceptance criteria for all 68 planning packages. These are
traceability records, not passing application checks.

Each clause has a persistent ID, document/section/line, exact statement and digest,
delivering child, first gate, verification package/capabilities, positive fixture,
negative oracle, assertion and evidence state. The concrete assertion is the
individual source statement, narrowed against the named fixture/oracle; fixture
families are shared where the same integrated scenario proves several obligations.
Production tests must later bind their exact IDs and outcomes to these rows;
free-form oracle text alone cannot pass a requirement.

The source reader conservatively inventories all prose, list items and table
cells below numbered headings. Sentences/semicolon clauses and T §10.2 service
operations are separate leaves; comma/conjunction field lists remain attached to
their defining contract. Context introductions/history are labeled separately.
Fenced JSON/equation/diagram examples and Markdown header syntax are excluded,
not silently claimed as executable requirements. Their surrounding normative
quantity/conservation/IPC obligations are tracked. Each top-level source section
retains the original verification matrix's behavior, planning owners and evidence.

Stable IDs are assigned once in this candidate. On a source amendment, retain the
existing requirement ID where its identity persists, record amendment/supersession
or retirement explicitly, and reconcile source digests, assertions and affected
tests. Do not regenerate IDs or convert prior statuses into passes. The checker
fails source edits or missing/duplicate clauses until that review is performed.
No generation/synchronization command overwrites the checked-in ledger.

`delivery-plan.json` defines child scopes and the early development DAG, rather
than assigning future agent identities. Null prerequisites prohibit allocation;
parents retain all acceptance obligations. Early production children follow
delivery §4.1 overrides. Every actual start still records a verified upstream SHA,
interfaces, bounded acceptance, scope reservation, owner/controller and fixed
review route. Every actual merge SHA is initially null because no implementation
PR has been merged. Planned schemas and mocks are not production providers.

`case-owners.json` has complete ownership for every exact gate case, while
`regressions.json` preserves RT-01–14 contracts, first gates and concrete regression
children. The minimal trusted reader is required at G2; broader archive recovery
is G5. Engine target observations are G2, notes UI is G3, streaming navigation is
G6, and native installed-product acceptance is G7. T §10.2 history migration is
separate from earlier undo/fork/compare. These distinctions prevent future-service
dependencies from silently moving into the offline milestone.

Run `python3 scripts/check_baseline.py` for the full mechanical baseline check.
Run `python3 -m unittest discover -s tests/roadmap -v` for independent gate
witnesses, missing/changed clause/dependency failures and allocation dry runs.
`python3 scripts/check_roadmap.py` remains the narrow exact-gate manifest checker.
All use Python 3.12 stdlib before WP-002 introduces frozen development dependencies.
