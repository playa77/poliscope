# Runtime wire contract, protocol 1 / schema 1

Canonical source: `engine/poliscope_engine/contracts/__init__.py`. Generate with
`uv run --frozen python scripts/generate_contracts.py`; `npm run contracts:check`
fails on drift. TypeScript and tool inputs derive from the same JSON Schema.
Main's `wire.ts` validates inbound and outbound messages. WP-010 must integrate
these validators into live routing; today's bootstrap is a separate scaffold.

UTF-8 JSON Lines use LF, no CR, at most 1 MiB including LF. IDs are opaque,
nonempty bounded strings. Progress correlates request and operation IDs; null total
means unknown, never zero. Counts are bounded exact integers in both runtimes.
Diagnostics never belong on stdout. Error messages must be safe static descriptions,
not echoes of private payloads. Cancellation acceptance does not promise rollback
of an already committed result; status unknown does not prove no commit.

Only protocol 1 is supported. A handshake must offer 1; unsupported envelopes fail
with UNSUPPORTED_PROTOCOL before dispatch. Schema/application/protocol versions
are distinct; application changes alone do not change the wire version. Unknown
fields fail closed. Additive fields require coordinated schema regeneration and
consumer validation before use; breaking changes require a new negotiated protocol.
No legacy adapter or compatibility window exists yet (bootstrap is not protocol 0).
Future adapters need explicit fixtures, owners and retirement criteria.
Historical-read, replay, privacy and spending contracts are later WP-005 children.
Runtime status does not certify replay or computation compatibility.

`fixtures.json` is synthetic compatibility evidence, shared by Python and TypeScript.
It covers each runtime variant and rejects unknown versions/operations/fields and
malformed/oversized frames. Domain decimal/unknown/infeasible evaluation fixtures
belong to world/evidence children, not invented runtime results.

## World inspection, world schema 1

`world.inspect` adds a read-only projection contract. Canonical DTOs live in
`engine/poliscope_engine/contracts/world.py`; they generate through the same wire
schema, TypeScript types and tool-input schemas. This is a coordinated additive
contract extension: existing runtime fixtures remain accepted. Existing consumers
must be regenerated/validated before a world service sends these new variants.
There is no legacy-world adapter; no world service is implemented by this package.
WP-010 will dispatch runtime messages; later world services own these reads.

Every request binds data-store, civilization, branch and immutable revision IDs,
collection, explicit nullable cursor and a limit of 1–100. A response returns that
context, independent catalog/model/numeric-runtime identities, effective simulation
tick/calendar, and exactly one typed page. All pages cap items at 100; the 1 MiB
UTF-8 frame limit still applies to their combined size. Services must reduce the
page size to fit; a count cap alone does not guarantee a frame fits. `next_cursor`
is null only at the end. Cursor tokens are bounded opaque strings: the future
service must bind them to the complete authorized context/collection, reject
cross-context reuse, respect the requested limit, and never silently switch a
historical request to the current head. The DTO validator cannot prove that binding.

Scopes and entities are stable-ID projections. Typed, separately versioned edges
carry membership/aggregation semantics explicitly as weight, partition or
non-aggregating. They do not imply geographic containment, duplicate ownership,
or universal local precedence. Mechanism instances pin definition versions and
declare inheritance, typed parameter data and modeling status. Unknown mechanisms
may remain qualitative/unsupported; no code or expressions execute from DTOs.

Partition values keep conditions, design, assumptions, dynamic state, observations
and goals separate and carry scope, effective time and provenance references.
`quantity` preserves a bounded finite decimal spelling (including exponent strings)
with unit, time-basis and denominator references. `unknown` carries a reason and
has no numeric value; `0` remains a known quantity. Labels and references are
separate variants. This package checks structure, not Decimal representability,
unit existence/conversion, membership weight ranges, graph consistency, referenced
entity existence, or model validity. WP-006/007 and the producer services own those
checks. Source/assumption references become richer evidence objects in
WP-005-evidence. These projections do not authorize writes or establish evaluation
sufficiency; findings, unavailable-model/stale-revision and preview/apply contracts
remain their allocated children. Effective simulation time is not wall-clock time.

