# WP-011-shell — Selected historical evidence desktop

Started 2026-10-18 at main `b56f7cf` (merged PR #15). Owner Codex `/root`;
controller requesting user; one sequential agent, checkout `/workspace/poliscope`,
branch `codex/wp-011-shell`. Route SV, separate inspection; agent review deferred.
Prerequisites: WP-010-transport merged at `0b828b5` and WP-010-history-read merged
at `b56f7cf`. Contracts: runtime protocol 1, historical interface/schema 1.

Scope: main-owned selected-store authorization, mutually exclusive numerical and
historical child lifecycle, named bounded read-only shell methods, visible failure
and stored-history presentation with original identities and paginated evidence.
Write reservation: desktop shell/main/preload, engine shutdown, corresponding
unit/Electron tests and execution records. No dependencies or contracts changed.

Acceptance: a player selects a store through a main-owned dialog and supplies the
retained storage context/revision/result identity; cancellation preserves current
state. Main retains paths and grants, validates sender/document and bounded input
before dialogs/process work, and refuses concurrent selections/reads. Stop and
observe the numerical child's exit before launching any historical reader. Never
start a replacement after unconfirmed exit. Read supported evidence after engine
failure without cached results; show stored mode, model/runtime/revision, coverage,
time, limitations and errors without exposing paths or enabling mutations. Named
page reads remain bound to the granted result. Retry normal engine only after the
reader exits; quit waits for active bounded reads. One instance owns each data
directory. Test production process ordering and hostile inputs plus packaged UI
where available. Full WP-011 IPC/service surface, passive network adversarial
gates, WP-010 operation replay and native release support retain their acceptance.

## Separate inspection and validation

Inspected every new IPC handler's sender/main-frame/document and argument checks,
cloned schema-validated selection, main-only paths/grants, serialized operations,
read-only result binding, safe error strings, React text rendering and original
identity/time/coverage display. The numerical shutdown previously treated its
wall deadline and child error as successful termination. It now resolves only
for observed exit or absence of a spawned process; an unconfirmed deadline rejects
and blocks replacements. Reader callbacks wait for process completion; reconnect
and quit cannot overlap an active read. Cancellation retains current selection.

Frozen npm/uv installations succeeded with unchanged locks. Initial restricted
network/cache attempts failed; setup used the session network path and a writable
/tmp uv cache. Typecheck, generated contracts, content inventory, roadmap and
baseline checks pass. Engine suite: 283 tests plus 24 subtests; desktop unit suite:
193 tests; roadmap suite: 40 tests. The five new controller cases cover malformed
and path-bearing selections before dialogs, invalid pagination, cancellation,
busy/closed refusal, unconfirmed-exit refusal, and real-process cold reads after
normal startup or malformed handshake, followed by bound pages and reconnect.

Native Linux packaging succeeds. The packaged Playwright flow uses synthetic
SQLite, the bundled reader, a stub of the native file-picker result, actual form
submission, historical identity/coverage display, collection reads and reconnect.
It also checks secure renderer preferences and a second instance's refusal in
the same isolated data directory. No native picker interaction is automated.
The host lacked Xvfb and system package installation permission; Debian's Xvfb
was extracted under /tmp and used for the successful display-backed run. Tests
launch Electron with --no-sandbox as the existing cloud smoke harness requires;
this does not certify sandbox enforcement or the WP-011 adversarial gate.

Outcome: **solo-validated; agent review deferred**. This bounded shell child is
complete. The current primitive requires the player to know retained storage
context/revision/result IDs; browse/discovery and full creation/navigation belong
to later service/UI packages. No production simulation, automatic compatibility
recovery, operation replay, historical schema migration or application milestone
is claimed. Windows and paid providers were not exercised. Next scope is
WP-011-ipc, retaining full parent security/service acceptance.
