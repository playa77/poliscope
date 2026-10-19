# Static dependency compilation, version 1

`compile_dependencies(request, registry, world)` validates and activates exact
reviewed static mechanism instances without calling implementations. Exact
quantity metadata (unit, period and denominator) and reference/label types must
match at numerical bindings. Cross-scope conversion requires a future explicit
adapter. A port has at most one producer, including fixed and allocation inputs.

Every mechanism claim must bind to a canonical account entity and an explicitly
named allocation group. Claims on one account cannot split across independent
groups. Compiler order never supplies political precedence. Shared groups may
span several accounts. Account quantities must agree exactly; conversion is a
mechanism dependency, never an implicit unit conversion.

The numerical graph expands requested outputs → claims → shared allocation →
actual consumption → allocated input → dependent outputs before SCC detection.
Account producers add output → account dependencies before classification, so
production feedback cannot disappear into an external bookkeeping pass. An
account producer denotes a dependency, not a posting or permission to create
resources. Solver integration must check physical yields, funding and final
account conservation through the existing allocator/AccountBook.

Nodes have collision-free tuple identities; immutable types and request snapshots
are JSON strings. Components are strongly connected numerical subgraphs in
stable topological order of the condensation DAG. `ready` means structurally
schedulable, not numerically evaluated. `missing_input` identifies an absent or
explicitly unknown propagating input. `solver_required` marks cycles, including
self-loops. `blocked` marks acyclic dependents of unresolved components. Full
missing-input identities remain separately inspectable even within cycles.
Optional `omit` inputs may remain absent or unknown without blocking scheduling.

Institutional and documentary relationships retain kind, endpoints and source
reference in a separate immutable collection; their cycles never enter numerical
SCC detection. IDs order computation, never civic decisions.

The request permits 100 instances and 1,000 items per binding collection. Expanded
graphs cap at 25,000 nodes and 50,000 edges; exceeding a cap raises an explicit
`dependency_budget_exhausted` error without returning a partial graph. Iterative
SCC traversal avoids Python recursion depth limits. Input collections are detached
and revalidated; results contain only frozen records, tuples and strings.

This is a static plan, never an execution capability or evaluation cache identity.
Its digest covers canonical request, model identity and activated declarations;
execution must revalidate current world, implementations, reviews and solver
choices. WP-014-solvers owns finite allocation, linear/iterative execution,
actual-output values, funding/entitlement dependencies and final-account staging.
No callback runs, numerical result is inferred, account materializes, policy is
selected, scientific validity is established or application milestone passes.
