# WP-055 candidate packages for owner testing

Both targets built, installed and passed all five packaged native smoke scenarios
in [workflow run 41312619335](https://github.com/playa77/poliscope/actions/runs/41312619335)
at source `ab3363651b322fa747f2d3b3fc22365aa2a69c4b`:

- [Windows x64 artifact](https://github.com/playa77/poliscope/actions/runs/41312619335/artifacts/13086261993)
- [Linux x64 artifact](https://github.com/playa77/poliscope/actions/runs/41312619335/artifacts/13085822906)

These are unsigned test candidates, not a published release. Download requires
GitHub access to the repository. The artifact names end in the exact source hash
above. Each contains a release archive, JSON identity receipt and SHA-256 file.
Remote CI validates packaging/install/offline behavior; real owner desktop,
keychain, proxy and signing outcomes are not inferred from those passes.

## Windows

1. Download and extract the Windows artifact. Locate its `release` directory.
2. In PowerShell there, run:
   `Get-FileHash .\Poliscope-0.1.0-win32-x64.zip -Algorithm SHA256`.
   Compare the result with `Poliscope-0.1.0-win32-x64.sha256`.
3. Extract that inner ZIP. In its `Poliscope-0.1.0-win32-x64` folder, run
   `.\install-windows.ps1` from PowerShell. The installer checks payload hashes
   and bundled known answers, then creates a per-user Start menu shortcut.
   It does not require administrator access, Python or Node. If a previous
   same-version installation exists, select a fresh absolute destination with
   `-Destination 'C:\Users\YOUR_NAME\Apps\Poliscope test 055'`.
4. Launch Poliscope from the shortcut and perform the short check below.

Respect the machine's existing PowerShell/organization policy. If it blocks the
installer, return that exact message; do not globally weaken execution policy.
The full checked payload remains available in `app/` for diagnosis.

## Linux

1. Download and extract the Linux artifact. Enter its `release` directory.
2. Run `sha256sum -c Poliscope-0.1.0-linux-x64.sha256`.
3. Run `tar -xzf Poliscope-0.1.0-linux-x64.tar.gz`, then
   `cd Poliscope-0.1.0-linux-x64` and `sh install-linux.sh`.
   Choose a new absolute directory as the first argument if the same-version
   destination already exists. Launch from the installed desktop entry.
4. Perform the short check below. Normal installation must use the ordinary
   Chromium sandbox; `--no-sandbox` is only for the isolated CI/cloud runner.

## Short real-machine check

Use a fresh test sandbox. Disconnect networking, create a civilization, preview
and cancel a change, then preview and Apply one. Inspect its account/trace,
fork and compare, export/import a portable archive, close and reopen. Confirm the
same confirmed revision and evidence remain. A stopped preview or rejected import
must not alter the confirmed state. No key is needed for these checks.

Return the target/OS version and any failure's exact visible message and action.
Codex owns diagnosis, fixes and evidence aggregation; the owner is not being
asked to debug the package, map requirements or configure a development toolchain.
See `docs/native_distribution.md` for the longer optional platform checklist.
