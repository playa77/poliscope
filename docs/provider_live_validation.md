# Bounded OpenRouter validation

The 2026-11-01 WP-055 live allocation is complete. The latest authorized model is
`z-ai/glm-5.3-flash`, with OpenRouter choosing the provider under the user's existing
key guardrails and no model fallback. The final actual provider was `Z.AI`.
[Results and limits](roadmap/execution/WP-055-live-review.json) retain the successful
run and every prior failure. Successful tool continuation is verified; the
production configuration does not require manually selecting a provider.

The normal opt-in entrypoint is:

```sh
POLISCOPE_LIVE_OPENROUTER=1 DISPLAY=:99 node scripts/run_provider_live.mjs
```

Ensure an X display first. The published environment already delivers the key;
never request it in chat or write it into commands/files. The credential is read
only by Electron main, removed from its environment before Python is launched,
held session-only and removed before exit. The runner uses the actual production
controllers, Chromium transport, sharing gates and Python/SQLite spending service
with an isolated public synthetic world. No user civilization data is sent.

Public preflight is `DISPLAY=:99 node scripts/run_provider_live.mjs --preflight`.
Authenticated metadata and preparation can be inspected without a billable POST
using the opt-in command with `--authenticated-preflight`. Neither preflight
certifies the complete live scenario. The session CA verifier checks chain,
hostname, validity and server purpose; TLS verification is not disabled globally.

## Lifetime allocation

**The current allocation is exhausted. Do not send more paid requests under it.**
The durable `artifacts/wp-055-live/dispatches.json` receipt records 24 dispatches
and 100 policy units. The retained copy is in the live review. Never delete or
reset either receipt to renew allowance. Reconcile any newer local receipt with
the retained allocation before another authorized run.

A policy unit is USD 0.10 of worst-case exposure, separate from provider actual
charges and Python's authoritative application ledger. Migration preserves all
nineteen earlier USD 0.50 reservations as 95 units. The final five dispatches each
reserve one unit, reaching exactly USD 10 across both selected models and every
failed/lost/cancelled attempt. No model switch resets the counter.

The final requests pin 1,024 output tokens, text/tools only, fewer than 40,000
conservatively bounded input tokens, USD 2/M prompt/completion ceilings and zero
per-request fee. Their maximum cost is strictly below
`(40000 + 1024) * 2 / 1000000 = USD 0.082048`, covered by USD 0.10. Python checked
the bound. The filesystem lock and serialized fsynced reservations prevent
concurrent overspend. Malformed receipts fail closed. There is no automatic
paid retry or alternate model/provider selection.

## Coverage and evidence

The final run passes authenticated metadata, nonstream and streamed generation,
actual generation-cost reconciliation, JSON-object output, a real grounded tool
call, separately approved completed continuation, low reasoning controls,
cancellation and key removal. Shared responses supply the JSON/generation and
stream/reasoning inspections without duplicate paid requests.

The authenticated route advertises JSON-object support but no strict JSON Schema
support. The runner verifies strict-schema rejection before dispatch and validates
the returned JSON object separately. Tool calling uses advertised `auto` mode.
Unsigned standardized reasoning text can continue on the same selected model
without provider pinning; encrypted/signed/provider-specific details remain
subject to affinity checks. No selected control is silently dropped.

Parallel fragmentation, private-context canaries, concurrent spending, encrypted
history, attachments and uninduced credit/rate/redirect failures have deterministic
integration coverage. No live image/video/audio, native keychain, remote privacy
promise or provider account hard-cap certification is implied. Visible reasoning
was absent in the final run; earlier real tool usage reported reasoning tokens.

Redacted workflow evidence stays under `artifacts/wp-055-live/`; its aggregate
JUnit and source manifest are under `check/`. The final successful manifest was
verified before subsequent test/documentation-only edits. Compressed reports,
original source fingerprints and dated review are retained under
`docs/roadmap/execution/evidence/WP-055/`. No prompts/completions, keys, raw provider
errors or account limits enter those records. Historical failures are preserved;
none is relabeled as an initial pass.
