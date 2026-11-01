# Reviewed provider context bounds

The main process bounds serialized messages, tool definitions and response format
by UTF-8 bytes plus 1,024 tokens per message/tool/framing unit. These are capacity
bounds, not token counts or scientific quantities. Python owns cost arithmetic.
Unknown tokenizer families remain blocked.

The existing GPT byte-level BPE route is retained. WP-055 additionally admits
only `deepseek/deepseek-v3.2` with catalog tokenizer `DeepSeek`, for text/tools.
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

On 2026-11-01 the user restricted all live validation to
`deepseek/deepseek-v4.1-flash-1017`. No other model is used by the live runner.
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
1,024 total output tokens and at most twelve durable dispatches. Model fallbacks
are disabled. Routine compatibility requests explicitly disable default reasoning;
the separate reasoning check requests the advertised low effort.
