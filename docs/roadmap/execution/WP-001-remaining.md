# WP-001 remaining children — start contracts

Recorded before execution on 2026-10-17, continuing the parent assignment.

Both WP-001-requirements and WP-001-decisions retain Codex `/root` as owner and
the requesting user as controller (chat contact). No collaborators; one agent
implements and performs a separate inspection. Validation route is SV with
`solo-validated; agent review deferred`; no independent or human approval is
implied. Base is `4b9cac6fd994491db92518fccebf4e9142b42e03`; upstream
`origin/main` was pulled at this session's start and matches that base. Existing
baseline-child edits are retained. Application contracts do not yet exist.

## WP-001-requirements

Prerequisite: baseline child and its 13 passing bootstrap tests. Write reservation:
`docs/roadmap/execution/requirements.json`, `packages.json`, `delivery-plan.json`,
`scripts/roadmap_sources.py`, validation extensions in `scripts/check_roadmap.py`,
and `tests/roadmap/`. Capabilities: TPM/TL plus specification and verification
inspection. Inputs: complete D/T revision 0.3 and all 68 planning packages.

Deliver stable individual clause IDs, exact source locations/digests, delivering
child, verification owner, first gate, positive/negative oracle and honest
evidence state. Preserve all 34 top-level sections. Include explicit exceptions
for examples and historical context. Inventory capabilities, prerequisites and
acceptance for all 68 parents. Reject missing/duplicate clauses, unknown owners,
missing fields, source drift and invalid early dependency cycles. Stable IDs are
maintained through explicit amendments; regeneration cannot erase requirements.

## WP-001-decisions

Prerequisite: requirements child validated locally in this parent change set.
Write reservation: execution decisions, release inventory, benchmark definition,
resource/access forecast, RT regression register, workflow checks/tests and parent
handoff/status notes. Capabilities: TPM/TL with PRODUCT/MODEL/QA inspection.

Deliver DEC-01–12 resolutions or named blocking decision records, measurable
DEC-04/06 scope, a concrete acyclic early production-child plan, RT-01–14
regression ownership, allocation/handoff procedure and all six capacity-change
dry runs including stable active assignments and interruption/replacement.
Dependencies on the full consuming parent must fail validation. No merged child
SHA exists yet; future consumers must remain blocked until actual merge evidence
is recorded. Local validation of planning contracts does not waive that rule.

## Shared acceptance route

Run the bootstrap manifest checker and unittest discovery; mutate manifests to
prove missing leaves, missing gates, unknown dependencies and allocation changes
fail. Inspect oracles and first gates separately from their generation, with
special attention to M2 historical reading, M3 UI and M6 provider-only behavior.
Check local documentation links and `git diff --check`. Record actual counts,
source/tool identities, limitations and parent acceptance, keeping all application
outcomes unrun. The parent is complete only when every WP-001 acceptance item has
evidence or an explicitly permitted named decision blocker.
