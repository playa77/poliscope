# Shared accounts v1

`AccountBook` snapshots and validates a bounded `AccountBatch` of definitions and
already solved actual postings against the canonical numeric unit registry.
Queries return detached DTOs. IDs are unique across accounts, postings, claims,
reservations and subtotals. The host supplies world/revision-bound identities,
reviewed mechanism references and scope/access authorization. This module checks
accounting, not those permissions; there is no public command or persistence.

Stock, flow and capacity accounts retain unit, scope, explicit period and declared
physical, budget or ledger invariant. Flow/capacity require a period; values are
quantities available in that period, never rates automatically integrated over a
calendar. Unit kind must match. Ledger identity checks do not assert a universal
physical conservation law for money, entitlements or social indicators; these
require separate model-specific accounts/mechanisms. No monetary-to-food exchange
or social effect is inferred.

Supplies, imports and production are explicit inbound boundary postings; domestic
use, export and loss are distinct outbound categories. Internal transfers and
residual movements have two endpoints with identical unit, kind, scope, period
and invariant. Cross-scope exchange and transformations require explicit upstream
mechanism modeling, not a unit-label edit or implicit conversion here. Mechanism
and source references remain inspectable in `book.batch`. Production/loss actuals
are trusted solved values: verifying yields, residual products and actual-input
feedback belongs to the allocation/compiler/evaluation children.

Each account satisfies opening + incoming = closing + outgoing exactly using
rational sums, independently of Decimal context. Every individual posting and
closing balance must also fit its declared WP-006 quantum/range. Negative balances,
quantum loss, overdraw, unknown references and incompatible transfers reject the
whole candidate. There is no tolerance or clamping. Boundary postings assert
explicit modeled inflows/outflows, not a fabricated source of supply. A finite
external supply must have its own finite account and transfer postings. A transfer
does not multiply supply across recipients.

Reservations are physical holds, distinct from WP-048 provider spending. A hold
references one claim and account. Fulfillment postings name both claim and hold:
closing is debited by actual use, while outstanding hold is reduced by the same
amount. Availability is closing minus outstanding holds, so the hold is deducted
once. Duplicate reservation IDs, overfulfillment, excessive/unfunded holds and
holds beyond remaining requests fail. No file-order precedence is selected.
Claims return actual and unmet quantities, including zero fulfillment beside
surplus. An unfulfilled request is playable; a request alone neither grants
access nor creates a resource allocation. Allocation/access/funding procedures
remain WP-015-allocation.

Inputs must already include explicit rounded postings and residual movements.
Use `numeric.stage_transfer` to derive a quantized transfer and its signed residual;
translate positive residuals to source→residual and negative residuals to
residual→destination postings. Submit every posting together. Missing or invented
residuals cannot be inferred from an unlabeled amount: upstream transformation
and publication consumers retain that obligation. This module never rounds
postings or labels a remainder consumption.

Subtotals declare account/subtotal members. Unknown members, cycles, duplicate or
overlapping leaves and incompatible signatures fail. `total(tuple_of_ids)` sums
closing balances over compatible disjoint leaves and rejects adding a subtotal
beside any of its members. Account definitions/quanta can differ in resolution;
aggregate totals must still fit the authoritative exact Decimal runtime.

No allocation solver, transition, durable publication, numerical SCC, provider
call, implicit rights or scientific validity is delivered here. Full WP-015 and
application gates retain their remaining acceptance obligations.