Shared `world:*` fixtures cover all page types, state partitions, entity/scope and
relationship kinds, inheritance/modeling/origin enums, exact quantities, unknown,
pagination and negative inputs. Python and TypeScript reject malformed types,
schemas, decimals and oversized lists/frames in both directions. Synthetic DTO
validity does not certify production world or simulation behavior.

## Evaluation evidence, evidence schema 1

Canonical `engine/poliscope_engine/contracts/evidence.py` adds `evidence.inspect`, `evaluation` summaries
and `evidence_page` results. This is a coordinated additive extension on protocol
1; regenerate consumers before dispatch. Existing runtime/world fixtures remain
supported; there is no legacy evidence adapter. No evaluation service is added.
The summary is a result projection for future producers, not a new evaluate or
preview command. `complete` describes evaluation completion, never an overall
civilization score or universal sufficiency verdict.

Evidence reads bind immutable revision and result IDs, collection, cursor and
limit (1–100). Pages repeat context, catalog/model/numeric identities, scope and
effective time. Five independent pages hold outputs, findings, sources, assumptions
and traces. The 100-item/100-reference caps and 1 MiB aggregate frame limit both
apply. Producers must paginate summary finding/trace references as well as pages;
summary references are bounded entry points, not a claim to include the closure.
Services own cursor/result authorization, request/response correlation, matching
scope/time/context, graph closure and keeping observation and coverage statuses
consistent. Structural validation cannot prove these relationships.

Coverage distinguishes known, partial, missing input, unmodeled, conflict, solver
failure and not applicable. Known observations contain quantities, labels or
references; unavailable observations require an explicit unknown reason, with no
numeric slot. Partial observations may carry qualified known or unknown values.
Quantity spelling, units, time basis and denominator are preserved. Coverage
explanations, covered/excluded scopes and missing inputs stay explicit. Incomplete,
infeasible and unresolved summaries remain successful results with findings;
`STALE_REVISION`, `MODEL_UNAVAILABLE` and `DATABASE_FAILURE` are operation errors.
Unknown evidence schemas fail `INVALID_MESSAGE`, as world schema errors do.

Findings distinguish physical shortage, selected-policy breach, institutional gap,
uncertainty and player-target observation, with rule/affected/provenance links.
Source references pin repository, document, revision, location, SHA-256 excerpt
digest, license and historical status with explicit supersession references.
Historical status (current/amended/superseded/disputed/unknown) describes document
lineage, never scientific validity or model coverage. Assumptions separately pin
scope, definition/version, origin, uncertainty form/definition and rationale.
Uncertainty references describe model data, not executable expressions or implied
probabilities. Trace nodes carry mechanism/version, scope/time, typed input/output
ports, child dependencies and source/assumption/trace references. Future producers
must independently validate calculations and referenced content/licenses.

All fixtures are synthetic. These contracts do not certify scientific evidence,
trace closure, retained historical readability, computation compatibility,
result hashing, storage, exports or privacy. Classified private payloads are not
source/assumption rationale: future privacy contracts/services own that boundary.

## Historical interface 1

`history.schema.json` and `history.ts` describe a separate, one-shot historical
interface. It negotiates no numerical protocol, loads no numerical models and
returns only `mode: stored_historical` evidence. `saved-evidence.schema.json`
validates the supported retained JSON envelope: `history_schema: 1`, one existing
`EvaluationSummary`, and five typed collections (`outputs`, `findings`, `sources`,
`assumptions`, `traces`), each at most 100 items. The entire stored envelope must
fit the storage 1 MiB UTF-8 limit. Store it via trusted Python `retain_evidence`
under the main-selected context ID and summary result ID. Generic old JSON is not
implicitly upgraded to this envelope. Reference closure, scientific validity and
private payload exclusion remain the producing repository's responsibilities.

