# Native distribution and owner validation

Build on **Windows x64 or Linux x64** using the pinned Node 24/npm and Python
3.12/uv environment from README. `npm ci`, `uv sync --frozen --python 3.12`, then
`npm run dist` produces a versioned archive, JSON receipt and SHA-256 file in
`release/`. A fresh output directory is required for each candidate. To use another
directory: `npm run package`, then
`uv run --frozen python scripts/distribution.py --output release/candidate-2`.
Cross-compilation and other architectures are rejected. No command publishes.

The Windows ZIP and Linux tarball contain `app/`, an installer, a payload checksum
list and an identity manifest. Both installers verify payload hashes, install into
a new per-user version directory, run the bundled engine self-test, then update a
user launcher. They require no administrator account, installed Python or Node.
These are script-based per-user installers, not MSI/deb system packages. Windows
needs its included PowerShell; Linux needs sh, coreutils and sed, plus Electron's
normal desktop shared libraries (GTK, NSS, X11/Wayland and audio support). Headless
test runners also need Xvfb. The owner validation baseline is Windows 11 x64 and
Ubuntu 24.04 x64. Native OS floors and other Linux distributions remain unverified.

On Windows, extract the ZIP and run `./install-windows.ps1` from PowerShell after
reviewing it. Organization execution policy may require administrator approval;
the installer does not bypass it. The default is
`%LOCALAPPDATA%/Programs/Poliscope/<version>`, with a Start menu shortcut. An optional
`-Destination` selects a new absolute path. On Linux, extract the tarball and run
`sh install-linux.sh`; default installation is
`~/.local/opt/poliscope/<version>` with a user desktop launcher. An absolute first
argument selects another directory. Launch normally from the shortcut. Do not use
`--no-sandbox` for ordinary installation; that flag is only for cloud test runners.
Some Linux systems require a configured unprivileged user-namespace sandbox or an
administrator-installed Chromium sandbox helper. Never make an unreviewed bundle
setuid to work around a launch failure.

Close Poliscope before upgrading. A destination that exists is never overwritten;
when installing another candidate with the same app version, choose a fresh path.
Old versions remain available for rollback by launching their executable directly.
The default user-data identity stays `Poliscope`; installers never migrate, copy,
reset or remove profiles, transcripts, keys or civilization stores. Use the app's
backup/export tools before opening saves with a newer version. Compatibility and
explicit migration checks still apply; rolling back an app does not downgrade a
database. Uninstall by deleting only the selected installation directory and its
launcher; user data and separately selected civilization folders remain. Deleting
keys/transcripts is a separate action within the app. A failed install may leave
its new directory for diagnosis; the prior launcher and data remain intact.

## Signing and reproducibility

Candidates are **unsigned by default** and must be labelled that way. Checksums
detect corruption; they do not establish publisher identity. Verify an artifact's
hash against a separately trusted receipt before running its installer.

Signing is opt-in after `npm run package`:
`uv run --frozen python scripts/distribution.py --sign`. On Windows install the
certificate and private key in the build account's Windows certificate store and
provide `signtool.exe` through PATH. Set `POLISCOPE_SIGN_THUMBPRINT` and
`POLISCOPE_TIMESTAMP_URL` (HTTPS). Each staged EXE/DLL/PYD is signed using SHA-256
and timestamped, then verified using Authenticode policy. Keys/PFX passwords are
never command arguments, artifact files or committed configuration. The original
unpacked app is not modified. On Linux set `POLISCOPE_GPG_IDENTITY` for an existing
externally managed GPG key; a detached ASCII signature is created and verified.
No automatic key import, login or signing-service configuration is attempted.
Sign the Windows installer script separately under your organization's execution
policy if required; its signing is not currently automated.

The receipt retains app version, commit and dirty-tree status, lock/content hashes,
every payload file hash/size/mode, executable architecture checks and the exact
bundled-runtime probe. The sidecar additionally records final archive size/hash
and detached signature hash where applicable. Timestamps, native toolchains,
PyInstaller bootloaders, compression and signing prevent a bit-for-bit reproducible
build claim. Dependency locks and identity records permit candidate comparison;
they do not prove independent reproducibility or native acceptance.

## Owner-run checklist

The manual **Native distribution candidates (owner-run)** Actions workflow builds
unsigned candidates on both target OSes, installs them and executes packaged
offline/recovery/archive/provider tests. It is not a release workflow or a required
agent delivery gate. Download and verify its retained receipts/artifacts and record
run URL, commit, OS/version, signing status, and results for each target.

1. On a machine without Python/Node on PATH, install to a path containing spaces.
   Run `resources/poliscope-engine/poliscope-engine[.exe] --self-test` from the app
   directory. Confirm status `passed`: fixed Decimal/HMAC answers, cold SQLite
   replay, retained evidence, idempotent retry, archive import/export.
2. Start the desktop offline. Create a synthetic settlement, preview/apply a
   change, fork/compare and replay a timeline; export/import an archive into a fresh
   folder. Cold reopen retains the exact confirmed revision and evidence. Check
   cancellation, rejected imports, backup/restore and engine reconnection.
3. Install a second candidate into a new directory. Confirm old installation,
   profiles, transcript and selected civilization stores remain intact. Test
   rollback using a compatible backup. Remove one installation; data must remain.
4. Inspect real OS key protection: Windows DPAPI; Linux secret-service/keyring
   backend where available. If unavailable or `basic_text`, the app must report
   session-only storage, lose the session key on restart and retain no plaintext
   key. Remove a synthetic key and confirm requests cancel. Existing deterministic
   provider tests cover redirects, cookies, endpoint binding and session fallback;
   they do not certify a real keychain. Paid/live tests remain separate WP-050 work.
5. Test supported system proxy behavior, disconnection/partial streams, bounded
   close and cancellation with a controlled endpoint. Confirm no credential is
   forwarded on redirects, no automatic paid retry, and civilization state remains
   independent. Inspect loaded native libraries/OS dependency failures and record
   actual signing/install outcomes. Do not infer Windows behavior from Linux.

Native outcomes and signing remain unverified until the owner records them under
the project-wide [native-validation waiver](platform_scope.md). Cumulative G7/M7
and public release authorization are separate from WP-054 implementation.
