# Provisioning: static freight adapter

`logistics.transport(LogisticsRequest, units)` stages a detached, pure candidate
through the shared `allocate` and `AccountBook` services. It has no private stock,
engine, database or numerical context. Canonical account IDs remain the only
resource/capacity authorities. The host supplies resource bindings and routes;
this adapter does not infer geography, connectivity, scientific evidence or
execution permission from imported content.

Each active batch claim is a freight claim against a source stock. Historical
claims can be explicitly closed as described below. Declare
exactly one route per claim, binding its destination, transport-capacity account,
positive capacity-per-unit coefficient, access decision/limit and any crew or
entitlement requirements. An explicit selected period binds every capacity
requirement. Shared capacity accounts compete globally; do not copy a budget for
each route. Each endpoint must use the same stock unit, quantum and resource ID,
and different local scopes. The source and destination sets must be disjoint:
transshipment/cycles require a separately declared solver, not list ordering.

Routes use explicit priority or all-or-nothing procedures and complete claim
orders. Unknown access/funding/procedure leaves the allocation unresolved. No
route is an invalid request, never a free transfer. Zero throughput or denied
access produces zero delivery with unmet claims and preserves distant stock.
Only new actual fulfillment becomes paired source export/destination import
postings. Existing imports and previous actuals are never mirrored again.
Movement records retain exact posting IDs, resource identity and provenance.
Capacity/crew debits stay in the same shared book. Destination overflow or a
failed invariant rejects the whole detached candidate; nothing is published.

The returned `allocation` is the source-allocation calculation evidence; the
returned `batch` and `accounts` include final paired imports/exports. These are
separate explicit stages, not competing authoritative books. Calling with the
returned batch allocates only remaining unmet claims using remaining capacity;
a complete retry is not a durable operation-ID replay. The caller must use the
existing revision operation ledger before publication. No IPC endpoint or model
activation path is added by this host-only adapter.

Local use remains a separate declared access procedure through the shared
allocator: delivered stock does not imply entitlement. Prior claim/posting
history remains in the batch, and a later phase must explicitly close earlier
allocation choices. Production/transformation uses shared finite actual-input semantics; the
static chain below composes production/delivery/use without dynamic scheduling. Losses, unit conversions, intermediate storage schedules, routing
optimization, replenishment and circular returns are unavailable in freight v1.
The authored [model card](freight-v1.json)
is hypothetical arithmetic evidence, not source-corpus or empirical approval.

Run `uv run --frozen pytest tests/engine/test_logistics.py`. Its independent
integer enumeration and literal fractional/reservation fixtures cover two
recipient groups sharing source stock, truck and crew budgets; distribution under
explicit alternatives; unreachable surplus; access denial; time-period isolation;
prior fulfillment; overflow; and malformed interfaces. Real DOM-02/05/08/10/12
counterpart acceptance and all-domain M3 acceptance remain pending.

## Static production/delivery/storage/use chain

`chain.evaluate_chain(ProvisioningRequest, units)` composes the real finite
allocator and freight adapter. Canonical Python v1 contracts generate
`contracts/provisioning.schema.json` and TypeScript. A request binds one period,
a resource ID for every physical stock, and at most 32 explicitly ordered phases.
This is a trusted host calculation interface, not a model activation permission.

Every phase declares fresh claims/reservations, its complete claim order,
procedure, coefficients, access, funding knowledge and provenance. Production
requires declared yields or loss. The shared allocator checks physical dimensions,
actual-input mass balance, scope, positive funding rates, quantum lattices and
finite budgets. Product and residual quantities are actual output, never requested
output. Labor, land and energy capacity IDs are ports into shared accounts, not
private domain budgets. Energy here is a dated capacity requirement; multi-input
physical recipes need a separately reviewed solver. Nothing infers a labor,
transport or civic allocation rule from a stock total.

Freight phases retain the v1 same-resource/unit cross-scope paired actuals. The
additive `LogisticsRequest.closed_claim_ids` field explicitly partitions prior
claims from current routes; omitted means no closed claims, preserving standalone
v1 calls. Closed IDs must be unique and exist, with no corresponding active route.
Their original postings, unmet quantities and unfulfilled holds remain in the
book, and cannot generate a new import. Every other claim requires a route.

Storage phases are local, same-resource/unit, lossless handling into explicit
stock accounts, with selected finite handling requirements and destination
magnitudes. Use phases withdraw actual local stock through selected access and
entitlement rules; use cannot generate product or recycling. Time-dependent
storage loss, replenishment and return transitions remain unavailable. Generic
production losses are explicit calculation evidence, not ecological sink models.
No unlimited external supply is introduced; external stock must already be
explicitly finite in the host-provided initial book.

