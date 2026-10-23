# Domain conformance v1

`DomainModule` in `contracts/domains.py` is the shared authoring contract. JSON
Schema and TypeScript are generated in `contracts/domain.*`; neither content nor
a schema can grant trusted execution authority. All twelve domains retain the
same world, mechanisms, policy resolver, accounts, evaluator and shared store.
Domain-specific databases, engines and import paths are forbidden fields.

`DomainRegistry` stores detached immutable snapshots. `validate` checks complete
port catalogs against exact versioned mechanism declarations, canonical entity
kinds and state authority, exhaustive selected branch coverage, scope/procedure
availability, source references, evidence claims and ready counterpart contracts.
It does not manufacture mechanism reviews. Actual activation still uses
`MechanismRegistry`'s model/evidence/fixture/ownership/context checks. A registered
module does not authorize a public IPC operation or a database write.

`templates()` returns the retained `catalog-v1.json`: all twelve domain templates,
38 pinned source branches and 44 distinct counterpart pairs from the domain
register (including knowledge/culture's all-domain path). Each branch has status,
evidence status, applicable scopes, static/transition availability, limits and a
next task. All initial branches are unresolved and have no executable mechanism
or state authority. These templates contain no inferred resources or social
coefficients. Do not report numerical completeness from catalog coverage.

The lower numbered DOM package owns each pair's fixture integration; the other
package supplies and validates its counterpart. This assigns a domain/package
responsibility, not an agent or scientific reviewer. All retained pairs start
`pending_counterpart`. Before changing a pair to `ready_for_conformance`, declare
real input/output interface IDs, exact matching types, common authoritative
references and host-known versioned fixture IDs. Both participating modules must
be registered. If responsibility is undecided, use `owner_status=unresolved` and
`integration_owner=null`; it cannot be marked ready. Passing the common synthetic
fixture does not satisfy real counterpart acceptance or empirical review.

## Shared fixture and harness

`tests/fixtures/domains/shared-v1.json` is the stable data-only synthetic fixture
`synthetic:domain-conformance@v1`. Its inputs/definitions are derived from the
merged WP-019 finite headless example; its expected quantities are the retained
independent integer arithmetic oracle. `tests/engine/domain_fixture.py` supplies
trusted callbacks and synthetic reviews without importing other test builders.
No JSON selects a Python module or implementation to load.

Canonical references are `stock`, `product`, `residual`, `labor` (accounts),
`water` (resource), `shared:asset` (asset), `shared:cohort` (fixed-input cohort),
`east-authority` and `region-authority` (institutions). `east` and `west` are
settlements; `watershed` and `region` provide overlapping region views. Asset and
cohort anchors have no invented capacity or population quantity. They expose
unavailable behavior until a reviewed model supplies it. Reuse these IDs across
counterparts; do not rename each participant's copy of a stock or people budget.

The independent oracle is 100 kg stock, two 80 kg requests, one 40 kg reservation,
12 hours labor and an explicit priority procedure. Actual inputs are 60/40 kg,
not 80/80 kg. The reservation is deducted once. At 0.1 labor per kg, 2 hours
remain. Actual inputs yield 70 kg product, 20 kg residual and 10 kg loss. Claims
retain 20/40 kg unmet. Unknown is not zero and no default priority is invented.
The fixture's synthetic selected priority is not a product recommendation.

`conformance.run_case(ConformanceCase(...), catalog=..., mechanisms=...,
branch_ids=...)` invokes the actual pure evaluator twice and checks unchanged
world/relationship/input/declaration snapshots, reproducibility, literal outcome,
selected typed observations/provenance, complete accounts/claims and required
trace dependencies. Expected results must be authored independently; never
refresh a golden output from the implementation under test. The returned result
is detached. Provide all branches of the selected module allocation, not a subset
chosen to hide missing coverage. Per-case accepted branches need not cover all
twelve domains; the retained template test checks the complete pinned inventory.

Run `uv run --frozen pytest tests/engine/test_domain_conformance.py`. The common
suite parameterizes the real finite path across all twelve domain names and tests
two local scopes, overlapping authority and repeated canonical resource views,
registration/trust failures, malformed units/inputs, overspending/double claims,
foreign/double state writers, type/reference mismatches, missing/false coverage,
provenance, actual-output dependency and impure callback mutations.

`stage_transition` is a proposal-only fixture hook over the real
`MechanismRegistry.stage_changes` guard. It requires an explicitly declared hook,
entity/scope/properties, reviewed transition support and world-owned state, then
returns a private candidate. Foreign writes fail and original state is unchanged.
Unavailable hooks fail explicitly. WP-034 must extend this with scheduling,
checkpoint/replay and durable publication evidence. The harness is trusted-host
validation, not a sandbox: snapshot/repeat checks cannot prove arbitrary Python
free of filesystem/network side effects. No imported code is executed here.

## Authored DOM-01/02 counterpart

`templates()` retains the initial unactivated inventory above.
`conformance_catalog()` layers the fixed authored
`provisioning/counterpart-catalog-v1.json` declarations over it. Only
`pair:DOM-01:DOM-02` is `ready_for_conformance`; 43 pairs stay pending. This
names a host-only finite fixture, not parent or scientific acceptance. The two
authored modules classify every branch as partial hypothetical support with
explicit limits; no immutable source model is activated.

The real adapter and host binding are documented in
[provisioning](provisioning/README.md). Matching label ports carry opaque digests
of the complete bound context and staged book. They are not quantity ports,
serialized stock payloads or public execution capabilities. Both callbacks run
the actual domain evaluators; no generic pass-through arithmetic substitutes for
them. `run_bound_case` rebuilds a fresh registry against the actual case world,
checks catalog/model/runtime and context, then uses the common `run_case` harness.
Trusted reviews remain an explicit host requirement. Passing synthetic SV
conformance does not supply independent scientific review.

The common evaluator retains `partial` observations and an `incomplete` outcome
for these bounded declarations. The separate paired report exposes full staged
balances, actual/unmet claims, loss, holds and posting provenance. No generic
engine account publication, database write or new IPC is implied.
