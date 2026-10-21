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
