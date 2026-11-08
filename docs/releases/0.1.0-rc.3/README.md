# Poliscope 0.1.0 release candidate 3

Prepared 2026-11-08 as the UI rebuild delivery [WP-058](../../roadmap/execution/WP-058.md)
on top of merged `0.1.0-rc.2` (source `77602b0`, delivery PR #130 merge). The
application still identifies itself as **0.1.0**; the `rc.3` label identifies
this handoff without changing the application version. This is an unsigned
educational prototype candidate. No release, signing, upload to a release
channel or merge is authorized by preparation, and no native artifact has been
built for this label; the owner-run native workflow decides that separately.

## What changed relative to rc.2

1. The desktop presentation layer was rebuilt from zero: Tailwind v4 through
   `@tailwindcss/vite`, the ReUI registry on `radix-nova`, design tokens for the
   owner-settled violet canvas (`#F4EFFE → #BFA6E6`), "Lifted" elevation on
   `rgb(24 20 48)` and primary `#2207D4`, plus a floating navigation rail and a
   shared card, form and table component set. All eleven screens were rebuilt on
   it, one commit each.
2. The shell's DOM contracts were repaired where the earlier rewrite had dropped
   them (`.domain-grid`, `.inquiry-guide`, `.workspace-layout`, the session-only
   purpose field, the goals/policies/mechanisms line, and the skip link as first
   tab stop). Two desktop specs were updated with recorded reasons: the focus
   ring now follows the theme token, and the shell smoke opens the collapsed
   evidence reader and measures injected markup rather than the shell's icons.

## What did not change

Engine, contracts, content, dependency locks, packaging and the numeric, wire,
SQLite and calendar identities are unchanged relative to rc.2: the freeze input
list and fingerprint carry the same 665 paths. The [rc.2
record](../0.1.0-rc.2/README.md) therefore carries this candidate's model,
performance, provider, scientific and owner-validation scope unchanged; its
explicit limitation claims are not re-evaluated by this presentation change.
The optional assistant screen still renders through the transitional element
layer and is scheduled for its own delivery.

## Freezing and current receipt

[The current inventory](inventory.ci-history.json) freezes every product,
schema, content, lock, packaging input, WP-055 evidence and requirement source
by path, size and SHA-256 at this delivery's commit. Verify the checkout against
it with `uv run --frozen python scripts/freeze_release.py --check`. A different
label uses `--label <candidate>` with a fresh release directory; receipts are
never overwritten or relabeled in place. The [rc.2](../0.1.0-rc.2/README.md) and
[rc.1](../0.1.0-rc.1/README.md) receipts remain immutable. Scope, provenance and
the publication boundary follow [native distribution](../../native_distribution.md);
execution evidence and change accounting live in the [execution
ledger](../../roadmap/execution/README.md) and [WP-058](../../roadmap/execution/WP-058.md).
