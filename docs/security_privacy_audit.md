# WP-053 threat, privacy and recovery audit

Scope: production source at the WP-053 candidate based on `2239711`, Windows x64
and Linux x64 product boundaries, tested here with cloud Linux and synthetic
worlds, credentials and private canaries. This is a separate author inspection
and executable regression pass: **solo-validated; agent review deferred**.
No independent penetration test, native OS certification, live provider privacy
claim, or cumulative G7/M7 result is implied. Exact results are in
[the validation receipt](roadmap/execution/WP-053-validation.json).

## Threat model and boundary inspection

Untrusted parties control imported archives, content definitions, source prose,
assistant replies/tool arguments, attachments and provider responses. They may
attempt forged renderer IPC, resource loads, prompt injection, oversized messages,
malformed streams, replay or sharing/spending races. The installed main process,
Python executable and registered mechanisms are trusted code. An attacker who
can replace the application, compromise the OS account or read process memory is
outside this boundary. No test uses real keys or paid external providers.

| Boundary and inspected production owners | Enforcement and exercised evidence |
| --- | --- |
| Renderer → preload → main (`security.ts`, `ipc.ts`, `desktop/preload/index.ts`) | Isolated sandbox, named preload methods, exact live owner/main-frame/document authorization before schema validation, bounded errors. `security.test.ts` and packaged `security.spec.ts` exercise foreign WebContents, subframes, stale documents and provider/assistant/recovery/import/world calls without opening a dialog. |
| Untrusted text → renderer (`desktop/renderer`, `security.ts`) | Source, Markdown and assistant prose render as React text; there is no HTML execution path. Production CSP denies connections, images/media/fonts/frames/objects/workers; local scripts/styles remain bounded to the packaged directory. Navigation, redirects, windows, webviews, downloads and permissions are denied. Packaged controlled sink probes test HTML, script, SVG, CSS and other passive resources with a positive reachability control. |
| Main → engine/readers (`engine.ts`, `workspace.ts`, `history.ts`, `recovery.ts`, `spending.ts`) | Absolute managed/bundled executables, no shell or PATH fallback, explicit environment allowlists, isolated Python, bounded request/output and deadlines. Diagnostics are drained or replaced with fixed errors. `engine.test.ts` probes an actual child's environment with credential, proxy and injection canaries; transport tests cover wrong protocol, invalid UTF-8, excess size, unexpected IDs, stream loss and backpressure. All five one-shot launch sites use the same inspected environment allowlist. |
| Content/import → Python (`archives.py`, `storage/store.py`, mechanisms/expressions) | No extraction or executable registration. ZIP directory preflight, entry/path/type/hash/JSON/reference/schema and decompression budgets precede transactional import. SQLite reader disables extensions and trusted schema, verifies schema identity and is query-only. Archive, pack, mechanism, expression and recovery tests reject unsafe definitions and preserve originals. |
| Main → provider (`providers.ts`, `provider-network.ts`, `provider-requests.ts`) | Credential bound to profile and canonical endpoint; remote plaintext/userinfo/query/encoded-path endpoints rejected. Fixed routes, manual redirects, no cookies/login or generation retries. Separate provider session. Bounded metadata/response parsing, credential-echo checks and sanitized failures keep raw credentials/error bodies out of renderer replies. Synthetic transport/controller tests inspect actual request JSON and headers. |
| Assistant → scoped facts/tools (`grounding.py`, `grounding.ts`, `sharing.ts`, `assistant.ts`) | Main-retained immutable state grant; public classifications propagate through source dependencies. Fixed allowlisted read/pure-preview tools return constant denial without probing private existence. Every continuation receives complete-payload review, cumulative disclosure accounting, revocation and a distinct durable spending reservation. No tool has commit, code, SQL, path, key or arbitrary fetch authority. Grounding and assistant suites exercise injected calls and revocation races. |
| User Apply → durable history (`revisions.py`, `boundaries.py`, `storage/store.py`) | Python alone writes SQLite. Validated candidates, branch/head checks and evidence/operation/head changes share one transaction. Completed exact bindings replay before current-head/runtime checks. Staged invariant failures, lost acknowledgments and crashes cannot expose an invalid boundary or duplicate mutation. |

The packaged combined attack case (`E2E-012.d` in
`assistant-content.spec.ts`) explicitly shares a malicious synthetic attachment
prompt, receives hostile provider markup and a private artifact, deletes the
turn, sends a fresh request without its private derivatives, then rejects a
traversal/executable archive. A controlled server records all requests; there are
no passive hits and the confirmed civilization catalogue remains unchanged.
The grounded packaged case separately attacks read-only tool disclosure, including
private-reference existence. Ordinary player Preview/Apply remains distinct from
provider output and tools.

## Findings and disposition

| Finding | Severity / owner | Fix and retest |
| --- | --- | --- |
| SEC-053-001: interrupted transcript save leaves an owned plaintext staging copy that subsequent turn deletion did not remove | Medium privacy / desktop transcript owner | `TranscriptStore` discards only its exact UUID-v4 `.tmp` staging names before reading or deleting snapshots. Writes flush the staged file before rename. A child process leaves a synthetic private canary then exits; cold listing, first-save recovery and deletion remove it while preserving the confirmed snapshot and unrelated draft. A real POSIX directory permission-loss regression preserves the prior snapshot, then permits deliberate retry after permissions are restored. `transcripts.test.ts`. |
| SEC-053-002: delayed interview focus steals the next domain button's keyboard activation under rapid navigation | Low reliability / workspace UI owner | Replace deferred animation-frame focus with a layout effect bound to the selection intent, including repeated same-domain opens. The original full-run failure and final affected keyboard/focus regression are retained in the receipt. No simulation or IPC authority changes. |

