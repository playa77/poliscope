# Content build and host review boundary

`build.py` deterministically transforms a pinned, validated corpus import plus
host-authored qualitative templates into immutable release artifacts. The normal
reader is bounded, rejects duplicate keys, symlinks, undeclared files, invalid
references, digests, source/license gaps, missing branch/template/inquiry coverage,
invalid conditions and unreviewed numerical activation. Reads return detached DTOs.
PyInstaller includes the exact data bundle; the packaged workspace and interview
services use the same reader as development.

`reviewed_registry` is a trusted-host API, not an IPC operation or pack hook. It
requires explicit hash approvals after review of operational definition, procedure,
denominator/time/scope, basis, uncertainty, invariants, validity limits and
unsupported extrapolation. Exact evidence and fixture bytes are part of the
approved record's closure. It produces the existing immutable registry's `Review`
records and cannot install implementations or bypass contextual activation.
No production source mechanism is approved by WP-026. Synthetic activation tests
establish the integration boundary only, not empirical or independent-agent review.