A `HistoryRequest` contains `history_protocol: 1`, full revision context, result
ID, collection (`summary` or a collection above), integer offset 0–100 and limit
1–100. Pages return existing evidence DTOs; `next_cursor` is the decimal next
offset, or null. No cursor lookup, SQL, path, computation or mutation operation is
accepted over stdin. Main supplies an absolute database path, opaque storage
context ID, and trusted context/result grant at process launch. Every request and
returned result is bound to that grant. IDs do not themselves authorize a renderer.
A future shell must validate sender/document and selected store before using main's
primitive. There is no public renderer API or automatic engine-failure fallback yet.

The reader serves one LF-terminated UTF-8 JSON request, writes one response, then
exits. Requests/responses include LF in the 1 MiB bound. Invalid requests and
unsupported/unreadable stores return stable bounded error codes without raw data,
SQL, paths or diagnostics. Main caps both output streams, kills after 10 seconds,
permits one active reader per controller and rejects invalid/mismatched responses.
Only storage schema 1 is readable; foreign/altered/future schemas are preserved
with no migration. SQLite opens `mode=ro` and query-only, with extension loading
and trusted schema disabled, exact schema validation, a statement work budget and
bounded lengths. It reads committed WAL state; SQLite may maintain its normal
shared-memory sidecar. Main database and WAL contents are not rewritten.

The installed native engine executable's `--history-read` entry selects this
trusted reader before numerical runtime startup. In development main launches
isolated Python's `poliscope_engine.history`. The caller stops the numerical child
before launching its replacement; automatic lifecycle coordination is WP-010-
lifecycle/WP-011. Older-schema/archive recovery remains WP-041. This interface
proves safe structural readability, not reproduction of historical computations.

## Data-only pack format 1

`pack.schema.json` and `pack.ts` derive from `contracts/packs.py` separately from
the wire protocol. They describe bounded inline-text manifests, separate runtime
identities, pinned dependency digests, source/license archives, full alternatives,
typed parameters/measurements, scoped assumptions and versioned uncertainty
relationships. `packs.PackArchive` additionally verifies reference and digest
closure, namespace uniqueness and declared dependency consistency. Schema parsing
alone does not establish these semantic invariants or license/scientific validity.
No pack command or renderer import surface is added. See the pack service README
for the historical-read/execution boundary and supported import bounds.

## Mechanism declaration contract 1

`mechanism.schema.json` and `mechanism.ts` derive from
`engine/poliscope_engine/contracts/mechanisms.py`. The two synthetic domains in
`mechanism-fixtures.json` are validated during generation; generated
`mechanism-fixtures.ts` also checks them against TypeScript with `satisfies`.
They demonstrate matching quantity types and allocation-dependent outputs, without
registering, binding, executing or mutating state.

The contract declares stable/versioned IDs, domain/scopes/entity kinds, typed
ports, required/optional input behavior, explicit output dependencies, owned
dynamic-state proposals, static/transition implementation references,
preconditions, shared-account claims, policy composition, evidence/assumptions,
coverage limits, traces/diagnostics and validation fixtures/properties. All
fields are bounded and extra fields are forbidden. Required inputs and dependent
outputs propagate missing coverage; optional omission has no implicit value.
Claims distinguish requested amounts from actual allocation and require dependent
outputs to declare their allocation input. Shared account identity comes through
a required reference port; a claim never creates a separate account copy.

Canonical `MechanismDefinition` validation additionally checks local ID uniqueness,
reference closure, exact claim/allocation type metadata, declared state ownership
and transition support. JSON Schema and TypeScript alone do not perform these
cross-field checks. Callers must revalidate serialized data at trust boundaries;
frozen models contain mutable lists and are not a trusted registry or state store.

Implementation references are opaque versioned data. They cannot name code to
import, supply a shell command, embed a formula or authorize a graph operator.
Qualitative/unsupported drafts have no procedures. An unreviewed or hypothetical
numerical declaration may be inspected structurally; parsing never changes its
evidence status or authorizes activation. Text is displayed as untrusted data.

