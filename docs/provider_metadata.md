# Provider catalog and capability metadata

Provider settings offer explicit catalog refresh and cached search, including open
model IDs and variants. Choosing a listed model edits preferences; save that
choice explicitly. Removed models remain readable in the cache, retain their
original observed time and cannot be selected from the catalog. A saved model ID
is never silently replaced. Search and pagination operate on retained metadata,
without sending a query, society data or generation to a provider.

Catalog refresh is a main-owned authenticated GET to the saved profile's
`/models`. OpenRouter has its own adapter. Its per-model provider inspection
uses `/models/{author}/{slug}/endpoints`; key-limit inspection uses `/key`.
OpenAI-compatible profiles use only `/models`; account and provider-endpoint
inspection remain explicitly unavailable. Generic model listings do not establish
text, tools, modality, context, pricing or routing support. Saved capability
preferences remain unverified preferences and cannot override discovered evidence.

Every catalog row carries its source and observation time. Input and output
modalities retain open strings. OpenRouter's `supported_parameters` determines
reported tool, structured-schema and reasoning support; `response_format` alone
does not establish JSON Schema support. Missing lists mean unknown. An explicit
list omitting a known parameter means unsupported. A modality is supported if
reported in either direction; absence means unsupported only when both direction
lists are present. This aggregate signal does not establish input/output task
suitability; the directional lists remain visible. Per-provider entries retain
separate parameter, context, completion-limit and pricing evidence, with unknown
modality information where it was not supplied. Routing is an OpenRouter adapter
capability, not a guarantee that a particular provider accepts a chosen route.

Prices retain the provider's decimal strings and unknown pricing keys. Prompt and
completion prices are reported USD per token; other pricing keys retain provider
semantics, including dynamic/negative sentinels. Unknown fields, modalities and
parameters remain in the complete model/endpoint JSON for forward compatibility.
Metadata is data displayed as escaped text; imported definitions are not executed.
No currency arithmetic, spending approval or generation suitability is inferred.
A future request builder must revalidate all selected controls and current model
and provider evidence before dispatch (WP-044 onward).

Caches live separately from civilization data, alongside app provider settings.
They bind profile ID, provider kind and canonical endpoint. Reads are offline and
labeled cached; observations older than 24 hours are labeled stale. Refresh never
runs automatically. Failed or unrecognized responses preserve the previous cache;
a successful complete listing marks absent IDs removed. Endpoint/type changes or
profile deletion invalidate the old cache. Corrupt/disposable cache data does not
prevent settings access. Key removal cancels requests but retains model metadata;
cached catalogs can reflect account-specific visibility. Cache files and filesystem
backups may retain that metadata. They are not part of portable civilization
archives, retained simulation evidence or the Python engine. Key-status data is
not cached. A null limit/remaining value means unknown or unlimited, never zero.
Provider numeric account values are reported metadata rather than exact local
accounting or a spending authorization.

Metadata transport uses Electron's isolated memory session and system proxy,
with cookies and interactive authentication disabled, every redirect blocked,
15-second deadlines and an 8 MiB response limit. No automatic retries occur.
Raw error bodies/headers and key labels/organization identifiers never reach UI
or cache. Credential echoes are rejected before raw model fields can be retained.
Authentication, credits, throttling, absent models, schema failures and network
errors have fixed actionable messages. Profile/key replacement, removal and
shutdown revoke requests, and late completions cannot publish against a changed
profile. Cache writes are atomic, exclusively staged and bounded to 8 MiB;
model history is bounded to 10,000 IDs and endpoint history to 32 model entries.
A capacity error preserves prior data instead of silently truncating a refresh.
Normalized model raw data is limited to 32 KiB of UTF-8 and endpoint raw data
to 128 KiB, keeping even Unicode-heavy responses within the reply budget. Partial
listings explicitly marked `has_more: true` reject without marking models removed.
The schema-validated named IPC reply is bounded to 2 MiB, with five-model pages.
No renderer URL, header, path or stored-credential read API exists.

## Official schema evidence

Retrieved 2026-10-26 from current official documentation (read-only; no real API
key, paid request or authenticated provider call). These HTML SHA-256 digests
identify the retrieved pages, including their documentation shell; synthetic
fixtures transcribe the relevant response shapes rather than copying SDK guesses.

| Source | API assumptions | Retrieved HTML SHA-256 |
| --- | --- | --- |
| [OpenRouter models](https://openrouter.ai/docs/api/api-reference/models/get-models) | GET `/api/v1/models`; `data` array, open `id`, architecture direction lists, `supported_parameters`, string pricing, context and top-provider completion limit | `f67633fb28d22eaf0b0e8fa8f40dd9535a6187a2591894db0bdd22c9e496ec1c` |
| [OpenRouter model endpoints](https://openrouter.ai/docs/api/api-reference/endpoints/list-all-endpoints-for-a-model) | GET `/api/v1/models/{author}/{slug}/endpoints`; `data.id`, `endpoints` with provider name, supported parameters, limits and pricing | `19d617f891c2120a888a0a559f4c60db1e6346b48e36de30dd077ffe4c2dc2ef` |
| [OpenRouter key status](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-key) | GET `/api/v1/key`; `data` with numeric/null limit, remaining and usage, optional free-tier boolean; other account fields excluded | `7d4711ef31bee4a8dc57ca1329b8f4ca3649018d1668ed8d2bf005be9badbee2` |
| [OpenAI list models](https://platform.openai.com/docs/api-reference/models/list) | GET `/v1/models`; `data` array with open model identity, created/owner and optional shutdown metadata; no execution capability schema | `c49e05cc19ee0302093ea77af6ac1d0d9ad0fe8cfe5b76c20cfa0ed10236e97e` |

The initially guessed OpenRouter `models/list-endpoints` documentation path
returned 404; the official models page linked the current endpoint URL above.
Fixtures are deliberately synthetic, including future models and fields.
Adapter/unit tests cover OpenRouter shapes, unknown/stale/removed IDs, account
redaction, malformed data and cache isolation. Packaged Electron loopback tests
cover actual compatible discovery, keyboard/search and cold offline inspection.
These tests are separate from live endpoint compatibility or model generation
outcomes. Real OpenRouter/OpenAI credentials, live generation, real protected
keychain and native Windows behavior remain untested in this package.
