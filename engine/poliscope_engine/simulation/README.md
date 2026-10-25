# Atomic transition reduction v1

This is the trusted Python WP-034 host. It composes WP-033 scheduling/adoption,
WP-015 finite allocation, WP-027 domain authority and the merged
WP-036-boundary-store. No renderer endpoint, source-code loader, default civic
policy, overall score or implicit stock/capacity renewal exists.

An experiment explicitly selects a `TransitionPlan`: its opening finite book,
canonical account/value bindings, instance order, old/new claim precedence and
operation quota. Optional transition-only instances require real registered
mechanisms but no fake static implementation. The complete configuration is
frozen with the schedule in the experiment's identity. Every mapped account
belongs to the canonical `shared_accounts` writer and must match a real account
entity and its exact opening balance/unit/scope/time semantics. Static and dynamic
books cannot separately spend the same account. Stocks are quantities, not rates;
dated book periods remain in the receipt without becoming a stock rate basis.

A `TransitionAdapter` is application code registered in the existing mechanism
registry as a versioned `transition` implementation. Declaration/fixture/review,
domain hook, scope, entity and state-owner checks gate it. Content cannot provide
callbacks. `propose(invocation)` declares typed finite claims, access/funding
terms and transition class. `resolve(invocation_with_actuals, proposal)` proposes
only owned state writes from solved actuals. `validate(invocation, proposal,
writes, complete_closing_inputs)` checks the selected model's independent
invariants and must return None or raise. These are trusted pure callbacks, not a
Python sandbox. Repeat execution detects differing results and input mutation;
every call receives detached inputs and a fresh canonical Decimal context. Host
implementation versions and review evidence must describe the actual code.
Callback inputs are a typed physical view, restricted to declared read partitions;
undeclared policies/assumptions are unavailable, and goals, notes and measurement targets
are never available. Full-state invariant checks also exclude those annotations. Declared policy reads
receive the shared resolver's typed outcomes, including conflicts; they never pick
a raw binding by input order.

Each private boundary:

1. Stages dated conditions and approved scoped policy deltas, never revision
   snapshots. Resolves due instances and declared preconditions under that staged
   configuration. Known inapplicability causes no effect; unknown selected model
   prerequisites cannot become zero competing demand.
2. Collects proposals before spending. One global finite request uses the selected
   procedure/order. Unknown access or funding withholds shared allocation; declared
   allocation feedback without a supported coupled solver is retained as unresolved,
   never replaced by a single pass. Resource-free supported effects remain available.
3. Materializes actual accounts and an independent Fraction balance/quantum oracle.
   Binds closing quantities back to canonical resource state. All original postings and terms
   survive in immutable prior receipts. The active book rolls exact closing
   balances forward and retains only outstanding claims/reservations, with original
   requested and prior-fulfilled quantities explicitly preserved for owned claims.
   This does not replenish capacity or erase fulfilled history.
   Fulfilled old claims cannot consume again. A pending claim whose owner is not
   due is explicitly paused/unknown; its original terms are restored only for a
   due model. Unknown footprint of an unresolved selected model conservatively
   withholds the shared book instead of favoring a known competitor.
   An owning model can explicitly refine unknown pending access/funding when
   dated evidence resolves it. The expected prior-choice digest is mandatory;
   known rights, claim quantities, coefficients and account mappings cannot be
   reauthorized through that refinement. Earlier terms remain in prior receipts.
4. Stages typed, time-bound, disjoint domain writes through the production
   conformance/ownership checks; rejects aliases and conflicting writes. Checks
   full closing-state model invariants, static solver status and evidence closure.
5. Recomputes the candidate in the boundary-store validator, then confirms state,
   transition receipt, static result/trace closure and exact operation outcome in
   the provider's single transaction. Only committed journal rows are queryable.

Posting IDs are local to a boundary receipt and must be qualified by experiment
context and sequence. Receipts retain selected classes, statuses, provenance, actual demands/allocations,
original pending terms, all before/after account witnesses and state writes.
`coverage` describes the selected transition computation, never scientific validity
or sufficiency. Known shortage remains an unmet amount even with complete
computational coverage. Missing native models stay `coverage_gap`; no class model
is inferred from a domain name. Reviewed procedural adapters are implemented;
transition graphs without this reducer's adapter remain explicit gaps.

`preview(expected, day)` is noncommitting. `advance_boundary` provides exact
payload/context-bound confirmation and reconstructs completed retries from retained
history before requiring a model or callback. `run_chunk` requires the current
confirmed head and bounds the number of boundaries; per-boundary operation IDs are
stable. Progress fires only after confirmation and retains the worst coverage in
that chunk, including intermediate gaps. Cancellation checks span proposal,
allocation, resolution, invariants, evidence, precommit recomputation and writes.
Cancellation resumes from the confirmed head; no postcommit cancellation can undo
acknowledged work. These bounded chunks are not WP-036's full durable experiment
controller, checkpoint selection, pause/replay or retrospective-fork workflow.

Existing v1 boundary histories and operation bindings remain readable: absent
transition extensions do not change their state/request/schedule identities.
Account mappings, pending ownership and refinement references are canonical sets;
instance/claim priority orders remain semantic sequences.
Historical reads need no historical numerical registry or callback. The only
new numerical class examples are explicitly hypothetical test models; real source
transition activation and empirical model validation remain separate domain work.

WP-035 adds an optional frozen `random_plan`. Explicit named draws are realized
privately before proposals, charged to the quota and passed through each
invocation only for its declared references. Full realizations remain in the
confirmed transition receipt. See [the sampling contract](../stochastic/README.md)
for dependence, persistent variables, fork policies and historical/runtime rules.
