# Provisioning research coverage

`coverage-v1.json` is a standalone, data-only DOM-01 research inventory, validated
against canonical `ProvisioningCoverage` and the pinned WP-025 source inventory by
`npm run content:validate` and independent fixtures in
`tests/engine/test_provisioning_exploration.py`. The content validator explicitly
registers these two research files separately; unknown artifacts still fail. It is outside `release-v1` and does
not alter content activation, the existing imported original alternatives or
historical player commitments. Source MIT attribution and complete archived prose
remain in the immutable release described in [the content guide](../README.md).

Every branch, leaf and relevant decision has an entry. `static_available` on a
partial catalog row refers only to the explicitly described hypothetical generic
adapter behavior within settlement/region fixtures; it does not assert that the
source-sector model is implemented or scientifically supported. Empty supported
scopes explicitly mean no implementation for that effect. `documents` preserves
source document or amendment references, including source decision IDs where the
original ledger amends another decision. `option_refs` preserves all original
source alternatives; historical adoption is not a player default.

Every transition remains unavailable. Empirical review, source model activation,
real counterpart acceptance and full domain/static/application gates are open.
