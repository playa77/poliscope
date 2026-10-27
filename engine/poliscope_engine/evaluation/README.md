# Pure static evaluation

`evaluate(world_graph, design, assumptions, model_identity, registry=host)`
returns a detached version-1 `EvaluationResult`. WorldGraph and the immutable
host MechanismRegistry are internal Python services, not renderer capabilities.
There is no database, provider, wall-clock, sampling or state publication step.
Inputs and results can be inspected without accepting a design or altering a save.

The bounded design selects an execution plan, effective simulation time, policy
bindings/rules, external input bindings, precondition rules and explicit realization
evidence. World bindings require exact entity/scope and a declared read partition.
Assumption/realization IDs bind repeated uses to one supplied value; missing
references are structural errors, while explicit unknown values propagate missing
coverage. Fixed, world, assumption, realization, policy and numerical producers
cannot silently overwrite one another. Policy floors/ceilings only become point
inputs if the host explicitly selects that projection. Unresolved policies remain
conflicts. No automatic adoption, civic precedence, target optimization or sampling
is introduced. Measurements, optional target observations, richer findings and
public inspection retain WP-017 and transport acceptance.

Preconditions have descriptions but no existing executable predicate contract.
Versioned host-selected unary rules supply typed equality/order/known predicates
for exactly the declared input reference. Multiple preconditions form conjunction.
Unsupported multi-input semantics require an explicit future rule extension;
missing rules yield missing coverage rather than silently passing. Compiler edges
include precondition inputs before SCC classification. Failed predicates return
the declaration's `not_applicable` or `conflict`; the callback does not run.
Descriptions and imported rules never authorize code. Host-selected design/rule
construction is the caller's responsibility; this API is not a content-pack API.

Numerical execution continues independent components. Missing, unmodeled,
precondition conflict, solver failure and partial support retain distinct coverage
through downstream dependencies. Account batches are returned only when all
numerical components are solved; a partial numerical model remains marked partial.
Claim distributions include exact actual/unmet amounts; the retained final batch
identifies claimant, scope, period, accounts, postings, and source provenance.
Physically insufficient but valid designs return `insufficient`, distinct from
structural exceptions and unresolved allocation. Trace edges retain numerical,
precondition, funding and transformation dependencies. All input/model/realization
snapshots remain available; this is numerical/structural evidence, not scientific
validation. Qualitative/unsupported declarations never execute callbacks.

Canonical version 1 normalizes declared Decimal fields/quantities, sorts declared
unordered maps/sets, and preserves semantic sequences including political claim
priority, iterative update order, event order and expression operands. Label text
is not a Decimal. The complete world (including unbound properties), design and
assumptions identify input; full definitions, expression graphs, review records,
implementation IDs/versions/phases, units, periods, catalogs, evaluator/numeric
runtime and exact Python patch version identify model. Realization identity, seed,
ordered event IDs and supplied values identify realization. Their digests form the
cache key; the complete result payload forms output identity. Strict contracts
have no request-ID or bookkeeping-time fields; effective time stays included.
This conservative identity may miss reuse opportunities but cannot reuse on equal
visible indicators. Native reproducibility across Windows x64 and Linux x64 remains unverified.

`EvaluationCache` is a bounded host-owned wrapper, separate from pure evaluation.
It validates/resolves fresh inputs before lookup, stores detached JSON and checks
output digests. Only locally generated entries are accepted. Entries also retain
the exact registry object, preventing a new callback object from borrowing an old
entry under copied implementation IDs. Host code changes must increment the
implementation/model/runtime versions: manifests are not Python source hashes.
A digest detects accidental corruption, not hostile host memory changes. This
cache is disposable and never a repository of accepted result evidence.
It bounds both entry count and serialized UTF-8 result bytes (64 MiB by default),
refreshes recency on hits and evicts older entries before admission. An oversized
result is returned complete without caching. `clear()` discards disposable entries
without changing retained evidence. This byte quota does not bound registry
objects, Python overhead or combined application RSS; those need measured process
budgets. The wrapper remains an explicit host API, not automatic revision caching.

Purity tests install tripwires for filesystem, SQLite, sockets, wall clock and
random draws, verify normal evaluation makes no calls, and show injected impure
callbacks fail visibly. Reviewed Python callbacks remain trusted application code;
these tests and the API do not sandbox arbitrary Python or make external effects
reversible. Future callbacks must retain the purity validation route.
