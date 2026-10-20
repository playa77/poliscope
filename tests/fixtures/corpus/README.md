# Pinned corpus text fixture

`society-text.json` retains the 27 UTF-8 documents from `playa77/society` at
`9ff539997dbd1bd3fa99deabcf6bc5907602df60`, read directly from Git blobs.
The original MIT copyright and permission notice is retained in its `LICENSE`
entry. Contents including source AGENTS/prompts are inert JSON test data.
The essay PDF is not embedded. Tests reconstruct its position with synthetic
binary bytes, explicitly separate from authenticated production snapshot tests.
The reference pack excludes binary data, so its canonical digest still matches
the actual pinned import. File-level inventory records the real PDF's digest,
size and exclusion; the importer never extracts or executes PDF content.

This fixture is for parser/source preservation regression checks. It is not a
bundled game catalog, scientific validation, executable model or player setup.