Phase completion closes earlier claims to further allocation. It does not erase
history, retry them later, cancel obligations or release outstanding reservations.
A later allocation cannot output into any earlier claimed source account; this
conservative v1 guard excludes circular-return chains rather than inferring a
fixed-point solver. The order is a declared dependency/procedural choice. Staged
results show full input/provenance, allocation actuals/outputs/losses, final claim
balances and paired movement references. They do not replace durable accepted
trace evidence or the normal revision operation ledger.

An unresolved procedure/access/funding stops the chain, returns the blocked phase
and staging evidence, and sets final `batch`/`accounts` to null. Earlier stages
are not an accepted result. Invalid interfaces, overflow or invariant failure
raise before returning any candidate; caller inputs remain unchanged. A resolved
candidate is still pure, with no persistence, operation replay, public IPC or
renderer integration. Retrying a full request reproduces the candidate; continuing
from an output requires fresh phase claim IDs and explicit remaining budgets.

The [authored model card](production-use-v1.json) records the hypothetical model,
review boundary, exact independent fixture and port ownership. It is engine-local
and does not alter the immutable production release. Run
`uv run --frozen pytest tests/engine/test_provisioning_chain.py tests/engine/test_logistics.py`.
Fixtures include two local scopes/groups, independent integer enumeration,
by-products/loss, shared labor/land/energy/handling/entitlement limits, inaccessible
surplus, holds, closed actuals, fractional remainders and whole-candidate failure.
Scoped options/coverage, production source review/activation, real counterpart
acceptance, full DOM-01 and WP-032 remain pending.

## Scoped procedures, indicators and coverage

`exploration.interview(request, units, phase_id, scope_id)` returns two original
hypothetical shared `Definition` alternatives: explicit-order partial priority and
explicit-order all-or-nothing. No alternative is selected by default, even if the
input plan already declares a procedure. The full input plan retains that existing
procedure for inspection. Any local phase kind can be explored; every claim in
that phase must use the selected source scope. Freight destinations can cross the
boundary, while a phase with sources in multiple scopes requires a separately
agreed joint procedure. No local question grants control over that joint order.

`exploration.preview(request, units, ProcedureEdit)` accepts only the option ID,
phase, scope, complete unique claim order and baseline digest. It reruns the real
chain after replacing the named phase's procedure/order. It cannot edit access,
quantities, resource identities, coefficients or evidence. The digest covers the
complete base plan, provenance, unit registry, numeric runtime and adapter version;
changes require a fresh preview. Unknown/foreign options, incomplete/conflicting
orders, stale baselines and incompatible scopes fail. This is a **host-only pure
calculation preview**, not a revision token, model approval or renderer API.
Publication still requires the existing review and revision/operation services.
The production interview service continues to record qualitative commitments;
selecting a historical source answer never silently registers an executable model.

`exploration.report(request, units)` returns exact per-claim requested, actual and
unmet quantities, scoped stock/resource/unit/period identities, declared access
and limits, source availability before the phase, and each funding, entitlement
or transport port's coefficient, scope, unit, period and before/after availability.
The report declares the adapter version, partial model coverage and hypothetical
evidence independently from whether calculation resolved. These are shared
balances, not a budget promised independently to each row.
Availability means unreserved free stock; claim-specific holds remain separately
visible in the complete phase account batch. Rows do not rank causes or sum
incompatible resources/units. Zero physical supply, zero delivery capacity,
positive stock behind denied access and limited entitlement remain distinct
fields; finite competition/quantum/indivisibility require the retained procedure
and actual evidence rather than an invented single causal score.

Every row links its exact fulfillment postings and source refs. The complete
nested `ProvisioningEvaluation` preserves output/loss actuals, paired freight
export/import IDs, all holds/accounts and phase order. Account/flow evidence is
returned data, not a new competing reducer or durable trace service. Resolved
earlier stages in an unresolved chain are explicitly staging only: final candidate
accounts stay null, the blocked phase's actual/unmet quantities are null, and
subsequent phases are `not_evaluated`. Known declared ports remain visible with
null measured balances. Repeated reports/previews are deterministic and detached.

The standalone [coverage inventory](../../../../content/provisioning/coverage-v1.json)
accounts for all three source branches, ten leaves, 24 decisions and the source
maintenance decision at the pinned archive. It preserves every source alternative
reference and amendment link, and records partial/unsupported/provenance effects,
hypothetical/unreviewed evidence, scope availability and next research. Generic
mass transformation, freight/handling and access-conditioned use are partial
static capabilities. Source-specific energy/water physics, waste recovery,
circular loops, empirical institutions and all transitions remain unavailable.
The inventory is not part of the immutable production release and activates no
source model. Its exact reconciliation and pure API acceptance fixtures run with:

```sh
uv run --frozen pytest tests/engine/test_provisioning_exploration.py
```

Real DOM-02/05/08/10/12 paired acceptance remains blocked by those counterpart
modules; reassess the next ready static domain allocation after this child merges.