`WP-012-registry` must resolve units/time/denominator definitions against the
numeric/world registries; check source/assumption, domain ownership and scoped
cross-domain references; resolve trusted implementation IDs and enforce evidence
and fixture review before activation. It must check every proposal against the
registered state owner and submit changes to shared transactional reduction.
`WP-012-expressions` owns the registered operator allowlist, unit inference,
size/depth limits and evaluation. Dependency/SCC solving, actual allocation,
missing-coverage execution, policy resolution, persistence, pack attachment,
conformance integration and scientific validation remain downstream obligations.
The v1 declaration adds no IPC command and changes no pack or wire version.

`solver.schema.json` and `solver.ts` derive from canonical `ExecutionRequest` in
`contracts/solvers.py`: host-selected finite procedures and runtime claim mapping,
linear equations or bounded iteration, explicit tolerance/order/starting state,
and operation quota. Runtime validation additionally checks exact compiled SCC
membership, applicability, graph edge closure, typed account mappings and joint
funding contention. These are pure engine contracts with no new wire operation.

`evaluation.schema.json` and `evaluation.ts` derive from canonical
`EvaluationDesign` / `EvaluationResult` in `contracts/evaluation.py`. They cover
bounded static evaluation plans, explicit value/policy/precondition bindings,
realization evidence, typed coverage, trace edges, final accounts and canonical
identities. WorldGraph/host registry authority and fresh external-reference checks
remain runtime responsibilities. This adds no wire method or persistence format.

`measurement.schema.json` / `measurement.ts` define WP-017 versioned indicators,
post-evaluation goals, typed findings, condensed calculation traces, bounded trace
queries, complete local accepted-evidence closures and explicit public projections.
These host-service contracts do not add renderer IPC authority. Python owns all
measurement/threshold/target arithmetic; retained data does not require a live
model registry. See `engine/poliscope_engine/measurements/README.md` for boundaries.

## Revision services v1

`revision.schema.json` and `revision.ts` are generated from canonical Python
contracts for create, preview/apply, branch movement and bounded history queries.
Complete input snapshots, typed ordered changes, candidate/output differences,
archived alternatives and classified noncontent rationale references are explicit.
Apply carries the original request, digest and operation ID; consumers must replay
that exact request after uncertain replies. The host must authorize store and
civilization selection. These contracts do not add renderer IPC capabilities or
waive transport bounds. Production service and persistence/recovery semantics are
in `engine/poliscope_engine/revisions/README.md`.

## Workspace boundary v1

`workspace.schema.json` and `workspace.ts` define bounded creation options,
selected-store branch/domain/setup directories, state metadata and scope-bound
world pages. They are generated from Python `contracts/workspace.py`. Main owns
folder selection, child operations and context grants; the renderer supplies no
path, registry, executable, SQL, or arbitrary method. Every result binds the store,
civilization, branch, revision, model/time and selected scope. Named IPC grants
cover create/open/query only; preview/apply remain separate consumer work.

An unanswered design now permits an empty mechanism-instance collection. This
additive structural relaxation avoids injecting a synthetic civic mechanism to
create a sandbox. The starting workspace model explicitly has no numerical social
mechanisms; empty observations are not scientific evidence or a coverage claim.
Existing nonempty requests retain their validation and execution rules.

`interview.schema.json` and `interview.ts` are generated from Python interview v1.
They expose only context/scope/domain queries, bounded typed drafts, data-only
question/option projections, a digest-only Apply grant and confirmed/stale state.
They never grant arbitrary revision changes, operation IDs, paths or mechanisms.
Templates reuse the pack `Definition` contract; original synthetic wording and
complete cards are retained in the decision alternatives' design values. Imported
corpus registration remains a later content package.

Main owns the one pending candidate and mutation identity. Python reconstructs
changes from the immutable base and validates exact Decimal conditions, scope and
candidate identity before production revision Apply. Private rationale text stays
outside immutable history/evidence/operation bindings in `private-interviews/`
beside the selected store. Revisions hold only classified private references.

