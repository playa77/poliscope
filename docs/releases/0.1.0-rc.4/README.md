# Poliscope 0.1.0 release candidate 4

Prepared 2026-11-08 as the corrective maintenance delivery
[WP-059](../../roadmap/execution/WP-059.md) on top of merged `0.1.0-rc.3`
(source `1f3aa72`, delivery PR #131 merge). The application still identifies
itself as **0.1.0**; the `rc.4` label identifies this handoff without changing
the application version. This is an unsigned educational prototype candidate.
No release, signing, upload to a release channel or merge is authorized by
preparation, and no native artifact has been built for this label yet; the
owner-run native workflow decides that separately.

## Corrections relative to rc.3

1. The rebuilt floating navigation rail hid its brand, every workspace control
   and the `role=status` engine element below the `lg` breakpoint (1024 CSS
   px): at the Windows runner's effective window width the shell fell out of
   reach and three packaged offline workflows (E2E-009/011/017) failed although
   the distribution installed and its engine probe passed. The shell now
   renders the same navigation and status in the content column whenever the
   rail is hidden, so exactly one navigation and one status element stay
   accessible at any window width, display scale or zoom level; wide-window
   rendering is unchanged.
2. `scripts/freeze_release.py` now covers the shipped `components/`, `lib/`
   and `components.json` sources introduced by the UI rebuild: the freeze
   fingerprint carries 686 inputs (was 665), so future candidates cannot drift
   there undetected.
3. The `0.1.0-rc.3` record gains its
   [artifacts.json](../0.1.0-rc.3/artifacts.json) for the built-at-`1f3aa72`
   run: Linux verified end to end; the Windows job's distribution was sound but
   its offline workflows tripped correction 1.

## What did not change

Engine, content, contracts, dependency locks and the numeric/runtime
identities are unchanged relative to rc.3, and desktop application code
outside the shell status/navigation strip is unchanged. The rc.3 record
carries this candidate's model, performance, provider, scientific and
owner-validation scope through the rc.2 and rc.1 lineage unchanged.

## Freezing and current receipt

[The current inventory](inventory.ci-history.json) freezes every product,
schema, content, lock, packaging input, WP-055 evidence and requirement source
by path, size and SHA-256 at this delivery's commit, now including the shipped
component sources. Verify the checkout against it with
`uv run --frozen python scripts/freeze_release.py --check`. A different label
uses `--label <candidate>` with a fresh release directory; receipts are never
overwritten or relabeled in place. The
[rc.3](../0.1.0-rc.3/README.md), [rc.2](../0.1.0-rc.2/README.md) and
[rc.1](../0.1.0-rc.1/README.md) receipts remain immutable. Scope, provenance
and the publication boundary follow
[native distribution](../../native_distribution.md); execution evidence and
change accounting live in the
[execution ledger](../../roadmap/execution/README.md) and
[WP-059](../../roadmap/execution/WP-059.md).
