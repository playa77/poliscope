# Uncertainty and capacity methods v1

These pure, opt-in calculations are pinned to an immutable revision. They do not
activate content models, choose policies, edit the world, rank alternatives or
sample a source range. `contracts.uncertainty` generates the bounded JSON Schema
and TypeScript API. The named desktop grants are `uncertainty`, `sensitivity` and
`capacity`; the workspace CLI uses those same operation names. Inputs and method
assumptions are echoed in every report, with provenance, coverage and digests.
All numbers use the existing exact Decimal runtime; probabilities are reduced
integer fractions. No binary floating-point or wall-clock value enters results.

## Explicit parameters and dependence

Each parameter has a stable ID/version and references one revision quantity.
Point values require exactly one point. Closed ranges require ordered bounds.
Distribution and qualitative declarations cannot smuggle in a point or bounds.
Repeated references share the same variable; two variable IDs cannot alias one
revision quantity. Local method assumptions include IDs, versions and rationales;
source references must resolve in the revision. A hypothetical declaration is not
source evidence or scientific review. No midpoint, uniform law or empirical
probability is inferred. Explicit sensitivity selection is a separate decision.

`affine-box-v1` supports dimensionless coefficients over quantities with identical
units, scope, time basis and denominator. It combines coefficients symbolically
before computing exact extrema. Thus `x + (1-x)` is exactly 1 even when x ranges
from 0 to 1. `declared_box` states that the distinct bounded variables may take
any combination in the specified box. It is an admissible-set assumption, not a
probability/independence assertion. A restrictive non-box dependence cannot use
this method and remains unresolved. Threshold diagnostics distinguish always,
never and overlap; range overlap is not a probability. Mathematical constant-only
expressions have no physical quantity metadata. No nonlinear propagation or
silently widened interval approximation is registered.

`finite-factorization-v1` enumerates the complete finite joint law. A factor owns
one or more distribution variables. Each conditional row declares its parents'
values and joint outcomes with exact probabilities summing to one. Multiple root
factors explicitly assert factorization; missing dependence does not multiply
marginals. Shared latent causes are ordinary parent variables consumed by
conditional factors. A joint factor can also encode common-cause outcomes
directly. Every distribution variable has exactly one owner. Cyclic dependence,
mixed probability/range problems and exceeded enumeration/precision limits return
unmodeled coverage, without a truncated probability. Missing/duplicate conditional
rows, unreachable rows, malformed probabilities or inconsistent references are
invalid declarations. Reachable positive-probability parent assignments require
exactly one row. Every report distinguishes the finite law from a realization.
This service never draws random numbers; WP-035 remains the named-stream sampling
authority. A table is not automatically converted into a stochastic transition.

The independent example has two supplies failing together with probability 1/4.
A shortage when either fails has probability 1/4 under that common cause, versus
7/16 under explicitly independent failures with the same marginals. Conditional
and joint encodings give the same result. Repeating a variable never resamples it.
The support, not its enclosing interval, determines equality probabilities.

## Sensitivity and presentation

`SensitivityQuery` enumerates up to twenty explicit complete point variants. Every
selection retains its player/model decision reference. Points must respect the
declared point/range/support; finite joint models additionally reject impossible
combinations of individually valid marginal values. Each variant runs the real
revision preview/evaluation/measurement pipeline, preserving its original model,
realization and baseline. No variant is applied, ranked or chosen automatically.
The report retains each full measurement/trace closure and its physical digest.
There is no automatic range propagation through an arbitrary mechanism graph.

The desktop inspector exposes point/range and two-outcome finite declarations,
threshold coverage, exact probabilities, explicit A/B variant previews and the
optional resource bound. Assumptions and exact values have accessible text/table
representations. Full multivariate factor tables are supported by the typed
service; a general graphical factor editor is not provided. Method reports are
noncommitting previews, not durable accepted timeline results. The normal
workspace's missing numerical mechanisms remain visibly unmodeled.

## Registered capacity calculation

`linear-resource-capacity-v1` is the sole registered capacity method. Each
constraint declares a pinned available resource value and aggregate demand
`fixed_demand + demand_per_unit * solved_value`. Both demand terms are
nonnegative, giving an explicit proof of monotonicity. Each resource budget occurs
once. The solver neither discovers constraints nor allocates an omitted resource.
The player/model selects a named solved entity/unit, the fixed quantities, an
aligned nonnegative search interval, quantum and iteration limit. The solved
entity cannot also supply a fixed/evolving quantity. A population must explicitly
have role `solved_capacity_bound` and the registered people dimension, never
`fixed_input` or `dynamic_state`. Scope/time/unit mismatches and unknown units are
rejected. Missing supply yields unmodeled, not zero capacity.

Binary search over integer quantum indices stops at adjacent feasible/infeasible
points. Each constraint returns independently inspectable demand witnesses.
An infeasible lower endpoint means no solution in the selected interval. A
feasible upper endpoint reports `upper_feasible`, not an unbounded/global maximum.
Iteration or Decimal representability failure is explicit. For 20 kg available,
2 kg fixed use and 3 kg/person, whole-person capacity is 6 (20 kg), while 7 requires
23 kg. With half-person quantum the bracket is 6 and 6.5. An additional 17 kg
resource with 2 kg fixed and 4 kg/person narrows whole-person capacity to 3/4.
Player goals are post-calculation observations and cannot alter these constraints.

The current exact methods are bounded educational computations. Continuous laws,
nonlinear/range-dependent optimization, automatic model/source activation,
scientific validity, Windows certification and the full G4/M4 transition gate are
not established by this package.
