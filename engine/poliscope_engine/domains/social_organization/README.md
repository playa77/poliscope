# Static care and arrangement interface v1

`evaluate_care(CareRequest, graph=..., units=...)` returns detached hypothetical
host evidence. It owns no state, people, capacity ledger, service stock or IO.
Canonical `household_arrangement`/`community_arrangement` entities identify
explicit household/community scope views. These are host-declared views, not
inferred household counts or geographic containment. Direct `cohort_membership`
relationships retain WP-007 partition/weight rules. A repeated canonical partition
is counted once in the selected union; disjoint shares must sum to at most one.
Missing population stays unknown. The selected population property must contain
nonnegative count quantities with population dimension and no denominator or
flow basis. No count or time is multiplied by the number of networks.

Each `CareObligation` links one arrangement's beneficiary to a canonical provider,
optional directly authorized institution, host obligation reference and exactly
one positive DOM-02 `care` claim. Providers may serve another cohort and need not
belong to the beneficiary's selected networks. The claim is the host-declared
time demand; no demographic coefficient or individual simulation creates demand.
Multiple beneficiaries require distinct claims; one hour cannot fulfill two
obligations by referencing the same claim. Every care claim must be mapped.
Institutional references certify neither legal duties nor enforceability.

The complete work batch shares one settlement/region and explicit dated cohort
budgets. Actual DOM-02 enforces access, terms, complete priority/all-or-nothing
procedure, finite balances, holds and prior fulfillment. Employment, unpaid work,
care, training and participation retain separate categories in one report.
Results identify beneficiary/provider, requested work, prior actual, additional
actual, remaining unmet work, unit/period and posting IDs. Unknown access or
procedure yields null actual/unmet and no complete work candidate. A known care
shortage remains a resolved calculation and does not erase a duty. Population
unknowns make the overall report unresolved while known work remains inspectable.

The synthetic oracle has ten people viewed in two networks, five provider hours,
four care hours, three employment hours and two training hours. Employment then
training leaves four care hours unmet. Care first fulfills four, leaving one for
employment. Four held care hours cannot be consumed by another activity. Reusing
the resulting batch spends no fulfilled work again. Actual DOM-04 fixtures use
the identical care/work batch and expose case-capacity loss when care is first.

Contracts are generated in `contracts/social-organization.*`; arithmetic card
`care-v1.json` is hypothetical and unactivated. This is a trusted host API, not
public IPC, a reviewed source model, a timeline or parent acceptance. Authored
arrangement alternatives, source-gap coverage, service/goods chains, actual
DOM-06/07/11 counterparts, health/kinship/belonging outcomes and demographic
transitions retain separate dependencies. No universal social quality is scored.
