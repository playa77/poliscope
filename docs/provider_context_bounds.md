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
