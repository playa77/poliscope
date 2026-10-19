# Bounded finite allocation

`allocate(AllocationRequest, Registry)` snapshots/revalidates strict version-1
inputs and returns detached solved actuals plus an `AccountBook`-validated batch.
It performs no I/O and never changes the caller's batch. The trusted host supplies
reviewed mechanisms, access decisions, funding/entitlement coefficients and the
player-selected procedure. This is an accounting/procedural service, not an
externally callable authorization API or a scientific validation boundary.

`priority` allocates up to each remaining claim in the explicit global claim
order. `all_or_nothing` follows that same declared order but skips a claim unless
its whole remaining request can be served. There is no implicit procedure or
stable-ID precedence. Collection order is irrelevant. Missing procedure, access
or funding knowledge leaves this bounded component unresolved without posting
partial actuals; an unknown competitor cannot be skipped to favor a known one.

An allowed choice declares a per-call maximum additional access quantity. Denial
keeps physical stock and unmet demand visible. Funding and entitlement requirements
consume separate finite budget/ledger accounts per actually allocated input unit;
they never create physical capacity. Shared requirements contend in the same
explicit global order. Scope must match. Periods must match except that undated physical stock can
consume an explicitly selected dated capacity budget (for example labor hours).
This does not accrue hours or infer a period; the selected finite account and
its period remain in the request and accounting trace. Hosts must explicitly
supply period-bound monetary/entitlement budgets for period-bound resources.

Existing actuals reduce remaining claims; outstanding physical holds are available
only to their claim. Fulfillment replaces those holds once. Unreserved allocation
uses only free availability. Input, funding and output quantities must all fit
their account quanta exactly. The least common rational quantum step bounds
allocation; quantities that cannot move remain in explicit source balances and
unmet requests. No transfer or yield is rounded away, and no negative balance is
clamped. This version uses exact conversion, not approximate rounding.

A choice may declare linear physical stock outputs with explicit product/residual
roles, output units and an input-unit loss coefficient. Dimension, scope, period,
unit scale and exact conservation are checked: scaled output coefficients plus
loss equal one input unit. Coefficients multiply **allocated**, not requested,
inputs. Full input withdrawal is already recorded as claim consumption; product
and residual accounts receive production postings. Loss is the explicit consumed
mass not returned in these outputs, retained in each allocation's loss trace.
It must not be deducted from the source a second time. Non-transforming uses
remain ordinary consumption and make no yield claim.

No output account can also be an allocation resource or funding account in the
same call. Resource accounts cannot double as funding requirements. Such coupled
components require WP-014 graph/solver integration; output file order never
substitutes for a solver. This child exposes actual consumption/output edges for
that future integration, without claiming SCC, world authorization, durable
publication, full parent acceptance or complete application behavior.
