# Assistant content, ownership and compatibility

WP-047 extends the main-owned assistant gateway. Content remains optional and is
never authoritative simulation evidence. The current bounded support matrix is
explicit; catalog visibility alone does not enable an adapter or tokenizer.

| Content | Input route | Output route | Bounds / rejection |
| --- | --- | --- | --- |
| Text | Ordinary text; explicitly selected UTF-8 plain-text local excerpts | Escaped React text and separately labelled visible reasoning | 8,192-character excerpts; original aggregate attachments at most 64 KiB / four files |
| Image | Inline PNG, low detail, on `openai/gpt-4o`, `openai/gpt-4o-2024-08-06`, `openai/gpt-4o-2024-11-20`, with current image capability metadata | Dedicated image generation is unavailable in the chat adapter; rejected before sharing | At most 512 × 512; no URL input, pixel decompression, thumbnail or inline rendering |
| Audio | Inline canonical PCM16 mono 16kHz WAV on `openai/gpt-4o-audio-preview`, `openai/gpt-4o-mini-audio-preview`, `openai/gpt-audio`, with current input capability metadata | Requested streamed WAV on the same named OpenAI audio models, bounded assembly, private artifact metadata and explicit save to a new file | PCM16 mono 16/24kHz output; at most 64 KiB; no playback, tool combination or nonstream output |
| Video | Typed MP4 selection is explicitly rejected before dispatch | Unavailable; unsolicited video fields invalidate the response | No certified decoder, adapter or token bound; use a player-authored local text description |
| File | Plain-text local excerpt extraction; originals are never sent by this route | Unavailable; unsolicited file fields invalidate the response | Provider-side PDF/text file processing is unavailable; no implicit OCR, PDF decompression, remote file ID, URL or filesystem access |

This is the full package's bounded adapter/capability matrix, **not** a claim that
all provider modalities or all models are supported. Unsupported combinations are
visible and fail closed. Native Windows, live paid providers, real keychains and
broader modality adapters remain untested/unavailable. No M6/G6 claim follows.
The unchanged GPT tokenizer requirement applies to every selected model/fallback.
Text accounting includes serialized bytes and framing reserves. Known GPT-4o
low-detail images add their documented 85-token image cost; known audio models
add one token per PCM sample, conservatively above their audio token rate. Every
fallback must independently qualify; renderer cannot supply an accounting receipt.
Unknown model families, high-detail images and other codecs are rejected.

## Provider schema verification

Public OpenRouter documentation was fetched on 2026-10-26 without credentials:
[image input](https://openrouter.ai/docs/guides/overview/multimodal/image-understanding),
[audio](https://openrouter.ai/docs/guides/overview/multimodal/audio),
[image generation](https://openrouter.ai/docs/guides/overview/multimodal/image-generation)
and [reasoning](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).
The current image-generation contract uses `/images` plus dedicated capability
metadata, not an inferred `chat/completions` image-output request. This gateway
therefore rejects image generation rather than treating a generic catalog flag as
permission to send an obsolete payload. Audio documentation requires streaming;
`modalities: ["text", "audio"]` and explicit `audio` voice/format are capability
checked. Every base64 audio chunk is decoded within a total bound; the assembled
WAV header is checked before a complete artifact can be retained or saved.
These reads establish schema inspection, not live provider integration evidence.

## Inclusion and ownership

Local selection is a session-owned copy. Each attachment records name, provenance,
original MIME/byte size/SHA-256, private/public classification, this-turn consent,
session retention and the extraction route. Excerpts inherit original
classification. The attachment manifest hash is part of immutable request context;
exact payload and inclusion metadata are shown before sharing. Selecting a file
does not send it: inclusion is explicit and review is disabled until consent or
clearing. After preparation the file selection and checkbox clear, so a new
request/model never silently inherits prior consent. File inputs are reset too.

Local UTF-8 extraction does not upload the original file; the reviewed excerpt
is the provider payload. Binary inputs use explicit provider processing only on
supported bounded paths. Attachments cannot combine with proposal tools, so
private original/excerpt derivatives cannot enter immutable simulation result or
proposal-origin records through this path. Grounded public context remains pinned
to the turn. Every continuation reuses the exact original inclusion and gets a
new payload review, disclosure-budget check and spending reservation.

Provider artifacts are always private session derivatives owned by the turn.
Only MIME/size/digest metadata is rendered. There is no HTML, Markdown, SVG,
media decoder, player, remote retrieval, blob URL or thumbnail path. The existing
production CSP and resource allowlist still deny image/media/font/frame/style URL
loads. Hostile prose is text, including nested SVG/CSS references. Explicit artifact
save goes through authorized assistant IPC, a main-owned native dialog and an
exclusive new-file write; no automatic open or overwrite occurs. Saved external
copies belong to the user and are outside session deletion.

Delete removes every active request in the same turn, its originals, excerpts,
response text, artifacts, opaque details, proposals and completed continuation
references; it revokes the shared disclosure capability and aborts in-flight work.
Late completion cannot restore it or dispatch a child. Shutdown clears the session
registry. No raw private content is written to provider metadata caches, simulation
history, civilization archives or reports. Such exports omit the entire assistant
session. Spending keeps only the existing durable identity/hashes/exposure, because
deleting private content cannot erase charges. JavaScript does not promise physical
memory zeroization; aborted operations release temporary references on completion.

## Opaque continuation and history

Visible reasoning/summary text is explicitly unverified and separate from facts.
Encrypted details stay out of that text. Bounded indexed stream fragments preserve
opaque strings and metadata without decoding or interpreting them. Changed types,
formats, IDs, unsafe keys, invalid values and oversized details invalidate output.
Only a successfully completed response can supply continuation details.

The main registry retains these details; renderer cannot supply arbitrary message
history or opaque authority. A tool continuation requires the original model's
reported identity, the same endpoint/profile revision, one selected model and
one explicitly pinned provider with fallbacks disabled. Opaque details occur in
the assistant history message, separately from content, and their exact serialized
bytes are included in the next payload review and disclosure accounting. Unknown
identity or incompatible routing is a new-request requirement. Model/profile
changes cannot silently translate history. Every deliberate new request starts
fresh history; local transcript persistence and generalized cross-model history
translation are unavailable. Opaque reasoning never becomes simulation state.
