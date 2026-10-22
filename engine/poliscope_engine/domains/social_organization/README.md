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
public IPC, a reviewed source model, a timeline or parent acceptance. Service/goods chains, actual
DOM-06/07/11 counterparts, health/kinship/belonging outcomes and demographic
transitions retain separate dependencies. No universal social quality is scored.

## Explicit care-time exploration

`exploration.interview/report/preview` retain the complete host arrangement and
offer two authored procedural choices: preserve the declared work queue, or move
care claims ahead of other work while preserving relative order within both
groups. No option is selected by default, and no source-maintenance decision
selects a care policy. This is a bounded time arrangement, not a membership edit.
Obligations, population, providers, institutions, paid/unpaid categories, requested
hours, access terms, holds, prior work and the allocation procedure stay fixed.
Care does not imply unpaid or employed status; paid work implies no wages.

Reports retain the actual care evaluator's beneficiary/provider and population
union alongside DOM-02 claim/account/holder budgets, units, period, prior and
additional actual, unmet work and postings. Employment, learning and case work
compete for the same time. Unknown procedures/access/population remain explicit.
Missing queues are not filled automatically. Malformed or foreign scopes fail.
Baseline identities bind the complete request, canonical world, units and runtime
versions; stale edits fail and all returned DTOs detach from the caller. The care
evaluator has no mechanism-registry input or source activation path.

`coverage.validate_coverage` reconciles standalone unactivated research content
against all 12 DOM-05 branch/leaf entries and 25 source-maintenance entries,
retaining pinned titles/documents/alternatives, availability and research gaps.
No kinship, child-rearing, health, demographic or belonging effects are inferred.
