# Provisioning: static freight adapter

`logistics.transport(LogisticsRequest, units)` stages a detached, pure candidate
through the shared `allocate` and `AccountBook` services. It has no private stock,
engine, database or numerical context. Canonical account IDs remain the only
resource/capacity authorities. The host supplies resource bindings and routes;
this adapter does not infer geography, connectivity, scientific evidence or
execution permission from imported content.

Each existing batch claim is a freight claim against a source stock. Declare
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
allocation choices. Production/transformation already has shared finite actual-
input semantics; complete production/delivery/use integration remains a later
DOM-01 child. Losses, unit conversions, intermediate storage schedules, routing
optimization, replenishment and circular returns are unavailable in freight v1.
The authored [model card](freight-v1.json)
is hypothetical arithmetic evidence, not source-corpus or empirical approval.

Run `uv run --frozen pytest tests/engine/test_logistics.py`. Its independent
integer enumeration and literal fractional/reservation fixtures cover two
recipient groups sharing source stock, truck and crew budgets; distribution under
explicit alternatives; unreachable surplus; access denial; time-period isolation;
prior fulfillment; overflow; and malformed interfaces. Real DOM-02/05/08/10/12
counterpart acceptance and all-domain M3 acceptance remain pending.
