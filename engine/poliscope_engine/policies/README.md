# Scoped policy resolution v1

`resolve` is a pure institutional pass over a `WorldGraph`, reviewed mechanism
registry, version-1 policy bindings and explicitly selected host resolution rules.
It returns detached typed results without executing callbacks, updating stocks,
writing storage, allocating scarce resources or compiling numerical SCCs.

Each binding identifies a mechanism's declared input parameter, exact value,
issuing institution, scope and affected account/choice references. Its semantics
come from the registered mechanism, never a caller-supplied override. Scope/entity
classes and the existing review/evidence/unit gate must pass before activation.
The requested static/transition phase uses its corresponding activation gate.
Known values require exact port metadata; unknown values retain reasons in findings.
Qualitative draft mechanisms are not activated numerically by this service.

An empty entity selection uses direct explicitly aggregating members of the scope.
A nonempty entity list explicitly selects targets rather than inferring containment.
The institution must have a direct `jurisdiction` edge to each entity or the
binding's scope. Missing jurisdiction is an authority finding, not an automatic
rejection of unrelated components. Neither containment, geography nor chains of
jurisdiction imply inheritance or political priority. Overlapping membership does
not create another copy of a binding at a canonical entity. This pass applies to
whole named entities; weighted population shares are not split or allocated here.

Bindings compete only for the same canonical entity/parameter. Exclusive overlaps,
delegation, compositions and bounds require an explicitly chosen host rule.
`ResolutionRule` is data-only, but the `rules` argument is trusted application
configuration, just like mechanism reviews: loading metadata does not authorize
registration. A future public command must validate the player's chosen rule
before calling this API. There is no public wire operation in this package.
Each rule declares versioned identity, an institution with direct jurisdiction,
exact participating policy IDs, affected scope, entity and parameter, and sources.
A rule only matches its exact participant set and a participating scope. Adding a
policy invalidates that match. Two applicable rules produce a resolution conflict.
Sources must resolve in the mechanism registry. Declared composition identities
must match the selected rule; the registry must also recognize those identities.

Engine-defined operations are deliberately small: `select` names the exact policy
for exclusive/delegated semantics; `sum` combines explicitly composable quantities
using canonical exact Decimal arithmetic; `bounds` returns the maximum declared
floor and minimum declared ceiling. It returns a constraint interval, not a chosen
value. Inverted bounds are conflicts. Incompatible metadata/types or operations
remain conflicts even with a selection rule. No conversion is inferred. A missing
selected value propagates missing input; unknown unselected alternatives do not
poison a selected known policy. Sum/bounds require all participating values.
Other composition operators require a future engine change and new identity.

Results expose participants, sources and the full chosen rule, including its
authority, scope and version. Findings expose authorities,
scopes, affected accounts/choices and missing resolution requirements. Allocation
precedence findings are institutional facts; this service does not satisfy claims
or compute allocations. Stable IDs order output only. Independent unconflicted
results survive. Snapshot limits are 100 bindings/rules and 100 targets per binding;
contract reference bounds also apply. Results establish structural behavior, not
scientific validity, institutional legitimacy or full application acceptance.
