# Host-only education capacity prerequisites

`evaluate_education(request, graph=..., mechanisms=..., units=...)` inspects
explicit dated staff/student time, materials and facility-slot commitments.
DOM-02 owns all work/goods/access allocation and canonical cohort time; WP-013
owns policy conflicts. The shared allocator owns facility slots, reservations,
prior fulfillment and quantum arithmetic. This module owns no mutable state.

Each service maps positive student `training`, staff `paid_work`/`unpaid_work`,
physical `goods` and facility claims. Staff qualifications and archive/skill,
technology and obligation references are declared host evidence. They neither
prove a qualification nor activate an empirical learning model. Direct authority
and the exact binding/target/parameter must resolve through WP-013. Missing rules,
access or qualification stay unresolved; known ineligibility is distinct from
capacity shortage. Reports retain full requests, cohort/asset/account identities,
prior and additional work, unmet claims, policies, units, period and postings.
Facility prior actuals are in the retained allocation request/accounts evidence;
`actuals.allocated` is additional fulfillment only. Unresolved facility actuals
are allocator placeholders, not measured zeros; check allocation status first.

Facility inputs form a disjoint account/claim pool with one `capacity`/`budget`
account per canonical asset in the period, dimension `facility_slot`. Competing
facility uses must be included in that pool. Posting IDs belong to their pool;
reports must not be concatenated into one batch without explicit ID remapping.
Cross-period/scope pooling, resource copies and unmodeled facility conversions
are rejected. Operating supplies belong to DOM-02's goods pool. This is a bounded
host-declared asset capacity interface, pending actual DOM-08 facility operation
and connectivity, not a substitute for that module.

The pools allocate independently. `capacity_ready` means every declared input
requirement has been fulfilled, including prior commitments. It does **not** mean
a lesson happened, attendance synchronized, skills changed or a course completed.
A blocked/denied/unqualified service can still have input commitments in another
pool: there is no inferred refund, optimization, rescheduling or atomic service
transaction. Callers must inspect both reports. Reusing the staged pools retains
prior fulfillment and does not spend inputs twice. No durable publication or
numerical IPC activation is provided.

Synthetic acceptance tests exercise staff/student/care competition in the actual
DOM-05 evaluator and preserve materials into the actual DOM-01 chain. A finite
integer oracle checks input quantities and readiness independently. Other domain
counterparts, all-domain education integration, research/culture mechanisms,
interviews/source coverage, durations, skills and transitions remain pending.

`exploration` provides host-only scoped interviews and pure stale-bound queue
previews: retain the declared queue or put explicit education input claims first.
Care and other work still compete in canonical accounts; facility order stays
fixed. Full host/mechanism/world context binds edits. No default, application,
learning or publication is provided. `coverage` checks the standalone exact source
inventory in `content/knowledge-culture`; source options remain provenance only.

The host-only real DOM-01/06 counterpart is in
[`provisioning/education.py`](../provisioning/education.py), with fixed reviewed
conformance bindings in `education_counterpart.py` beside it. Actual education
commitments consume local time/materials once before cross-scope production,
freight, storage and use. Facility evidence stays independent. See the versioned
`tests/fixtures/domains/provisioning-education-v1.json` and package evidence;
this bounded pair does not satisfy the all-domain education path or learning.
