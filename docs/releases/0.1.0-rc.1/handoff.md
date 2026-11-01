# Release authority, acceptance and support handoff

The repository owner controls release authorization. WP-056 prepares the candidate,
documentation and rollback path; it does not publish a GitHub release, upload a
signed installer, enable auto-update or merge its PR. App/schema/catalog/model/
protocol versions remain those tested by WP-055. Product/build input equality to
the native artifact commit is recorded separately from documentation/evidence
commit identities in [artifacts.json](artifacts.json).

## Acceptance and deferred review

| Area | Retained evidence / disposition | Responsible follow-up |
|---|---|---|
| Functional/numeric/history | WP-055 leaf, RT and G7 acceptance; original reports and affected source-impact review frozen in inventory | Codex `/root` author inspection; owner release decision |
| Model/scientific | Twelve-domain coverage review, hypothetical models, explicit unsupported effects; no independent scientific certification | Owner may commission domain experts; no prediction claim |
| Security/privacy | WP-053 audit and WP-055 attack/recovery, spending and live continuation evidence | Owner real keychain/proxy/signing tests; nonauthor security review deferred |
| Product/accessibility | Packaged keyboard/table/inquiry workflows; no independent learner study | Owner real desktop use; human usability review deferred |
| Performance | Owner-accepted prototype; annual target miss and final preview sampling remain disclosed | Optimization deferred by owner until packages/testing complete |
| Platforms | Windows/Linux CI build/install/offline tests, unsigned artifacts | Owner-run desktop integration under project-wide waiver; Mac deferred |

Validation route is **solo-validated; agent review deferred**. Author inspection
is not independent review. Deferred review risk includes defects outside synthetic
fixtures, empirical misinterpretation and native integration variation. No external
signoff is fabricated or made a new agent-delivery prerequisite. The owner should
retain these limitations in any eventual release announcement.

The dated live compatibility receipt is read-only evidence. Its USD 10 allocation
is exhausted and must remain exhausted across fresh workspaces. A new live run
needs explicit model, route/capability scope, dispatch/exposure bounds and new total
authorization. Existing keys/readiness do not authorize spending.

## Before authorizing public release

Review the exact inventory fingerprint and source commit, unsigned artifact hashes,
compatibility table, known limitations and owner-run results. Decide signing and
publisher identity separately; checksum equality alone is insufficient. If an input
changes, prepare a new candidate and rerun affected checks before authorization.
If the Actions artifacts expire, rebuild the frozen inputs, retain **new** artifact
hashes and run the native workflow; do not reuse old checksums or claim byte-for-byte
reproducibility. Record publication destination, exact files and explicit owner
approval. No command in this handoff performs publication.

## Recovery and rollback

1. Before installation, close the old app and retain its installation, receipt and
   a checked pre-upgrade database backup. Record which civilization folder is used.
2. Install the candidate into a new directory. Same-version installs need a fresh
   destination. Verify receipts, then exercise the offline inquiry/reopen check in
   the [owner guide](../../roadmap/execution/WP-055-owner-checks.md).
3. On failure, stop new writes and preserve the diagnostic and last confirmed head.
   Launch the previous installation and restore a compatible backup into a new
   folder. Never downgrade the newer database in place or delete the original.
4. Keep failed installation/store copies private for diagnosis. Delete only a
   selected installation/launcher when uninstalling; private stores and keys have
   separate deletion controls. See [recovery details](../../data_recovery.md).

## Support triage

Report OS/version/architecture, app/candidate/source identity, visible error,
actions, last confirmed revision and whether the issue reproduces with a fresh
synthetic folder. Include selected model/provider/date only for provider issues.
Do not attach keys, full environment, transcripts, personal saves or raw provider
payloads. Obtain a minimal redacted synthetic reproduction before sharing evidence.

Classify failures so model limits do not hide implementation defects:

- **Data loss, privacy leak or unsafe mutation:** stop affected writes/dispatches,
  preserve private evidence and escalate to the owner for a corrective package.
- **Application regression:** reproduce against the pinned candidate and expected
  result, add an independent regression and rerun affected gates.
- **Missing/unsupported model:** retain coverage/assumptions; do not fill a number
  with zero or invent a mechanism to dismiss the report.
- **External prerequisite:** record exact native dependency, signing/keychain or
  provider limitation and owner, without weakening sandbox/privacy/spending rules.
- **Usability/accessibility:** record the task, control and observed focus/status;
  preserve a keyboard/table route and track the concrete failed action.

There is no automatic paid retry, remote repair service or automatic redesign.
Corrective work uses a separate reviewed candidate and preserves the old release
inventory and accepted historical evidence.
