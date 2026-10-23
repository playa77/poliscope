# Explicit access and shared work assignment

`evaluate_economy(EconomyRequest(...), units)` is a pure host adapter over the
canonical account book and allocator. Contract v1 is generated to
`contracts/economy.schema.json` and `contracts/economy.ts`. The full request,
access/term provenance, incremental actual/unmet claims, account balances,
reservations and postings remain inspectable. No separate world or ledger exists.

Each goods activity identifies a physical stock claim, explicit eligibility and
access limit, plus any finite entitlement/funding requirements. Every such budget
has one declared holder and role; only that claimant can spend it. There is no
automatic currency-to-goods conversion. Funding is a declared budget debit, not
a payment to a seller or a wage. Unspent remainders stay in the original accounts.
Stock exists independently of rights: a zero rights budget can leave all goods
unconsumed, while denied eligibility remains distinct from insufficient rights.

Paid work, unpaid work, care, training and participation consume the same dated
capacity for a given canonical cohort. The adapter rejects duplicate cohort time
budgets, foreign holders, wrong dimensions/periods and incomplete activity maps.
The host must supply canonical disjoint cohort identities and an authoritative
opening population/time budget. Aliases or partially overlapping cohorts cannot
be validated from account IDs alone; resolve them through shared world/membership
services before this adapter. Geography cannot create a second workforce.
Work labels neither create wages nor imply service output, skills or employment
rates. Production/service definitions must separately consume actual resources.

Priority and all-or-nothing are selected procedures with an explicit complete
claim order. Neither is a default civic policy. Unknown precedence, eligibility
or terms gives `unresolved` and `batch=null`. The retained allocator's zero
increment placeholders carry `reason=unresolved`; they are not measured zero
outcomes. Its unchanged batch is staging evidence, never a complete candidate.
No automatic ranking or explanation of a unique shortage cause is inferred.

`compile_choices` checks exactly the same terms and returns canonical
`AllocationChoice` records for a provisioning use phase. Match the claims, account
IDs, period, terms and selected order, and validate through `evaluate_chain` using
the actual phase batch. Compiled choices do not carry publication authority or a
stale-base guard. Host-only preview code must not treat them as accepted history.
For work before production, pass the resolved shared batch to provisioning:
old claims are closed there and the same remaining labor budget constrains output.
Holds and actuals retain their IDs. An invocation on a previously fulfilled batch
allocates only remaining demand, but is not a durable idempotent settlement API.

The [model card](access-work-v1.json) and independently derived
`tests/engine/test_economy.py` oracles are hypothetical. The card is an engine-local
research record, outside the production content release. No source model is
activated. No new renderer/IPC, accepted trace closure, database writes, property
law, prices, wealth dynamics, settlement, recurring schedules or transitions are
implemented. Numerical product activation, full source/branch inventory, scoped
interviews and counterpart/parent acceptance retain their own packages.

## Scoped host exploration

`exploration.interview(request, units, scope_id)` returns authored procedure
alternatives using the shared Definition contract, with no selected default.
They govern declared goods access or the five distinct work/time categories;
they do not define property regimes or wages. Every claim source must belong to
the requested scope. A report can inspect several scopes, but a local edit cannot
reorder a multi-scope allocator invocation. Split or explicitly coordinate such
procedures through a separately designed joint host interface.

`exploration.preview(request, units, EconomyEdit(...))` requires the complete
claim order and exact baseline digest. The digest binds the full request,
provenance, unit registry, numeric runtime, evaluator and exploration version.
Only the procedure and order change; eligibility, holders and terms remain host
inputs. The returned candidate is hypothetical staging evidence, not a revision
candidate accepted by the product. There is no database or publication path.

`exploration.report` preserves claimant/activity/scope/unit/period, physical free
supply, eligibility, explicit limits, typed budget holders/rates, actuals and
posting references. `actual_before` is previous fulfilled demand; `actual` is
this invocation's incremental allocation; `unmet` is remaining demand after it.
Posting IDs include previous and new claim-linked postings and resolve against
the retained complete allocator batch. Unknown precedence/access/terms sets
`actual`, `unmet` and budget `available_after` to null. Known opening quantities
and previous actuals stay visible. The full evaluation carries missing-rule
reasons, all account totals/balances, holds, terms and original provenance.
Shared free supply/budget fields repeat for context and must never be summed
across claims. Different units/scopes/periods are not aggregate wealth or welfare.
These calculations imply no prices, employment rate, learning or service output.

[Research coverage](../../../../content/economy/README.md) accounts for every
pinned economy branch/leaf and source/system decision. Only generic goods/time
procedures have partial hypothetical support. Ownership law, currency mechanisms,
market/planning/gift behavior, prices, automation, wealth, redistribution,
inheritance and transitions remain unsupported. Production content is unchanged.

The real bounded DOM-01/02 counterpart now compiles use terms against actual staged
production/delivery and shares canonical dated work. See the
[paired host adapter](../provisioning/README.md#real-economy-counterpart-v1).
`conformance_catalog()` marks only this pair ready for conformance. Shared finite
claims and prior reservations are tested independently; no market, wage, wealth,
service-delivery or source-activation model follows from this disposition.

`governance.py` composes the actual DOM-03 ballot/authority/administration adapter
with DOM-02 allocation in a private host-only DOM-02/03 counterpart. Both stages
share identical canonical initial books and holders. Future claims are closed in
administration; administration claims are closed in economy. Explicit outcome
prerequisites restrict only affected-account access, preserving unknowns and
independent eligibility/funding/entitlements. The original request and actual
staged evidence remain separate. This hypothetical preview neither adopts a
policy nor publishes a book. See the [execution record](../../../../docs/roadmap/execution/WP-032-counterparts-economy-governance.md).

`adjudication.py` composes actual DOM-04 legal-case results and administrative
work with subsequent entitlement-constrained goods allocation (DOM-02/04).
Explicit prerequisites bind each goods claim to a case for its claimant, the
finite entitlement account and the binding's affected source/entitlement accounts.
Only an upheld result preserves existing terms. Other known outcomes restrict the
mapped claim; unknown cases withhold the complete candidate. Actual administration
and economic work share one staged book, with earlier/future claims closed in the
opposite phase. No ruling creates rights, rewrites history or enforces obligations.
Private host callbacks retain complete context/review bindings and opaque evidence.
See the [package record](../../../../docs/roadmap/execution/WP-032-counterparts-economy-adjudication.md).

The private `care` adapter validates actual DOM-05 beneficiary obligations and
canonical arrangement membership against the identical DOM-02 request. Care,
training, paid/unpaid work and participation share dated canonical time; goods
retain physical and access constraints. Both pure evaluations start from one
original book, preserving prior postings and holds once. Unknown population or
terms withholds the complete candidate; known unmet care remains explicit.
`care_counterpart` supplies reviewed context-bound opaque conformance tokens.
No care-quality, health, wage or demographic effect is inferred.

The host-only actual DOM-02/06 counterpart lives in `education.py` and
`education_counterpart.py`. Actual education staff/student/material commitments
and care/employment/goods share the identical finite dated economy book. Pure
recomputation retains prior use and holds once. Facility commitments remain in a
separate disjoint pool; neither pool implies synchronized teaching or learning.
Unknown prerequisites withhold the complete candidate, while known unmet inputs
stay visible. Opaque context tokens bind actual policy declarations/reviews,
request/world/units and runtime. See the literal economy/education fixture and
[package evidence](../../../../docs/roadmap/execution/WP-032-counterparts-economy-education.md).
