# Identity/state registry v1

`WorldRegistry` is a pure in-memory snapshot using the existing world DTOs. IDs
come from the caller and survive label/order changes; the registry does not mint
IDs from names. Entity, scope and value IDs share a namespace. Exactly one
civilization entity must match the registry civilization ID. All canonical entity
kinds are supported. Source and assumption references belong to the later pack
resolver; unit compatibility belongs to numeric/model integration.

Each cohort declares exactly one role: `fixed_input`, `dynamic_state`, or
`solved_capacity_bound`. This records the chosen modeling role; it does not select
a population mechanism or infer which arbitrary property represents its count.

Each entity/property/partition slot has one `StateOwner`. Ownership is independent
of scope, so relabeling an account through another scope cannot create another
stock slot or independent writer. Physical account/asset linkage, spending,
reservations and allocation remain later contracts; this registry cannot prove
that two different IDs are actually the same physical asset.

Inputs are validated and serialized into immutable strings, protecting against
nested mutable DTO lists and caller mutation. Queries return detached DTOs.
`with_values(writer_id=..., partition=..., changes=...)` validates the full batch
and constructs another registry. Any failure leaves the original intact. Existing
value IDs cannot change their entity/property/partition/scope binding. No deletion,
entity migration or ownership reassignment API is introduced. A trusted caller
chooses writer and partition; these are not renderer-supplied authorization.

The six partitions retain distinct ownership. A goal-edit batch accepts only
`goals`, even when a writer also owns a dynamic-state slot. Conditions, design,
assumptions, state and observations remain byte-for-byte preserved in the base
snapshot. Unknown values stay unknown; quantity strings are checked by the
canonical numeric runtime and never converted through float.

This child provides identity and state-change structure. External-interface
semantics, durable revisions and public commands remain subsequent packages.

`world.membership.WorldGraph` adds immutable RelationshipDTO v1 snapshots. Every
endpoint exists; relationship IDs share the world namespace. Only containment
must be acyclic; jurisdiction and network cycles are permitted. `related` returns
detached incident edges; `with_relationships` validates a complete replacement.
Containment does not implicitly define aggregating membership or inherit rules.

Aggregating edges point from canonical entities to scopes. Cohort membership
requires a cohort and an explicit rule. A partition ID identifies one indivisible
member across multiple scope views: a union counts that member once. Weighted
edges declare disjoint shares; selected weights add exactly and cannot exceed one.
Different partition IDs for one member, or mixed weight/partition declarations,
are ambiguous and rejected. Callers must select partition rules for overlapping
observational views rather than labeling duplicate full weights as disjoint.
Nonaggregating relationships never enter sums. These are structural declarations,
not evidence that a modeled partition corresponds to real populations/resources.

`aggregate` sums direct members for an explicit property/state partition. It uses
canonical entity values, exact numeric arithmetic, and matching units, time bases,
denominator scopes and effective simulation times. Missing/unknown members and
empty selections return explicit unknowns. No unit conversion, containment
rollup, inferred population measure, average, allocation or resource spending is
introduced. Relationships do not create owners or duplicate registry stock slots.
