# Scaffold development

Node **24.19.0**, npm **11.9.0**, Python **3.12.14**, uv **0.12.23**.
Use your Node version manager with `.nvmrc`; install the pinned uv release via
its documented installer or `pipx install uv==0.12.23`. No global Forge, Vite,
pytest or PyInstaller is needed. The root package/uv locks pin dependencies.
Run `npm ci`, then `uv sync --frozen --python 3.12` from the repository root.

| Path | Responsibility |
|---|---|
| desktop/main | Electron lifecycle, managed Python child, future protected integrations |
| desktop/preload | Named validated renderer bridge |
| desktop/renderer | React presentation only |
| engine/poliscope_engine | Python authority, with world/domains/simulation/storage/explanation namespaces |
| contracts | Canonical generated boundary artifacts (production generation pending WP-005) |
| content | Versioned content packs (pending WP-025) |
| tests | Roadmap, engine, desktop unit and actual Electron smoke tests |
| packaging | Native engine entry/build inputs |

`npm run dev` runs Forge/Vite and launches the absolute repository `.venv`
Python through main, with no shell. It needs a graphical desktop. Main owns one
child and closes its stdin on shutdown, with a bounded kill fallback. The child
only reports a bootstrap identity; it provides no application service yet.
The renderer reports actual startup status, with no automatic civic choices.

Private runtime files belong under Electron's OS user-data directory. Optional
`POLISCOPE_USER_DATA` selects an **absolute** isolated development/test location.
See `.env.example`; no dotenv loader or application key support is implemented.
Never put personal data in content/contracts/tests or Git. Packaged execution
uses only its native bundled engine, never a system Python fallback.

On Linux install GTK3, NSS, ALSA, GBM and the normal Chromium desktop libraries
(e.g. Debian `libgtk-3-0t64 libnss3 libasound2t64 libgbm1`) and use an active X11
or Wayland session. Headless checks need `xvfb` and `xauth`:
`xvfb-run -a npm run test:desktop`. On Windows use x64 Node/Python and allow the
Python executable to run; on macOS use matching arm64/x64 Node and Python.
PyInstaller needs the host's native binary tools (Linux binutils, macOS Xcode
command-line tools, Windows native runtime). Never cross-package an engine.

`npm run package` builds a one-directory PyInstaller engine then invokes Forge.
The native engine directory is copied outside ASAR as `resources/poliscope-engine`.
Outputs are unsigned **scaffold** applications, not playable release artifacts.
No makers, signing keys or notarization are configured; native feasibility and
release distribution remain WP-004/WP-054. Each OS/architecture must be verified
on its own runner. `npm run test:desktop` packages first and launches the actual
application with Playwright in a temporary user-data directory, without providers.
For a constrained development container, pass explicit Chromium flags with
`npm run dev -- -- --no-sandbox`; use the normal command on a native desktop.
Its explicit test-only Chromium `--no-sandbox` argument accommodates restricted
Linux containers; production launch retains Electron sandboxing.

`content:validate` and `contracts:check` validate the versioned inventories and
fail if unregistered files appear. Empty inventories are reported as empty;
these checks do not certify future packs or a wire schema generator. `npm test`
runs bootstrap desktop unit tests and the existing roadmap tests. Python tests
use `uv run --frozen pytest`. WP-003 adds the full evidence/CI harness; no
milestone gate selection is passed by the bootstrap checks alone.
