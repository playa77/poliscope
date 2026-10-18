# WP-011-ipc — Desktop IPC and passive resource boundary

Started 2026-10-18 on main `51b6764b881d977194c30e1ed8fc359caa2f58a3`
(merged PR #16). Owner Codex `/root`; controller requesting user; one sequential
agent in `/workspace/poliscope`, branch `codex/wp-011-ipc`. Route SV with separate
inspection; agent review deferred. Prerequisites: WP-011-shell at that merge,
WP-010 transport/history reader and protocol-1/schema-1 contracts already merged.

Scope/write reservation: desktop main security/IPC, preload's named API, renderer
text/source presentation, adversarial unit and packaged Electron checks, and
execution evidence. Keep four existing service methods; future service groups
require their own canonical contracts. No generic operation forwarding.

Acceptance: every handler rejects unauthorized windows, subframes, stale documents,
wrong arity and malformed/oversized inputs before side effects; returned errors
are bounded and contain no private paths. Main validates service replies. Production
renderer requests are limited to its packaged assets; permissions, subframes,
webviews, windows and navigation are denied. Development transport is loopback-only
and absent from packaged policy. Stored strings render as text, including hostile
HTML/Markdown/SVG/CSS. A controlled network sink receives no passive requests from
hostile resource references. Real Electron tests exercise unauthorized IPC and
recovery after rejected requests; Linux-only/sandbox harness limitations remain
explicit. Full future service groups, model execution and native release gates
remain separate. No G1 claim without its complete candidate-bound evidence.

## Separate inspection and validation

Inspected the four-channel registration and every caller, input, output and error
path separately from implementation. Requests require the current live owner,
main frame and exact active document, exact arity and at most 16 KiB of serialized
arguments before controller/dialog work. History inputs retain generated schema
validation and grants; results are bounded to 1 MiB and validated against generated
historical schemas in main, in addition to the reader's context/result binding.
Errors cross IPC as one constant bounded message, without process errors or paths.
No provider, filesystem, SQL, shell or arbitrary operation method is exposed.
The input limit applies after Electron deserialization; it is not a transport-level
memory allocation limit. Existing selected-history and reconnect behavior remains.

Inspected production request policy and embedded/meta plus response-header CSP:
only the exact main document and renderer-directory JS/CSS assets load; remote,
arbitrary local, image/media/font/frame/object/worker resources are denied. Session
permission checks/requests and downloads are denied. Window/frame navigation,
redirects, new windows and webviews are denied. Packaged mode discards any dev URL;
development allows only one validated HTTP loopback origin and its WS endpoint.
The current renderer treats retained strings as React text/JSON, with no HTML,
Markdown interpretation, automatic links or remote previews. Rich content and
explicit main-owned source-link/fetch methods need later service contracts.

Frozen npm/uv setup succeeded with unchanged locks using writable temporary
caches. Typecheck, generated contracts, content inventory, roadmap/baseline and
whitespace checks pass. Engine tests: 283 passing (including 24 subtests); unit
tests: 198 passing; roadmap unittest suite: 40 passing. Linux packaging passes.
The five new unit cases isolate same-owner wrong-frame and stale-document checks,
resource/dev allowlists, pre-side-effect argument rejection, safe output checks
and recovery. Both packaged Electron tests pass: selected-history smoke plus the
adversarial check. The latter sends actual valid IPC from another window and its
subframe, checks stale-document refusal and restoration, malformed and oversized
selection rejection before dialogs, and a reachable loopback sink with a positive
control. Image/media/poster/font/CSS import/background/SVG/embed/frame/script/fetch
and popup probes generate zero sink requests; injected event handlers do not run.
Saved hostile HTML/Markdown remains literal text. Navigation leaves the original
document and named API usable; reconnect succeeds after attacks. Playwright loses
its frame URL after Chromium cancels the navigation, so that final document and
UI interaction are inspected through Electron's main-owned testing API.

The intentionally unsafe probe window/preload exists only in the test's temporary
directory and ephemeral session; production preferences remain isolated/sandboxed
without Node integration. Xvfb was extracted under /tmp, with temporary writable
caches and network-enabled test execution. As in prior smoke coverage Electron
launches with --no-sandbox; this proves configured preferences and application
boundaries, not OS sandbox enforcement. Windows/macOS and native release security
remain untested. Candidate-bound engine/unit/desktop evidence is run and verified
with scripts/evidence.py; local ignored artifacts are not committed.

Outcome: **solo-validated; agent review deferred** for the complete bounded
WP-011-ipc child. No full WP-011 service inventory, production model execution or
G1/native-release acceptance is claimed. Reassess WP-006-numeric (merged
WP-005-world prerequisite) and WP-004-probe at the next boundary; retain all parent
acceptance and unavailable native-machine requirements.
