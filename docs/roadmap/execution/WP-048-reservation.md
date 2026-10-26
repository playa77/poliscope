# WP-048-reservation — Required production ledger consumed by WP-045

Owner/controller: Codex /root, controlled by the requesting repository user.
Allocated with full WP-045 on fetched main `3c1f3d2`, branch
`codex/wp-045-generation`; sequential, no collaborators. SV with separate author
inspection; **solo-validated; agent review deferred**. Acceptance is integrated
with the WP-045 parent; this is not a separate partial delivery or merge checkpoint.
Full WP-048 remains subsequent work.

Dependencies: existing Decimal28/exact Fraction arithmetic, SQLite and native
engine packaging on fetched main, WP-043 metadata and WP-044 immutable request
bindings. Contract: spending v1 (Python canonical schema and generated TS).
Write scope: Python private SQLite ledger/host/DTOs, packaged launch selector,
main bounded subprocess client and dispatch gateway, independent invariant tests,
parent records. No keys or prompt payloads enter Python's spending service.

Deliverables: atomic durable turn/session/profile reservations, exact replay and
conflicting binding/exposure rejection, reserved-only amendment and no-send
release, uncertainty/completion/status operations and crash/restart persistence.
Each scope allowance is established once and cannot silently change on a later
dispatch. Explicit bounded USD exposure, currency, policy version and payload/
endpoint/profile/model/context/request binding accompany each grant. Quantum is
0.000001 USD, enforced through the shared numeric runtime and independently
exact integer/Fraction representation. SQLite FULL durability and BEGIN IMMEDIATE
serialize all scopes together. Main persists uncertainty before sending. Cancel,
key deletion, completion and lost acknowledgments do not imply charge release.

Validation: independent fixed-money arithmetic, each isolated scope, amendments,
replay/conflicts, restart and forbidden release, zero/unknown input rejection;
12 concurrent independent SQLite connections allow exactly two 0.04 grants under
0.10 allowances. Production main-to-Python host integration carries grants across
controller restart and blocks the third 0.04 request. Native packaged generation
uses the bundled host, and cancel/key revocation preserve exposure. See parent
receipt for final outcomes and candidate identity.

No actual-cost aggregation, late-usage reconciliation, configurable limit-reset
workflow or account-side hard limit is claimed. Completed/uncertain exposure
continues counting until full WP-048 supplies recorded reconciliation. A local
bounded-exposure choice cannot guarantee a provider will not charge more.
