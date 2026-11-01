# Reviewed provider context bounds

The main process bounds serialized messages, tool definitions and response format
by UTF-8 bytes plus 1,024 tokens per message/tool/framing unit. These are capacity
bounds, not token counts or scientific quantities. Python owns cost arithmetic.
Unknown tokenizer families remain blocked.

The existing GPT byte-level BPE route is retained. WP-055 first added an exact receipt for `deepseek/deepseek-v3.2` with catalog tokenizer `DeepSeek`, for text/tools.
Media stays blocked on that route. Do not generalize this receipt to other models
solely because their catalog uses the same tokenizer family name.

Inspected 2026-11-01: official `deepseek-ai/DeepSeek-V3.2` tokenizer at
<https://huggingface.co/deepseek-ai/DeepSeek-V3.2/resolve/main/tokenizer.json>.
The observed 7,847,502-byte artifact has SHA-256
`cd050be35cae877f8f0aa847f45aa87e23835a56ca32b29b28545597852784e5`.
It declares BPE, no normalization transformations (empty Sequence), no subword
prefix/suffix, and a final ByteLevel pre-tokenizer with `add_prefix_space: false`.
Splits partition the input without expansion; byte-level symbols supply a base
representation and merges reduce token count. Added special tokens can consume
multiple characters as one token. Escaped serialized JSON overcounts ordinary
content; response schema and complete tool history are included. Framing is
reserved separately. A payload exceeding capacity still fails before dispatch.
This documents the inspected artifact; no claim that every remote provider runs
identical weights/tokenizer or supports untested modalities follows from it.

The current public OpenRouter catalog also includes structured pricing overrides.
Those are retained in raw metadata, but normalized flat pricing is unknown for
such rows. They cannot create an underestimated flat catalog estimate. Explicit
player exposure and Python's transactional spending gates remain required.

## DeepSeek V4.1 Flash 1017

At an earlier 2026-11-01 checkpoint, the user restricted live validation to
`deepseek/deepseek-v4.1-flash-1017`. The later authorization below supersedes that
model selection; this tokenizer inspection remains a historical exact-model receipt.
The production context receipt also admits this exact text/tools model after
inspection of its official tokenizer:
<https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017/resolve/main/tokenizer.json>.
Observed size: 6,367,257 bytes. SHA-256:
`c90dfa01249db1be4245780a052ede752e1361c612ac6d08e2bdada7d599476b`.
It likewise declares empty normalization, partition-only splitting, ByteLevel
pre-tokenization with no prefix-space addition, and BPE with no subword
prefix/suffix. UTF-8 byte/framing/schema bounds apply as documented above.
This does not grant a context receipt to unknown DeepSeek versions or image input.
The model advertises image input, but image-token accounting is not certified by
this text-only inspection. Audio/video are not advertised by this model.

Scheduled pricing remains unknown as a flat catalog estimate. The live runner
uses explicit USD 0.50 exposure and provider USD 2/M token price ceilings,
zero per-request fee, fewer than 200,000 conservatively bounded input tokens,
1,024 total output tokens and the original twelve-dispatch allocation at that historical checkpoint. Model fallbacks
are disabled. Routine compatibility requests explicitly disable default reasoning;
the separate reasoning check requests the advertised low effort.

## GLM 5.3 Flash

The user changed the authorized live model to exactly `z-ai/glm-5.3-flash` on
2026-11-01, with OpenRouter choosing the guardrail-allowed provider and no model
fallback. All existing dispatches remain charged against the same lifetime
allowance; changing model does not reset spending authority.

Inspected official tokenizer:
<https://huggingface.co/zai-org/GLM-5.3-Flash/resolve/main/tokenizer.json>.
Observed size 20,217,442 bytes; SHA-256
`19e773648cb4e65de8660ea6365e10acca112d42a854923df93db4a6f333a82d`.
It declares BPE with no normalizer, subword prefix/suffix or unknown token;
partition-only Split then ByteLevel without prefix space. Byte symbols provide
the base representation; merges/special tokens reduce content token count.
ByteLevel postprocessing does not expand token IDs. The existing conservative
serialized UTF-8 byte/framing bound therefore applies to this exact text/tools
model despite its nonspecific catalog tokenizer label `Other`. Other models
with that label remain blocked. Image/video token accounting is unvalidated.

The captured catalog declares mandatory reasoning and supports `low` effort.
The live runner uses low effort throughout, 1,024 output tokens and the existing
price/exposure limits. The streamed reasoning response also supplies the separate
reasoning inspection, sharing that inspection rather than duplicating paid dispatches
without omitting a capability check.

## Final allocation bound

The final GLM run uses fewer than 40,000 bounded input tokens, 1,024 total output
tokens, USD 2/M input/output ceilings and zero per-request fee: cost is strictly
below USD 0.082048, covered by USD 0.10 exposure. Nineteen earlier USD 0.50
reservations migrate as 95 USD 0.10 policy units; five final requests reach the
same USD 10 authorization. The final JSON response supplies both ordinary
generation and JSON-object inspections; stream/tool responses supply reasoning
inspection. No lifetime count or earlier reservation is reset. The receipt now
records 24 dispatches and 100 units; no further paid request is permitted.
