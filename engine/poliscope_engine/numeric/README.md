# Numeric runtime v1

`decimal28-half-even-exact-v1` fixes 28 significant digits, half-even rounding,
adjusted exponents -256 through 256, strict decimal-string inputs up to 256
characters and tuple exponents -512 through 256. No float is authoritative.
Stored values must be exactly representable. `calculate` uses a fresh Decimal
context, then compares its answer to a rational oracle; an inexact result is a
`precision_unsupported` error. Callers needing rounded allocations use an explicit
account policy and retain the remainder. Neither the process context nor mutable
`DefaultContext` selects runtime behavior. Python/runtime/platform identities
remain additional save/reproducibility metadata, not inferred from this ID.

`canonical` removes negative zero and insignificant trailing fractional zeros,
uses plain notation up to 256 characters and normalized scientific notation
beyond that boundary. It never uses context-dependent normalization. `display`
is a separate half-even fixed-place formatter; its output is presentation only.
The existing world/wire DTOs still preserve raw decimal spellings; semantic
consumers must call `parse` rather than treating structural validation as numeric
permission. No wire schema or compatibility version changes in this package.

`Registry` is an immutable tuple of immutable unit definitions. Dimensions are
sorted tuples of unique named integer powers, allowing new domain dimensions.
Positive scale factors relate units to the dimension's declared base. Kinds
separate stock, flow, capacity, count, time, entitlement, money and indicator even
when dimensional tuples coincide. Money never converts into a physical stock.
An exchange/yield mechanism must explicitly model its inputs, outputs and losses;
this registry does not manufacture a market conversion.

`convert` requires identical dimensions/kind and scope, exact representability,
and explicit time bases for flows/capacity. Rate conversion multiplies by target
seconds/source seconds. A population denominator is a positive explicit count
with immutable caller-supplied cohort/revision identity and matching scope.
Conversion first multiplies by the source denominator, then divides by the target
count. Unknown/zero counts fail. Provenance and revision authorization remain the
owning world's responsibility. Temporal definitions (including a 365-day year in
synthetic tests) are supplied by callers, not selected as the game's calendar.
Spatial aggregation needs world membership/weights; requesting another scope is
rejected rather than assuming identical populations or a uniform distribution.

`AccountPolicy` fixes a positive power-of-ten quantum, nonnegative balances,
maximum and reject/retain residual rule. The maximum must be an integer number
of quanta smaller than 10^28, ensuring every permitted balance is representable.
A `1E29` stock therefore cannot declare unit resolution; a quantum of 1000 is
permitted, but a unit posting is rejected. Quantization is exact half-even over
integer quantum counts. It returns both posting and signed residual. A nonzero
amount rounding to zero fails as a lost transfer.

`stage_transfer` is pure. It debits the exact requested amount, credits the
quantized destination posting and credits the signed remainder to an explicit
residual `Balance` in the same scope/unit. Source and residual accounts can have
finer quanta. Negative residuals require funding in the residual account; balances
never go negative. Inadequate resolution, range or funding rejects the complete
candidate. Duplicate account IDs and cross-scope/unit transfers fail. A future
mechanism can explicitly authorize and model transfers across scopes rather than
silently bypassing this check.

Exact integer quantum counts and rational sums prove opening total equals all
closing balances, and requested amount equals posting plus residual. There is no
tolerance, invented consumption or side effect. The store consumer must publish
**all** returned balances in one transaction with its revision/idempotency checks;
this module neither writes SQLite nor certifies those later integration gates.
Typed `NumericError.code` values distinguish invalid inputs, unknown/incompatible
units/scopes/time bases/accounts, unsupported precision, invalid denominators,
invalid account policies/balances/transfers, missing residuals, lost transfers,
insufficient funding and conservation failure. Diagnostic strings contain no
private payloads.
