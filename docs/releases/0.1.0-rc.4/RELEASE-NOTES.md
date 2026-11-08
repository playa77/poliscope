# Poliscope 0.1.0-rc.4 — release notes

Summary: the third iteration of the rebuilt desktop presentation layer, with
the shell's engine status and workspace navigation made reachable at every
window width, display scale and zoom level, plus completed release-freeze
coverage and record corrections for the partially-invalid `0.1.0-rc.3` build.
The application remains an unsigned, local-first educational prototype; it
still identifies as **0.1.0** and the `rc.4` label only identifies this
handoff.

## Fixed relative to rc.3

1. Shell reachability: the rebuilt floating navigation rail previously hid its
   brand, all workspace navigation and the `role=status` engine element below
   the 1024 CSS px breakpoint. On Windows CI's effective window width the
   engine status appeared as absent (packaged offline workflows E2E-009/011/017
   failed) and small or high-scaled windows lost navigation entirely. The same
   navigation and status now render in the content column whenever the rail is
   hidden, so exactly one navigation and one status element stay accessible at
   any width or zoom; wide-window rendering is unchanged.
2. Release-freeze coverage: the shipped `components/`, `lib/` and
   `components.json` sources introduced by the UI rebuild were outside the
   freeze whitelist and could drift undetected. The freeze now carries 686
   inputs (previously 665) and verifies the checkout with
   `freeze_release.py --check`.
3. Records: `0.1.0-rc.3` now carries its built-candidate record
   (`artifacts.json`) — Linux verified end to end, Windows distribution sound
   but its offline workflows invalidated by item 1.

## Packages (unsigned, source `17fce27`)

| Target | Name | SHA-256 | Bytes |
| --- | --- | --- | --- |
| Linux x64 | `Poliscope-0.1.0-linux-x64.tar.gz` | `c6610e62006a31dc490b78d3b2a2d0ad92a823f10c19de26dc3a3ecc36a17576` | 155 175 593 |
| Windows x64 | `Poliscope-0.1.0-win32-x64.zip` | `2ac5b591ed2bd99711583e03191d4254d4aeea54acb5cea0335503d707b97f08` | 175 329 336 |

Both install per-user with no administrator account, bundled Python engine
(no Node or Python needed) and have their payload verified by the installer;
the engine self-test reports `passed`. Linux default
`~/.local/opt/poliscope/<version>`; Windows default
`%LOCALAPPDATA%/Programs/Poliscope/<version>`. See
[native distribution](../../native_distribution.md) for the exact steps.

## Validation

- Owner-run native workflow
  [run 42509885922](https://github.com/playa77/poliscope/actions/runs/42509885922):
  Linux and Windows jobs both **success**, including installer and five
  packaged offline workflows on both OSes; wrapper digests verified against
  GitHub artifact metadata.
- Locally on the packaged binaries: narrow (1000×760) reruns of the three
  previously failing CI specs pass; wide (1280×900) twelve shell-sensitive
  packaged specs pass; `tsc --noEmit`, the vitest suite and the roadmap suites
  (67 tests including the freeze receipt) pass.

## Known limits

- Real desktop integration (sandbox remedies, keychain, proxy, signing,
  second-candidate rollback) remains owner-run and unverified under the
  project-wide waiver; the artifacts are unsigned, so checksums do not
  establish publisher identity.
- Engine, content, contracts, dependency locks and the numeric/runtime
  identities are unchanged relative to rc.3; the optional assistant screen
  still renders through the transitional layer and is scheduled separately.
- The model/scientific scope, performance dispositions and provider limits of
  the rc.1 lineage remain in force (see the rc.2/rc.1 records); nothing here
  is a scientific validity claim.

## Upgrade and rollback

Install into a fresh version directory (the installers do this by default);
close the old instance first and keep its installation, receipts and a
checked pre-upgrade database backup. On failure, stop new writes and relaunch
the previous installation; never downgrade a newer database in place. Full
steps and support-triage columns live in [the rc.1 handoff](../0.1.0-rc.1/handoff.md).