No other blocking finding was identified in the reviewed scope. Absence of a
finding is bounded by the inspected paths and exercised adversarial cases.

## Privacy canary inventory

| Data and possible copies | Projection / deletion evidence |
| --- | --- |
| Raw provider key and opaque encrypted blob | `providers`, `provider-metadata`, `provider-isolation`, `assistant` tests cover secure/session fallback, endpoint changes, cancellation/removal, error and chunked echo. Real archive export from a folder also holding provider storage contains neither raw key, encrypted bytes/base64, profile credential path nor provider-only metadata; SQLite also excludes the key/blob. |
| Private notes, rationale and historical copies | `test_workbench`, `test_comparison`, `test_archives`, `test_reports`, `test_recovery` use classified canaries, old alternatives, immutable evidence, tombstones, owned indexes and backup/restore. Ordinary archive/report omission applies across retained history and rehashes the projection. Explicit private export controls are independent. |
| Prompt/attachment originals, excerpts, tool results, opaque reasoning and artifacts | `assistant-content`, `grounding`, `assistant`, `transcripts` inspect complete outgoing payloads, constant denials, local session ownership and deletion. New threads do not inherit private derivatives or saved transcripts. Usage recovery stores charge bindings rather than original prompts. |
| Environment, diagnostics and telemetry | Actual-child environment canaries are absent; error replies never include selected private paths or uncontrolled stderr/provider text. Packaged sink receives only explicitly approved provider requests. Production source has no telemetry/crash-upload or renderer network client. The environment allowlist excludes provider keys, proxy credentials and Python/Node injection variables. |
| Interrupted transcript snapshots | SEC-053-001 regression covers abandoned active staging files, including no confirmed `transcripts.json`. Snapshot capacity fails rather than evicting private text silently. |

Deletion concerns active owned payloads and derivatives. User-exported artifacts,
reports, backups, filesystem snapshots, previously copied files and recoverable
storage blocks are independent copies; secure erasure is not promised. Failed or
interrupted explicit exports can leave staging files in the user-selected output
folder; these are user-controlled export copies, never silently imported or used
as provider context. Database backup restore cannot restore separately deleted
private stores. The audit does not assert that SQLite WAL/filesystem backups
securely erase old data.

## Fault matrix and recovery meaning

| Fault / production paths | Executable regression and expected outcome |
| --- | --- |
| Actual SQLite disk full and write denial during design Apply and timeline confirmation | New `test_fault_audit.py` uses `max_page_count` and `query_only`, checks actual `SQLITE_FULL`/`SQLITE_READONLY` codes, unchanged records/evidence/head and absent outcome; re-enabling writes permits exact retry. Cold replay after later head movement succeeds without an executable registry. No disk volume is filled; query-only models write revocation, not a claim about every filesystem/ACL. |
| Write failure/cancellation at each publication stage | Revision/boundary/archive suites inject every persistent write, verify rollback and compare independent confirmed connections; invalid staged invariants never publish. |
| Killed process during commit, migration or import; acknowledgment lost after commit | Revision, boundary, recovery and archive suites use real subprocess exits before/after commit. Cold reopen shows the old or fully confirmed new state, and exact retry yields one outcome. No automatic reset. |
| Child crash/protocol mismatch/stream corruption | Transport, engine, history and packaged offline/recovery tests reject pending calls, bound shutdown (including a SIGTERM-ignoring child), reconnect and read cold evidence without an old runtime. Unsupported schema/unsafe archive remains rejected, preserving its source. |
| Export/backup/report failure, disk/permission exceptions and preexisting destination | Archive/report/recovery tests preserve existing destination bytes and source history, remove ordinary failed staging, and reject overwrite. New packaged `fault-audit.spec.ts` exercises failed export and hostile import before killing main, then cold catalogue/history recovery. |
| Network disconnect, partial stream, malformed response, redirect/login and timeout | Network, stream, assistant and provider acceptance suites keep safe partial/incomplete/cancelled status, retain uncertain spending, never automatically retry generation and do not mutate civilization history. The expanded packaged assistant case destroys a real loopback HTTP socket after partial SSE output and verifies incomplete status, one dispatch and unchanged confirmed history. |
| Forced close and unsaved UI | Packaged offline failure case holds a real SQLite writer lock: Apply displays “Save unconfirmed”, retains preview and confirmed revision, then exact Retry Apply succeeds. Expanded packaged forced-main-exit case confirms catalogue and retained evidence survive a kill after rejected import/export. Close handling cancels provider work and bounds child termination. |

RT regression coverage is explicit: RT-01/02 retained/cold historical reads and
cache eviction (`test_revisions`, `test_boundaries`, `test_history`, `test_recovery`,
`test_archives`); RT-04 invalid staging/rollback; RT-05 retry after head advancement;
RT-07 historical classification/deletion/projection; RT-08 tool/result disclosure
and revocation (`grounding`); RT-09 passive sink/forged frames (`security`, combined
packaged attack); RT-10 concurrent 0.6 estimates under allowance 1 and late actuals
(`test_spending`, provider/assistant tests). Numerical RT-03/06/11/12/13 and the
case manifest RT-14 remain covered by the integrated regression suites; this
security package does not replace their owners or claim cumulative gate evidence.

Native ACLs, power loss, OS credential facilities and signing are owner-run;
provider compliance and paid live acceptance remain separately blocked in WP-050.
WP-055 owns the cumulative whole-product gate. WP-054 is next sequential work.
