# Measurements after evaluation

`observe(evaluation, definitions=(), goals=())` is a pure host service over a
validated WP-016 result. It never calls a model, changes a world, allocates a
resource, samples, ranks designs, or writes to a store. Definitions and target
comparisons are canonical Python contracts, with generated JSON Schema and
TypeScript in `contracts/measurement.*`. `MeasurementError` identifies invalid
structure; an unavailable valid observation retains its coverage and reason.

Versioned host-authored definitions name a procedure, exact input nodes, unit,
scope, aggregation, time basis, denominator scope, interpretation and provenance.
Identity, sum, mean, minimum, maximum, ordered difference and ratio are supported.
Inputs must have the same explicit scope; metadata must match exactly. Spatial
aggregation and unit conversion must already have been performed by a declared
world/mechanism adapter. A ratio requires like input quantities and a canonical
dimensionless indicator output. There is no guessed population denominator,
probability, interval propagation, good direction or warning margin. Arithmetic
uses exact rational intermediates checked against the Decimal runtime; division
by zero or an unrepresentable result is `solver_failure`, never rounded silently.

Every definition and dependency contributes coverage. `known`, `partial`,
`missing_input`, `unmodeled`, `conflict`, `solver_failure`, `not_applicable` remain
distinct. A partial numerical value stays inspectable but cannot pass a diagnostic
or target as wholly known. Unknown is not zero. Named versioned diagnostics have
typed thresholds, explicit comparison operators, interpretations and provenance.
Metrics without diagnostics remain neutral. All four diagnostic finding categories
are supported; target observations form the fifth category. Unmet physical claims
have a dedicated account trace. Known access/limit gaps are institutional findings. Coupled funding constraints
retain uncertain causal attribution instead of asserting physical absence. Exact causal
attribution among simultaneous constraints requires a separately declared
model/diagnostic; this service does not invent one. Policy resolution gaps remain
institutional findings.

Goals default empty. Narrative goals remain questions. Typed goals compare
known measurements after evaluation, with no callback into physics. Goal results
and measurement reports have their own identities; a target change preserves the
physical output digest, account allocations and calculation traces. No aggregate
score or ranking exists. `sufficient` may be false on explicit evidence; successful
finite computations never imply complete societal coverage or set it true.

## Traces and retained evidence

`explanation.build_traces` groups numerical SCCs into a DAG and retains internal
feedback edges, mechanism IDs/versions, entity/scope/time, typed input/output
values, source references and bound assumption identities. Final posting amounts,
account balances, available/reserved amounts and actual/unmet claim quantities
also have trace nodes. A shared finalization vertex bounds account dependency
fanout. Independent failures retain their traces. Trace IDs identify structural
vertices inside a report; queries bind report identity and an optional root.
`trace_page` walks transitive dependencies with count and byte bounds. Cursors
cannot cross reports/roots. An individual vertex larger than the response budget
fails visibly as `trace_node_requires_chunking`; it is retained intact locally.
Future IPC may chunk such vertices; no oversized protocol message is emitted.
Authored `explanation.TEMPLATES` are fixed versioned text, separate from AI prose.

`retain(result, report, references=())` returns a detached, hashed
`AcceptedEvidence` closure after verifying the report against its actual input.
It includes full approved simulation input/model/realization snapshots, all
accepted observations/definitions/targets/findings/traces and typed source and
assumption metadata. Source descriptors retain repository/document/revision,
location, excerpt digest, license and historical status. Transitive evidence
references are closed; missing descriptors are explicitly unavailable and private
by default. The complete closure must be persisted transactionally with acceptance
by WP-018, outside disposable caches. This package prepares the data and does not
accept a revision or claim that database integration is complete.

`read_retained` validates and reads the stored data without a registry, callback,
cache lookup or measurement recomputation. It does not recreate unavailable legacy
results under a new model. `unavailable()` records that absence explicitly. Schema
and canonical-identity compatibility remain necessary; this internal service does
not replace the separate trusted historical-reader protocol or waive its limits.
Hashes detect accidental corruption, not malicious reauthoring by a trusted host.

Reference catalogs classify visibility and availability independently. No private
payload can be promoted through a citation automatically. The owning producer
must supply only player-approved simulation data in `EvaluationResult` and only
host-authored public text in definitions/templates. Private conversations, excerpts
and rationale belong in their classified stores. Local target questions remain
separate post-evaluation content. `public_projection` excludes snapshots and all
goals, filters source/assumption/supersession references and metadata, recomputes
provenance-sensitive finding IDs, marks omitted-reference counts and hashes the
projection independently. It preserves physical values and the approved physical
output identity. Explicit public descriptors can be included; private IDs,
descriptions and private-only hashes are omitted. This deliberately evidence-reduced
projection is not an ordinary full portable save; portable archive integration
remains its own package. Hosts must not relabel it as a complete save.

Bounds: 1,000 definitions/goals, 100 operands/diagnostics per definition,
10,000 findings/reference descriptors, 40,000 trace vertices, 100 items/page and
900,000 serialized bytes/page. Limit failures publish no partial report. These
are deterministic structural observations on synthetic fixtures, not independent
scientific or usability validation.