`provisioning-care.schema.json` and `provisioning-care.ts` describe the host-only
DOM-01/05 counterpart. Beneficiary-linked care and canonical population evidence
precede the real provisioning/economy chain over identical dated work inputs.
Unknown care/population withholds a complete book. No public IPC or write grant
is added; source activation and empirical model review remain separate.

`provisioning-education.schema.json` and `provisioning-education.ts` describe the
host-only DOM-01/06 counterpart. The education request must match the exact local
account/holder projection of the whole provisioning work book; all claims, prior
postings, holds, terms and subtotals match. Remote stocks are retained untouched.
Actual student/staff/supply commitments feed the chain once. Facility evidence
stays in its disjoint pool. Unknown service prerequisites withhold a candidate;
resolved blocked/ineligible services retain commitments without inferring teaching
or learning. Policy declarations and explicit reviews bind the context. These
contracts add no public execution, numerical IPC or publication permission.

`provisioning-health.schema.json` and `provisioning-health.ts` describe the private
host-only DOM-01/07 request/evaluation. Health input commitments feed the finite
provisioning chain on one dated canonical work/material book; facilities retain
their separate pool. Unknown prerequisites withhold the final batch. Descriptive
need/exposure/health-state references do not imply treatment or health change.
Opaque context-bound conformance ports grant no public numerical IPC or mutation.

## Provisioning/infrastructure prerequisite contract v1

`provisioning_infrastructure.py` generates `provisioning-infrastructure.schema.json`
and `.ts`. Every phase claim names one or more explicit facility-demand
prerequisites. Full dated slot commitments gate existing access without a
slot-to-mass conversion. The finite facility/path book stays disjoint from
provisioning material/time accounts. Reports retain original requests, actual
reach evidence, the restricted chain request and a complete candidate only when
all inputs resolve. These host-only DTOs add no numerical IPC or publication.

`provisioning-continuity.schema.json` / `.ts` declare the host-only v1 DOM-01/12
pair: finite continuity evidence, explicit full prerequisite mappings and the
provisioning/economy candidate. Separate response slots never become material
stock, throughput or proof of aid delivery. Opaque private host bindings require
explicit reviews; no wire operation or numerical IPC is added.

`provisioning-environment.schema.json` and `.ts` describe the host-only DOM-01/10
shared extraction/production and exact residual/loss sink allowance composition.
They grant no execution, source activation or public numerical IPC authority.

`economy-governance.schema.json` / `.ts` declare the private v1 DOM-02/03
single-decision prerequisite. Administration and economy share identical initial
books and holders with explicitly closed phase claims. The decision restricts
selected affected-account claims; approval creates no rights, stock, time or
policy adoption. Unknowns withhold the final batch. Original and staged requests,
ballots, policy conflicts, actual commitments and unmet claims remain inspectable.

`economy-adjudication.schema.json` and `economy-adjudication.ts` describe the
private host-only DOM-02/04 counterpart: actual case outcomes and finite shared
administration precede explicitly mapped entitlement-constrained goods claims.
These additive generated artifacts do not activate public numerical IPC, create
rights or publish account candidates. See the
[package record](../docs/roadmap/execution/WP-032-counterparts-economy-adjudication.md).

`economy-care.schema.json` and `economy-care.ts` describe the private host-only
DOM-02/05 pair. Actual care obligations and canonical membership validate the
identical finite economy request. Both pure services recompute from one original
book; prior work is retained once. Unknown population or economic terms withholds
the complete candidate. These contracts confer no public IPC or write authority.
See the [package record](../docs/roadmap/execution/WP-032-counterparts-economy-care.md).

`economy-education.schema.json` and `economy-education.ts` describe private
host-only DOM-02/06 prerequisite/economy evidence. They retain the exact shared
work request, actual education policy and independent facility reports, pure
economy recomputation and a complete candidate only when inputs resolve. These
contracts do not activate numerical IPC, source models or teaching/learning.

