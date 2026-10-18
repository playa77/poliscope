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

This child provides identity and state-change structure. Relationship validation,
containment acyclicity, memberships/weighted aggregation, external-interface
semantics, durable revisions and public commands remain subsequent packages.
