# Retained inquiry reports and typed CSV (v1)

Python exports a validated WP-039 privacy projection of the selected store, or
one imported collection selected by its digest. No evaluator, PRNG or provider
runs. There is no AI prose generator in this package. Imported missing runtimes
remain inspectable; absent/reduced evidence is labeled, never regenerated.

Markdown separates player questions/targets, optional classified
inquiry/expectation/observation notes, original approved choices/alternatives,
inputs/policies, retained calculation findings, assumption descriptors, historical
source attribution, trace closure and unresolved coverage. Fixed explanatory prose
states the meaning of each. Untrusted content uses dynamically longer code fences;
raw links, HTML and images never become active Markdown. Private notes carry their
subtype when available; older portable-v1 notes explicitly lack that subtype.

CSV is UTF-8, RFC4180 (CRLF record terminators). Header names are fixed. **Every
nonempty text data cell starts with one added apostrophe**, including ordinary
identifiers, JSON fields, control-prefixed text and text already starting with an
apostrophe. Remove exactly one to recover the original text. Do not execute the
decoded string in a spreadsheet. Numeric columns (`report_schema`, `world_schema`,
`sequence`, `day`, `tick`, `value`) contain only trusted bounded integers or
validated Decimal quantity strings; signs, exponent and precision remain intact.
CSV consumers should parse quantities as Decimal, not binary float. Spreadsheet
autoformatting can change their display. Empty numeric cells mean unavailable or
not applicable, never zero. Structured laws retain their original integer weights
or rational numerator/denominator; no distribution is silently sampled.

Row kinds:

- `measurement`: saved scoped Python indicator, with definition version,
  effective simulation calendar/tick, coverage/reason, quantity unit/time basis/
  denominator, result/model/catalog/numeric identities and provenance links.
- `input_value`: authored input or state, explicitly distinguished from a
  calculated indicator. `partition` and `value_id` identify its role.
- `time_series` / `time_series_state`: the corresponding retained calculation or
  input/state at an experiment boundary, with experiment ID, sequence and day.
  A retained value's effective tick can precede its containing boundary day.
- `distribution`: declared experiment random law, variable/consumer references,
  dependence declaration, RNG method identity, scheduled day and provenance.
  No empirical frequency, implicit independence or unit conversion is inferred.
- `comparison`: child-minus-parent only when the same application comparison
  service accepts definition, model/runtime/catalog, time, scope, units,
  denominator and coverage. Incompatible pairs have no value and list reasons.
- `evidence_unavailable`: missing/reduced retained measurement/trace evidence.
  Public authored inputs can remain available separately.

The optional typed-service `scope_id` selects measurement/state/comparison rows;
Markdown still includes the complete context, source and trace closure. Unknown
scope IDs fail. Desktop exports every scope in the selected folder or imported
collection. It never silently selects only the current revision. Transient
uncertainty/sensitivity previews are not retained experiment measurements and are
not exported as historical results. Explicit laws in saved experiment plans are.

Archive privacy options apply across all revisions, alternatives and evidence.
Notes/rationale are excluded by default and appear only in Markdown after opt-in;
CSV contains no note/transcript/attachment payloads. Keys, encrypted key blobs,
private indexes and unrelated files are never enumerated. This version has no
transcript/attachment store. Public player-promoted design content remains public.
Projection identities are distinct from original private-bound hashes. Redaction
and evidence omissions remain explicit; projection does not establish scientific
validity or complete source coverage. No reports are automatically sent anywhere.

Main owns save dialogs and the selected absolute path. Renderer IPC accepts only
the generated `ReportRequest` and returns a small `ReportReply` receipt. Python
uses a bounded validated archive projection (256 MiB), writes in <=64 KiB chunks
under a 512 MiB output budget and publishes exclusively to a new file. Cancellation,
validation/size/write failures remove staging files and never change world state.
The worker has a 120s deadline. An uncertain reply may mean a complete file already
exists; the UI says to use a new path. Killing the process can leave an unlinked
staging file; it cannot expose a partial destination. Export is offline and uses
no secret environment variables. Windows native validation remains separate.
