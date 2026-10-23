# Shared domain fixtures

`shared-v1.json` publishes `synthetic:domain-conformance@v1` with canonical
world/account/resource/asset/cohort/institution IDs, exact mechanism declarations,
finite claims and independently specified expected amounts. It is synthetic and
not a real-world source or empirical model. See the
[domain harness guide](../../../engine/poliscope_engine/domains/README.md) for
identity reuse, the independent arithmetic oracle, authoring API, counterpart
acceptance and transition limitations. Keep expected values independent of the
production evaluator. Changes to these fixture semantics require a new version.

`provisioning-economy-v1.json` publishes the independent real-adapter arrangement
`synthetic:provisioning-economy@v1`: actual economy care/training and access feed
actual provisioning production/freight/storage/use. It retains both settlements,
overlapping regional views, one canonical time budget and prior care fulfillment.
The expected accounts/claims and conservation derivation are literal data, never
regenerated from evaluator output. `provisioning_economy_fixture.py` supplies only
trusted construction/review bindings. Source models remain inactive; the common
DAG observations are partial and the all-domain static gate remains open.

`provisioning-education-v1.json` publishes `synthetic:provisioning-education@v1`.
Actual DOM-06 policy/student/staff/supply and facility prerequisites feed actual
production/freight/storage/use. The same cohort supplies student and staff time;
its one 14 h book also funds care, production and freight. Education consumes
2 kg from the canonical raw stock. The disjoint 3-slot facility pool retains a
prior posting/hold and a competing claim. Expected accounts/claims and conservation
are literal independently authored data; helper code constructs trusted bindings
only. No learning, scientific validity or all-domain education gate is claimed.

`provisioning-health-v1.json` is a synthetic real DOM-01/07 fixture: 14 shared
hours split across ordinary care, beneficiary care, clinical staff and finite
production/freight; 20 opening kg, supply use, physical losses and remote final
use reconcile independently. Prior postings/holds and overlapping views remain;
clinic slots use a disjoint pool. Health needs/exposure/state are descriptive
references. No delivered treatment, health change or quantitative need coverage
is implied. Independent shortage/access/policy/context cases use the actual
health and provisioning evaluators through the common conformance harness.

`provisioning-infrastructure-v1.json` is an independently authored synthetic
DOM-01/08 host fixture: one 5-slot depot, bridge and road book supplies explicit
prerequisites for the existing finite economy/provisioning chain. Its slots never
convert to kg or merge with material/time accounts. Tests vary bottlenecks and
queues using independent integer/Fraction oracles and preserve holds/prior
commitments, distinct reach failures and stale-context rejection. It supplies
bounded conformance only, with no empirical validation or parent acceptance.
