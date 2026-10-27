# Accessibility and inquiry audit — WP-052

This is an author inspection and functional regression record, not a user study,
screen-reader certification or native Windows/Linux acceptance. The repository
owner runs native checks. All examples use synthetic local data; AI is optional.

## Core task inspection

| Task and implementation | Keyboard and accessible representation | Meaning and safeguards inspected |
| --- | --- | --- |
| Create/open a civilization (`workspace.tsx`) | Native labeled inputs, select and submit; skip link; focusable selected state | Unknown quantities remain unknown; blank civic choices; optional purpose creates no target |
| Choose/interview (`interview.tsx`) | Native radio group and fieldset, source/dependency disclosure; selected-domain focus | Origin/evidence/modeling/version and revision/scope; historical source adoption is not a player choice; defer is available |
| Preview/apply/cancel (`interview.tsx`, `world.tsx`, `evidence.tsx`) | Preview heading receives focus; Apply and cancellation are separate named buttons; errors use alerts | Noncommitting previews, qualitative model gaps, uncertain save/retry and retained alternatives remain explicit |
| Inspect shortage (`overview.tsx`) | Named buttons, exact distribution table, focus enters inspector and returns to trigger; Escape closes inspector | Local findings survive aggregate surplus; all seven coverage statuses have text; targets are player preferences |
| Trace assumption/source (`overview.tsx`, `atlas.tsx`, `matrix.tsx`) | Native disclosures and named inspection/paging controls; scoped row/column headers | Declared formulas, units, scope, time, source license, assumptions and unavailable evidence are retained |
| Atlas/matrix (`atlas.tsx`, `matrix.tsx`) | Labeled filters, sparse HTML table and relation list; no pointer-only cells | Count, relationship type, activation and coverage are separate; unknown grouping is visible |
| Network/world (`world.tsx`) | Diagram has a title and equivalent table with directed endpoints and relationship terms; edit controls are ordinary buttons | Layout rearrangement cannot edit canonical state; overlapping groups remain distinct; obligations do not imply fulfillment |
| Uncertainty (`uncertainty.tsx`) | Labeled inputs and report/witness tables | Hypothetical calculation, range, dependence and unsupported methods are explicit; no winner ranking |
| Timeline/experiments (`timeline.tsx`) | Native date/run/cancel/compare controls; exact state and probability tables accompany charts | Confirmed boundaries, scope, time, retained traces, declared laws and missing values; realized trajectories do not estimate probability |
| Fork/compare (`design-history.tsx`) | Named history buttons, labeled branch/revision inputs and lineage/comparison tables | Read-only history, alternate futures, right-minus-left delta and no branch ranking |
| Report/archive (`archives.tsx`) | Named import/export buttons, labeled privacy choices, native main-owned dialogs, bounded facts table | Markdown inquiry and typed CSV use saved evidence; private data opt-ins are explicit; no model rerun |
| Assistant/providers (`src.tsx`, `providers.tsx`, `assistant.tsx`) | Provider focus enters panel and Close returns to opener; native settings, sharing, stop/delete and proposal buttons | Optional own-key assistance, explicit sharing and ordinary player-approved proposals; offline inquiry remains available |
| Recovery/history (`recovery.tsx`, `src.tsx`) | Named inspection/backup/restore buttons, native dialogs, labeled retained identifiers and tables/text | Original store preserved, read-only evidence distinguished from execution compatibility |

The current learner regression (`accessibility.spec.ts`) connects expectation note,
interview preview/apply/deferral, matrix table, retained comparison, fork,
observation note and explicitly opted-in Markdown report in one offline session.
This contributes E2E-016.b evidence; it does not declare the cumulative G7/M7 gate.

All renderer tables declare column/row header scope. Interactive controls use
native semantics and visible names; no positive tab index or custom pointer-only
interaction is required. Inline inspectors are nonmodal: there is no focus trap.
File dialogs are main-owned native dialogs; OS dialog assistive behavior remains
owner-run. Status and error messages use status/alert roles, including retained indicator,
distribution, inspector and selected-state reads; polling engine status does not claim that pending work saved.

## Defects fixed

- Navigation changed content without moving focus into the destination. View
  headings and selected interviews now receive focus after explicit navigation.
- Preview results and world/evidence edit forms appeared after the initiating
  control without focus. Focus now enters the new heading. Applying a revision
  can remove the focused button; the selected-state region recovers lost focus.
  Cancelling world/evidence edits restores the opener or the recreated Add control.
- Provider settings had no return control. Close removes the panel and returns
  focus to the actual opener, including optional interview assistance.
- The skip link moves focus without changing the file URL: a fragment would
  invalidate the strict IPC sender grant. The regression checks both unchanged
  URL and a subsequent real workspace operation.
- Evidence inspector had button-only closure. Escape now closes it using the
  same existing focus restoration path.
- Table headers lacked explicit axes. Column and row scopes are now declared.
- Brown focus outline had poor contrast on the dark background. The pale outline
  also has a forced-colors Highlight override. Form controls inherit type size and
  dark color scheme. Narrow cards can shrink; table overflow stays in the article.
- The UI assumed the reader knew the inquiry workflow. An optional, collapsible
  six-step guide explains prediction, preview, local exclusion, source/coverage,
  same-state comparison and reports without assigning a goal or requiring AI.

The sRGB relative-luminance contrast calculation gives 11.97:1 for body text
(`#e8e9dc` on `#172c2a`), 9.27:1 for eyebrow text, 11.52:1 for links,
and 10.58:1 / 8.71:1 for the focus outline against the page/state panel.
These authored pairs exceed 4.5:1 text and 3:1 focus contrast. Native control
palettes and assistive rendering still depend on the owner's operating system.

## Inquiry walkthroughs

These are author-performed task perspectives over synthetic fixtures, not recruited
students, designers or educators. They do not establish classroom learning outcomes.

| Perspective | Task and evidence route | Interpretation the interface supports |
| --- | --- | --- |
| Student | Predict a population change, choose a domain alternative, preview 125 people, inspect unchanged branch before Apply; apply/cancel and read saved conditions (`accessibility.spec.ts`, `interview.spec.ts`) | A preview is unsaved; authored population is not a simulated benefit. Qualitative commitments do not calculate unsupported social effects. |
| Designer | Inspect east reserve 0 kg beside regional 200 kg, follow retained trace and declared no-transfer assumption/source, inspect local distribution; set an isolated session target (`overview.spec.ts`) | Regional surplus does not supply the excluded local group. A target is a declared preference. Exact trace, assumptions and coverage explain the result without AI. |
| Educator | Fork a retained revision, change the alternative, compare retained outcomes, inspect original wording and export an inquiry report (`design-history.spec.ts`, `atlas.spec.ts`, `reports.spec.ts`) | Original source choices are historical context, not required progression. Compare the same scope/time, explain model limits and preserve alternatives without a universal ranking. |

## Validation scope

The package record records current-run commands and results. Cloud packaged
Electron checks cover the named functional workflows, keyboard activation, focus,
zoom and table equivalents. Native screen-reader speech, OS contrast settings,
physical keyboard layouts and actual student comprehension are not measured here.
No claim of independent accessibility certification or human usability research.
