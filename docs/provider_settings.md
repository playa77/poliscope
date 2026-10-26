# Provider settings and keys

Open **Assistant and provider settings** from the app or workspace navigation.
Create a profile with its explicit API base endpoint and optional model ID.
OpenRouter uses `https://openrouter.ai/api/v1`; a custom OpenAI-compatible endpoint
must use HTTPS, except for loopback services. URLs cannot contain credentials,
query parameters or fragments. Save endpoint changes before entering another key.
Changing the endpoint/provider type removes its previous key and cancels its tests.
Profiles and model/generation/routing/capability preferences survive restart;
capability declarations are unverified preferences, not discovered capabilities.
Unsupported preference handling and generation belong to subsequent packages.

The temporary password field clears on transfer to main, including failed
transfers. Keys are never returned. With Electron OS-backed safeStorage, main
writes only encrypted endpoint/profile-bound material under the app's separate
`providers/credential-<id>.bin` store. Nonsecret profiles contain an opaque key
reference in `providers/profiles.json`. The provider store is separate from Python civilization records and is excluded
from portable archives and reports, even if the sandbox folder also contains it. Do not put credentials in
profile names, model IDs or other nonsecret preferences.

When protection is unavailable, throws during availability checks, or Linux
selects `basic_text` (including an absent backend result), the UI reports **session-only**.
Keys live only in main memory and disappear when the app closes. Existing
protected blobs remain unavailable without OS protection; replace or remove them
explicitly. Encryption or disk-write failures report a save failure and do not
fall back to a plaintext file. A missing, corrupt or mismatched protected blob
cannot authorize a test. Refresh after a failed or stale save before retrying.

**Test saved key** sends one non-billable metadata GET: OpenRouter `/key`, or
OpenAI-compatible `/models`, relative to the saved base. It sends no civilization
state, prompt, private note, attachment or generation request. HTTP success means
the endpoint accepted this request; a public/custom metadata endpoint may not
validate authentication. No model access, account limits, semantic response
schema or actual generation capability is inferred. Full provider-specific
adapters and key-status metadata are WP-043.

Networking uses Electron `net` in a separate memory session with its system proxy
behavior. Explicit Bearer authorization is bound to the saved profile/endpoint.
Cookies and interactive auth are disabled. Every redirect is stopped, including
same-host redirects; configure the intended endpoint explicitly instead. No
renderer URL/method/header override or arbitrary fetch API exists. Bodies and
headers are discarded; only fixed status text reaches the UI. Tests have a 64 KiB
response bound, a 10-second deadline, no retry and at most eight concurrent
profile tests. Profile preference changes, replacement, removal and shutdown abort
related work; the service does not wait for an uncooperative transport to settle.
Shutdown allows at most 1.5 seconds for pending settings I/O. A killed write can
leave encrypted staging material, which the next startup discards by exact
application-owned filename before opening profiles.

Remove/delete clears active session and protected material and cancels requests.
No filesystem secure erasure is promised; old user backups, OS recovery and an
OS-account compromise are outside this protection. Neither tests nor deletion
alter simulation history. Paid generation, automatic retries, spending, context
sharing, streaming and discovery are not implemented by these settings.

Model discovery, cached search, provider capabilities and safe key-limit
inspection are described in [provider metadata](provider_metadata.md), including
current official schema evidence and the distinction from live generation.
