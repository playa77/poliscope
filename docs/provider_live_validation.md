# Bounded OpenRouter validation for WP-055

The requesting user authorized a maximum USD 10 on 2026-11-01, preferring
DeepSeek or GLM. The selected model is `deepseek/deepseek-v3.2`; the dated public
catalog fixture quotes USD 0.26/M input and 0.38/M output. This is compatibility
validation, not a benchmark or scientific model evaluation.

Run public, unbilled preflight:

```sh
DISPLAY=:99 node scripts/run_provider_live.mjs --preflight
```

For live checks, configure **OPENROUTER_API_KEY as a secret** bound to the same
runtime variable in the task's cloud-environment configuration. Apply it, then
signal readiness without putting the value in chat, commands, source, fixtures,
PRs or logs. A provider-side restricted test key with an account limit of USD 10
provides an additional independent cap. The ordinary unit and packaged suites do
not invoke this runner or require any key.

With that environment binding available:

```sh
POLISCOPE_LIVE_OPENROUTER=1 DISPLAY=:99 node scripts/run_provider_live.mjs
```

The runner builds a separate Electron-main test application, uses native Chromium
networking and actual production controllers/Python SQLite services, and creates
only an isolated synthetic world. The key is taken from the environment in main,
removed from that process's environment, never passed to Python or a renderer,
and held session-only. Raw provider errors, prompts/completions and account limits
are excluded from retained evidence. Only allowlisted usage and result identities
are recorded; temporary world/settings data is removed afterwards.

A filesystem lock excludes concurrent runners. A durable receipt counts at most
12 billable POSTs across restarts, with no automatic retries. Each uses the
production ledger's USD 0.50 exposure reservation and USD 10 session/profile
limits: maximum reserved exposure for the complete live allocation is USD 6.
Requests pin one model, 1,024 output tokens, USD 2/M prompt/completion price
ceilings and zero per-request fee. Context and serialized payload bounds stay
active. Cancellation/lost replies consume dispatch permission. Never delete the
receipt to renew permission or raise these ceilings without new authorization.
An interrupted run may retain a lock; inspect/stop the old process before explicit
recovery. The dispatch count must be retained.

The test sequence covers native/public catalog; authenticated key/catalog/account
metadata; ordinary and streamed generation; strict schema output; grounded tools
and separately approved continuation; explicit reasoning; usage observation;
stream cancellation and credential removal. Unsupported modalities are reported
as unsupported for this text-only model, not certified by other models' mocks.
Failures stop the sequence. Rate limits/provider unavailability remain actual
outcomes; do not turn them into silent skips or paid retries.

Evidence is under ignored `artifacts/wp-055-live/`. Before accepting a complete
run, inspect each outcome against the production contract and bind evidence to
its exact source and runtime identities. A public preflight pass is not paid/live
acceptance. The runner's explicit session-CA verifier is limited to OpenRouter,
checks the peer chain with OpenSSL against the injected CA, hostname, validity and
TLS server purpose, and preserves ordinary verification for every other host.
It does not disable TLS verification or certify a native user's proxy setup.
