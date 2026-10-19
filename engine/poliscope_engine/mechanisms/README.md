# Trusted mechanism registry

`MechanismRegistry` is an immutable, model-versioned snapshot. It stores detached
contract-1 declarations, including drafts whose references or implementations are
unavailable. `with_definition` returns a new registry; duplicate ID/version pairs
fail. Historical inspection does not need activation or installed code.

The application supplies `Implementation` objects containing actual trusted
Python callables with exact ID/version/phase keys. The registry never imports a
module named in content or invokes a callback. `activate` resolves the requested
static/transition support, canonical scope/entity kinds, units, time bases,
denominator scopes, source/assumption IDs, fixture versions, policy composition
implementation and state owner. Unknown declarative graphs fail closed until
WP-012-expressions implements their own bounded validation.

Activation also requires a host-supplied `Review` for the canonical declaration
SHA-256 and exact model ID/version, with evidence-review and independent-fixture
review references. The trusted host is responsible for verifying those records
against actual reviewed evidence before supplying them. Pack evidence labels,
structural parsing and historical adoption cannot create reviews or register code.
Synthetic tests use explicitly synthetic dispositions; they do not establish
scientific validity or independent review of this implementation. Registry
construction is an internal engine API, not an untrusted JSON or renderer API.
Changes to trusted code require a new implementation/model identity and review.

`with_pack_definition` parses the exact inline JSON file from a validated
`PackArchive`, checks model and declaration metadata against its mechanism entry,
and returns a new registry. The caller must authenticate the archive using its
expected digest and check full archive/runtime/dependency compatibility separately
before selecting it for a model. Attachment alone does neither compatibility
approval nor activation. Sources and fixtures still resolve through the host's
trusted catalogs; imported IDs never populate those catalogs automatically.

`bind` checks two activated static declarations in one canonical scope and returns
a detached exact port type. Cross-domain references share identity; implicit
conversion, aggregation and account allocation are absent. `validate_value`
checks concrete values against unit/time/denominator metadata or canonical entity
kind, preserving decimal strings. Evaluation owns missing/unknown propagation,
preconditions, claims and diagnostics; registration does not invent defaults.

`stage_changes` revalidates transition activation against the supplied immutable
world, permits only declared dynamic-state properties for the selected entity and
scope, validates exact value types and delegates atomic candidate validation to
`WorldRegistry.with_values`. Owner IDs use canonical domain names. Even a trusted
callback's returned proposals must pass this guard. The result is a pure candidate,
not a database commit. Revisions, stale candidates, account spending, transaction
publication, execution isolation and evaluated transition effects belong to their
separate services. Activation returns a detached declaration for inspection;
consumers must not treat it as a transferable authorization token.

## Bounded expression graphs (contract 1)

The host supplies `ExpressionGraph` objects to the immutable registry. Procedure
identity resolves an exact graph ID/version. Graph snapshots are detached, and
activation requires a `Review.graph_digest` matching its canonical SHA-256 in
addition to the declaration/model and existing evidence/fixture checks. Imported
text cannot manufacture host review. Editing a graph with the same ID invalidates
review. Operator semantics are pinned to the model/runtime; changes require new
versions and review. Pack transport for graphs is not a public execution API.

Graphs contain at most 256 nodes with depth at most 32, 100 outputs and 100 state
proposals. Every node, even unused nodes, is validated. Stable ID order resolves
topological ties; cycles and dangling references fail. Registered v1 operators
are add, subtract, minimum, maximum (exact same quantity metadata), and multiply/
divide by an explicit unit-scale-one dimensionless indicator. No implicit unit,
time or population conversion and no arbitrary dimensional formula is inferred.
Constants are exact quantity strings. Input nodes can pass typed labels and
canonical entity references; arithmetic accepts quantities only. There are no
loops, imports, callbacks, code strings or extension names loaded from content.

`evaluate_graph` rechecks activation and returns detached `(outputs, state_values)`.
It uses the exact Decimal runtime; division by zero and unrepresentable results
fail. Missing or explicitly unknown inputs become `None` and propagate along
all dependent arithmetic paths; optional omitted inputs receive no invented
numeric default. Output dependency declarations must exactly match graph inputs,
including allocation dependencies. Callers retain original unknown reasons for
coverage reporting. This is local arithmetic, not a complete mechanism scheduler:
preconditions, policy conflicts, finite allocation, trace publication and
cross-mechanism solving belong to their respective runtime packages. State maps
must exactly match declared transition writes (and are empty for static graphs).
They carry no mutation authority: validated contextual proposals must still pass
`stage_changes` and subsequent transaction/revision checks before publication.
Structural validation and synthetic arithmetic establish no scientific validity.
