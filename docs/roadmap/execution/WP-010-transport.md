# WP-010-transport — Production stdio primitive

Started 2026-10-18 on main `3785021ae0c8032e80413d16c23aff81a18a034c`
(PR #13 merged). Owner Codex `/root`; controller requesting repository user;
one sequential agent, reserved checkout `/workspace/poliscope`, branch
`codex/wp-010-transport`. SV separate inspection; agent review deferred.
Dependencies: WP-002 at `d86aa12`, WP-005-wire at
`e0e18287cda3a45d52f22e98518ea6553134f580`. No dependencies added.

Full early transport child scope, per distributed delivery §4.1:
- Producer subpackage: Python bounded binary framing, protocol handshake, health,
  status/cancel unknown outcomes, graceful shutdown, stable safe errors.
- Consumer subpackage: main-process frame assembly, validation/correlation,
  pending limits/timeouts, progress routing, write backpressure, failure rejection,
  absolute no-shell child launch and bounded shutdown.
Both are allocated sequentially to the same owner against merged protocol-1
fixtures. Main's existing readiness view consumes the real handshake.

Acceptance: real Python child exchanges fragmented and batched frames; malformed,
invalid UTF-8, oversize, incompatible protocol, pre-handshake calls, unexpected
responses/exits and timeouts terminate or fail within bounds; safe diagnostics
never masquerade as results. Pending calls settle on transport failure. Runtime
shutdown exits, with termination escalation for unresponsive children.
World/evidence operations return explicit unavailable errors; no long-running
work exists, so status/cancel return unknown and no synthetic progress is emitted.
Progress reception is validated and routed by request ID. No new public renderer
RPC, mutations, retries or automatic reconnect. A failed session requires a fresh
child; future callers must reopen last confirmed state, never retry uncertain
writes. Trusted history, durable status/replay, storage-backed handlers and final
WP-010 lifecycle/parent/application gates retain their own providers and acceptance.

## Separate inspection and validation

Inspected byte bounds, partial-frame lifetime, response-kind/correlation checks,
fail-all behavior, queued writes, startup readiness and termination escalation.
Inspection found a handshake race: a valid handshake and malformed second frame
in one chunk could resolve negotiation before failure and later report ready.
Negotiation now checks session failure before readiness; an adversarial regression
covers the exact same-batch case. Close-without-EOF now also rejects callers.

Frames include the LF in the 1 MiB limit. Invalid/mismatched/uncorrelated producer
output ends the session; no raw diagnostic or response payload appears in errors.
Each call has a 10 second deadline. There are at most 64 pending calls; new calls
are refused while the writable stream needs drain. Callers may retry refused
backpressure only as an explicit new call; submitted calls are never replayed.
Malformed input ends the producer after one safe error; unavailable providers
return MODEL_UNAVAILABLE and leave the negotiated session usable. Shutdown sends
a request, sends TERM at 1.5 seconds and KILL at 2.5 seconds, with a 3.5 second
caller deadline. Transport failure independently escalates termination after one
second. Status and cancellation return unknown because this child starts no
long-running application work; durable status/replay remains historical-read work.

Frozen npm/uv setup succeeded with unchanged locks. Typecheck, generated-contract
drift, content inventory, roadmap/baseline and whitespace checks pass. The Python
suite passes 264 tests; the TypeScript suite passes 179 tests; roadmap unittest
runs 40 tests. Tests include actual Python/main transport integration, real
process crash, runtime cancellation, unknown status, malformed/fragmented/batched
frames, invalid UTF-8, oversize, protocol mismatch, wrong response kinds,
correlation, bounded pending/backpressure, timeouts, close/EOF and a real POSIX
child ignoring shutdown/TERM until KILL. All data is synthetic; no providers used.

The native PyInstaller engine builds and completes a protocol handshake. Vite
main/preload/renderer bundles build. Full Electron packaging was attempted twice;
the network-enabled retry failed downloading Electron's SHASUMS256.txt from GitHub
with HTTP 503. Packaged Electron launch is unrun; this environment also lacks
Xvfb. Native Windows behavior and hosted CI are unverified. This limitation
does not certify the final lifecycle or any application milestone.

Outcome: **solo-validated; agent review deferred**. Full allocated early transport
child is complete. WP-010-history-read is next for reassessment with its explicit
authorization/data-only contract. Storage-backed world handlers, long-running
operation progress/cancellation, durable replay, automatic state reattachment,
secure public IPC and final WP-010 acceptance remain their separately sequenced
providers. Candidate-bound engine/unit evidence is generated and verified under
`/tmp/poliscope-wp010-{engine,unit}`; these local reports are not hosted evidence.
