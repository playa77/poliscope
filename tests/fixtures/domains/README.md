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