`economy-health.schema.json` and `economy-health.ts` describe private host-only
DOM-02/07 prerequisite/economy evidence. Actual patient/staff/supply commitments
share one finite economy request; facility commitments remain disjoint. Unknown
inputs withhold the complete candidate. These contracts confer no public IPC,
write authority, treatment or health-outcome inference. See the
[package record](../docs/roadmap/execution/WP-032-counterparts-economy-health.md).

`economy-infrastructure.schema.json` and `economy-infrastructure.ts` describe
private DOM-02/08 facility prerequisites. Every economic claim declares demand
IDs, including an empty list for explicit independence. Actual finite slots and
directed reach restrict existing access terms; unknowns withhold the complete
candidate. Slot and economy books remain disjoint and inspectable. No throughput,
operating resources, rights, lifecycle model or public IPC is inferred. See the
[package record](../docs/roadmap/execution/WP-032-counterparts-economy-infrastructure.md).

`governance-adjudication.schema.json` and `governance-adjudication.ts` describe the
private v1 DOM-03/04 request/evidence contract. Every case explicitly declares its
approval prerequisite. Actual decisions and case work share canonical finite time;
opaque reviewed host ports carry context-bound evidence digests. No wire handler,
policy adoption, rights creation, legal enforcement or scientific acceptance is
added. Unknown prerequisites withhold the complete candidate.


Private `governance-education.schema.json` and `.ts` are generated from the canonical DOM-03/06 request/evaluation. Explicit service approval dependence connects actual scoped decisions to finite student/staff/supply work and disjoint facility slots. These are host-only contracts; no public numerical IPC, adoption or learning effect is declared.

Private `governance-communication.schema.json` and `.ts` describe the canonical
DOM-03/09 request, original preflight, restricted evaluation and complete two-book
candidate. Every message declares approval dependence or independence. Original
access/disclosure/reach/delay remain authoritative, with finite message and
verification slots disjoint from administrative time. No public IPC, publication,
delivery, truth assessment or adoption is added. See the
[package record](../docs/roadmap/execution/WP-032-counterparts-governance-communication.md).

Private `governance-participation.schema.json` and `.ts` describe the canonical
DOM-03/11 request, original-term preflight, restricted evaluation and complete
two-book candidate. Every accommodation claim explicitly declares approval
dependence or independence. Voluntary participation, eligibility, access ceilings
and unresolved obligation conflicts remain authoritative. Accommodation slots
remain disjoint from administrative time; no public IPC, attendance, belief or
rights resolution is added. See the
[package record](../docs/roadmap/execution/WP-032-counterparts-governance-participation.md).

`governance-continuity.schema.json` and `governance-continuity.ts` are generated
private v1 decision/response-slot contracts. They preserve original-term preflight,
actual governance and continuity evidence, and detached administration/response
books. They do not add public numerical IPC, adoption or source activation.

## Private adjudication/care conformance

`adjudication-care.schema.json` and `adjudication-care.ts` derive from
`engine/poliscope_engine/contracts/adjudication_care.py`. Every existing care
obligation explicitly declares a case prerequisite or independence. The adapter
runs actual case work before care on one canonical dated account book. Upheld
preserves original terms; other known outcomes narrow only dependent new care.
The result retains original-term preflight, legal findings, canonical membership,
prior/additional/unmet care and a detached hypothetical candidate. Opaque reviewed
host ports bind the complete request/world/unit/runtime/policy context. This is
private conformance, with no public IPC, new duty, rights creation or enforcement.

`adjudication-education.schema.json` and `adjudication-education.ts` describe the
private hypothetical DOM-04/06 composition. Explicit case/independence mappings
retain original education preflight, staged adjudication and finite work/facility
evidence. These DTOs expose no public IPC method or publication authority.

`adjudication-health.schema.json` and `adjudication-health.ts` describe the
private hypothetical DOM-04/07 composition. Explicit legal dependence/independence
retains original health preflight and declared needs, exposures and health states.
Actual case work precedes patient/staff/supply commitments on one dated book;
facilities remain a disjoint finite pool. Legal bindings cover direct and required
entitlement accounts. These DTOs imply no treatment, rights or publication.

