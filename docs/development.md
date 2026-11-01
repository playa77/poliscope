# Development and validation

Use **Node 24.19.0**, **npm 11.9.0**, **Python 3.12.14** and **uv 0.12.23**.
`.nvmrc`, `.python-version`, `package-lock.json` and `uv.lock` pin the toolchain
and dependencies. Install uv using its official installer or
`pipx install uv==0.12.23`; no global Forge, pytest or PyInstaller is needed.
From a fresh clone's root:

```sh
npm ci
uv sync --frozen --python 3.12
npm run dev
```

Development targets Windows x64 and Linux x64. Use x64 Node/Python on Windows.
On Linux install normal Electron desktop dependencies (Debian/Ubuntu: GTK3, NSS,
ALSA, GBM and X11/Wayland libraries; e.g. `libgtk-3-0t64 libnss3 libasound2t64
libgbm1`). Use an active graphical session. Headless Linux additionally needs
Xvfb/xauth: `xvfb-run -a npm run test:desktop`. PyInstaller needs native binary
tools (Linux binutils/Windows runtime); engines cannot be cross-packaged.

Forge/Vite launches React and one managed Python process using the repository's
absolute `.venv` executable, without a shell. Main negotiates protocol 1 and owns
lifecycle, files, OS-protected keys and provider networking. Preload exposes named
validated calls. The renderer has no Node/filesystem/SQLite/provider access.
Python owns canonical quantities, models, shared accounts, transitions and storage.
Generated schemas/types in `contracts/` come from canonical Python contracts.

The engine provides world/design/history, timeline/experiment, exploration,
notes/targets, archive/report/recovery and bounded assistant-context services.
Read [contribution rules](model_contributions.md) before changing these contracts.
The current [release candidate](releases/0.1.0-rc.1/README.md) records actual
coverage and remaining scientific, performance, native and provider limits.

## Private development data

Use Electron's normal user-data directory or set `POLISCOPE_USER_DATA` to an
absolute **isolated test** directory. Select a separate synthetic civilization
folder. Do not point tests at personal stores. `.env.example` describes options;
there is no dotenv loader. Configure real optional keys through the app's protected
BYOK settings, never in source, fixtures, shell history or a database dump.
Packaged execution uses the bundled engine with no system-Python fallback.

## Checks

```sh
npm run content:validate
npm run contracts:check
npm run typecheck
uv run --frozen pytest
npm test
npm run test:desktop
```

Content checks validate the immutable release artifacts and attribution inventory;
contract checks reject regeneration/registration drift. Pytest covers engine,
roadmap and harness invariants; npm test covers desktop units and roadmap tests.
Packaged tests build the native engine and actual Electron app and exercise
main/preload/child/SQLite paths with isolated synthetic data. Provider responses
are mocked unless a separately authorized live command is explicitly invoked.
`npm run test:providers` runs the exact deterministic capability/privacy/spending
selection. It incurs no paid generation. The WP-055 USD 10 allocation is exhausted;
a release check must never reset it or start another paid dispatch.

Use affected suites during development. At the package boundary retain exact
candidate/report identity and relevant full regression evidence. To run the
candidate-bound harness, choose fresh output directories:

```sh
uv run --frozen python scripts/evidence.py engine --output artifacts/engine-new
uv run --frozen python scripts/evidence.py unit --output artifacts/unit-new
npm run package
uv run --frozen python scripts/evidence.py desktop --output artifacts/desktop-new
uv run --frozen python scripts/evidence.py verify --output artifacts/engine-new
```

On headless Linux prefix the desktop evidence command with `xvfb-run -a`.
The harness rejects stale candidates, reused output directories, changed reports,
zero tests, failures and skips. Only synthetic report data may be retained.
Exact milestone selection validation uses
`scripts/check_gate_evidence.py SELECTION DIR...`; targets must occur exactly once.
Separate production-service/model inspection is still required. Existing full and
affected WP-055 reports retain original identities; they are not a single new
identical-candidate run.

## Packaging and CI

`npm run package` builds the native PyInstaller directory and Forge application;
`npm run dist` also creates a checksummed per-user installer archive in `release/`.
Neither publishes. See [native distribution](native_distribution.md) for signing,
upgrades and rollback. Native end users need neither Python nor an AI account.
The normal Chromium sandbox remains enabled; explicit test-only `--no-sandbox`
flags are restricted to isolated cloud runners, never ordinary installations.

Validation CI uses frozen installs and a fail-closed aggregate `checks` job.
PR/merge candidates must contain current main. Main pushes run a bounded engine
smoke; manual/weekly and authoritative candidate runs retain full scope. The
manual native workflow builds and installs Windows/Linux candidates and runs
packaged workflows. Owner desktop/keychain/signing checks remain owner-run under
[platform scope](platform_scope.md); remote CI does not imply owner results.

A frozen release input change must fail
`uv run --frozen python scripts/freeze_release.py --check`. Review affected
behavior/evidence, then prepare a separately named inventory; retain prior receipts.
See [release handoff](releases/0.1.0-rc.1/handoff.md) for release authority and triage.
