# Resource, access and dependency forecast

2026-10-17; one agent under user control, no promised completion date. Scope is
68 planning parents (26 M, 42 L). `delivery-plan.json` names 178 candidate child
scopes; 82 have concrete early dependency edges. Remaining children are planning
scopes, cannot start with null prerequisites and require bounded acceptance/write
contracts before allocation. Do not count parents and children as separate effort.

## Integration path and ready queue

WP-002 layout, Python, desktop and commands execute sequentially under the
[WP-002 parent contract](WP-002.md). After its validation and merge, the next
eligible scope is **WP-003-harness**, followed by CI and wire work. Allocate it
with a new source SHA, fixed owner/controller, write scope and validation route. Verified dependencies or actual
reviewed merged boundary children authorize development. A null merge SHA means
no merged evidence exists; it must never be interpreted as a passed contract.

The integration path is layout → reproducible scaffolds → harness/wire →
store/transport/trusted reader → world/registry/numeric/accounts/evaluation →
preview/apply/headless fixtures → synchronized offline UI → G2. Early contract
children unblock consumers without waiving the parent packages' wider acceptance.
The graph explicitly keeps storage independent of its future world/apply consumer,
boundary storage independent of the reducer, and sharing/spend providers
independent of generation dispatch. `check_baseline.py` validates those invariants.

Once G1 boundaries are ready, schedule native feasibility probes and provider
metadata research alongside the integration path at package boundaries; with one
agent these are sequential allocations. Domain/source preparation enters after
pack contracts. Static domain counterparts integrate at G3, generic time at G4,
portability at G5, complete optional AI at G6, and hardening/native delivery at G7.
All L inventory packages are decomposed before execution; domain parents retain
static and transition acceptance, and counterpart checks are integration
dependencies rather than circular development-start dependencies.

## Capacity and review

Current duties available to Codex: TPM/TL/ENG/DESK implementation and mechanical
QA/specification inspection. No independent MODEL expert, accessibility participant,
native-machine operator or nonauthor reviewer has been verified as available.
Do not invent people or certify scientific/user studies from structural tests.
Required evidence is due at WP-026/052/054 and release audit, with the relevant
package owner recording actual expertise/access before claiming acceptance.

At each boundary record availability (one to three agents), controller contact,
ready prerequisites, reserved write scopes, actual dependencies, reviewer capacity,
validation route, exact candidate and handoff. Joining agents take only unstarted
compatible work; departing agents complete their assignment or preserve an explicit
blocked checkpoint. Existing owner/controller/collaborators/division/scope/route
remain unchanged. Same-count replacement follows the same rule. No common
milestone/team completion barrier is required. Isolate each concurrent checkout,
database and secret environment. No actual second agent is allocated here.

SV backlog: WP-001 baseline/requirements/decisions and parent inspection are
`solo-validated; agent review deferred`. A later nonauthor review is additional
evidence with its own start contract; session restart is not independent review.
Repository account/branch protections are not modified by staffing changes.

## Access prerequisites and lead-time risk

| Dependency | Current observation | Owner duty / next evidence | Effect on forecast |
|---|---|---|---|
| Git remote | Session pull matched base main SHA; unrelated working edits preserved | Every package start refreshes safely | Setup/reconciliation time measured, never reset/clean to refresh |
| Python tooling | Python 3.12.14 / uv 0.12.23 pinned with uv lock | WP-002 records managed and clean-checkout setup | Frozen setup/clean checkout remain G1 work |
| Node/desktop tooling | Node 24.19.0 and npm 11.9.0 pinned; desktop launch/package checks in WP-002 | WP-002-desktop records pinned dependencies and actual smoke evidence | Native libraries/downloads may add setup time; do not claim runnable app |
| CI/branch access | No CI workflow or remote approval rules changed | WP-003-ci checks actual repository capabilities and required candidate rules | Shared account cannot produce independent GitHub identities |
| Source/license | No corpus excerpt retrieved/copied | CONTENT-001 / WP-025-inventory | License/source lead time can block content distribution |
| Benchmarks | Workload/budgets fixed, no exact native machine selected | PERF-REF-001 / WP-019 and WP-051 | Missing machine blocks performance claim, not framework implementation |
| Native execution/signing | Four targets required, access unverified | NATIVE-001 / WP-004 and WP-054 | External runner/signing lead time may dominate release |
| Provider APIs/credentials | No paid test authorization; no credentials read | PROVIDER-001 / WP-043 and WP-050 | Current schema/access/credit are separate from mock implementation |
| Model/usability expertise | Not independently staffed | WP-026-activation / WP-052-usability / WP-055-trace-audit | External evidence and participant availability can block empirical claims |

## Measurement and update method

No duration prediction is inferred from package size or agent count. Retain a
boundary record with wall-clock start/end, active execution time, setup/context
restoration, validation/inspection, correction cycles, integration/reconciliation,
external/controller waiting and artifact identities. The first package supplies
only one observation and cannot support a reliable rate or delivery date. As
comparable completed samples accumulate, report median/range and dependency
critical path separately from external waiting. Never multiply a human-day guess
by agent count or reassign an active plan to improve a forecast.

WP-001 observation: bootstrap checks complete in under one second on this cloud
runtime; that is validation overhead for planning tooling, not application
throughput or a forecast for implementation packages. No reliable complete
active-time accounting exists for the earlier turn, so duration/rate is explicitly
unavailable rather than fabricated. Subsequent start records capture it from the
beginning. Ready-queue updates and allocations occur at every package completion.

WP-003 update (2026-10-18): harness/CI/integration implemented under SV; see
[record](WP-003.md). Hosted CI awaits PR execution. WP-005 contract work is next
after merge; WP-004 retains WP-011-shell prerequisite. Native access remains
unverified beyond Linux scaffold smoke. No measured delivery rate is available.