`adjudication-communication.schema.json` and `adjudication-communication.ts` are
private generated contracts for actual case-work/message prerequisite composition.
Complete case/independence mappings preserve finite disjoint administration and
channel/verification books, original disclosure/access and prior commitments.
Only explicit dependent new publication access is restricted by known non-upheld
findings; unknowns withhold the complete candidate. No message payload, delivery,
publication, rights creation, public IPC or parent acceptance is introduced.

`adjudication-participation.schema.json` and `.ts` are private v1 contracts for
actual DOM-04/11 case-work and voluntary accommodation prerequisites. Complete
claim mappings declare legal dependence or independence. Case/group/facility/
authority/obligation/account identities are checked before staging. Original
participation declarations remain evidence; legal findings only narrow dependent
new access. Disjoint finite books preserve prior use, holds and subtotals.
These contracts add no public IPC, attendance, rights creation or enforcement.

`adjudication-continuity.schema.json` and `.ts` are private v1 contracts for
actual DOM-04/12 case-work and declared continuity prerequisites. Complete
case/independence mappings bind group, institution, asset, obligations and affected
capacity. Original preflight preserves vulnerability, authority, disclosure and
conditional aid. Legal findings only narrow dependent new access. Finite disjoint
books retain prior work, response use, holds and subtotals. No public IPC, rescue,
hazard prediction, rights creation or enforcement is introduced.

`governance-infrastructure.schema.json` and `governance-infrastructure.ts` are
private generated DOM-03/08 contracts. Actual scoped decisions precede explicitly
dependent new facility/path access. Original topology, availability, limits and
unknowns remain visible; administration and facility/link commitments occupy
separate finite books. These contracts expose neither public IPC nor maintenance,
construction, lifecycle transitions or delivered services.

`care-education.schema.json` and `care-education.ts` are private v1 care/education
contracts. Identical dated work, holders, activities and explicit precedence feed
both actual evaluators from the original book; equal work evidence prevents a
second budget. Beneficiary obligations, canonical membership union and independent
education facility/qualification/policy prerequisites remain inspectable. Unknowns
withhold the complete candidate. Opaque reviewed ports expose bound evidence only;
no attendance, learning, demographic effects, public IPC or publication is implied.

`experiment.schema.json` and `experiment.ts` describe trusted-host v1 experiment
create/fork/advance/control, checkpoint, progress and replay DTOs. They grant no
IPC authority. Additive optional `ExperimentRecord.origin` binds retrospective
openings to a confirmed boundary while preserving existing v1 history identities.

`uncertainty.schema.json` / `uncertainty.ts` are generated from
`contracts.uncertainty`: explicit point/range/distribution declarations, stable
variable references, finite joint/conditional factor tables, exact probabilities,
revision-pinned reports, explicit sensitivity selections and the sole registered
linear-resource capacity method. These data contracts do not activate source
models, sample intervals or authorize saved-state mutations.

WP-039 adds `archive.schema.json` / `archive.ts`, generated from the canonical
portable manifest, projected revision/branch/experiment/private-payload records,
strict model snapshots and path-free desktop request/page contracts. The accepted
synthetic fixture is in `tests/fixtures/archives/accepted-v1`; format/privacy and
collision rules are documented in `engine/poliscope_engine/ARCHIVES.md`. Imported
projections are immutable historical collections, never executable registrations
or automatic editable migrations. Full accepted evidence remains distinct from
explicit evidence-reduced omissions and optional caches (excluded in v1).


WP-040 `report.schema.json` / `report.ts` define `ReportRequest` and the bounded
`ReportReply` receipt. Named `report:export` IPC carries format, archive identity,
optional scope and existing privacy options, never a renderer path or file bytes.
Main selects the destination through its save dialog and launches the bundled
`--report` data-only worker. CSV-v1 types/escaping and row semantics are specified
in `engine/poliscope_engine/REPORTS.md` and `tests/fixtures/reports/format-v1.json`.
Archive-v1 gains an optional `note_kind` for explicitly included private notes;
older readable histories with no subtype remain supported and labeled.
