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
