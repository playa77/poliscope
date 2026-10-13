# Poliscope

**An educational sandbox for designing and exploring societies.**

Build a civilization out of choices. Follow their consequences across food, work, governance, relationships, culture, health, infrastructure, and the environment. Revisit an assumption, take another path, and see what changes.

Polyscope is a desktop simulation of one civilization as an interconnected system. You shape its institutions and material arrangements through readable, clickable interviews, inspect its resource and service accounts, and explore the relationships between your decisions.

You decide what matters. There is no campaign, prescribed ideal society, victory condition, or overall civilization score. Set your own targets, investigate a question, or simply explore.

## What you can do

- **Design through interviews.** Read a concrete problem, compare alternatives, ask for clarification, and preview a choice before applying it.
- **See the consequences.** Inspect status bars, quantities, service coverage, obligations, shortages, and unresolved conflicts.
- **Explore every choice.** Search the decision atlas, revisit alternatives, and follow dependencies through an interactive matrix.
- **Work across scales.** Inspect households, population groups, communities, settlements, regions, institutions, and the civilization as a whole.
- **Run experiments.** Advance through time, schedule changes, introduce disruptions, and inspect the mechanisms behind the results.
- **Keep alternate futures.** Fork designs and timelines, revisit earlier states, and compare branches without losing your previous work.
- **Inspect the evidence.** Follow outcomes to their inputs, calculations, assumptions, sources, and model definitions.
- **Use your own AI.** Connect a BYOK provider, including full OpenRouter integration, for contextual interviews and explanations.
- **Own your work.** Save locally, work offline, and export portable civilizations and explanatory reports.

## Get started

Download the appropriate package from this repository's **Releases** page:

| Platform | Supported architecture |
|---|---|
| Windows | x64 |
| macOS | Apple Silicon and Intel |
| Linux | x64 |

The desktop packages include the Python engine. You do not need Python, Node.js, a server, or an AI account to play.

1. Create a sandbox and choose or enter its starting conditions.
2. Give it a name. Add a purpose or target if you want one.
3. Open any domain in the society map and select a question.
4. Preview a choice, inspect its consequences, and apply it when ready.
5. Follow a dependency into another domain, or fork the design to compare an alternative.
6. Start an experiment when you want to explore change over time.

A fresh sandbox has no selected civic policies and no assigned goals. Reference setups identify the choices and assumptions they include. You can edit them or begin from your own conditions.

## Twelve domains, one civilization

Polyscope connects the material, institutional, social, and environmental dimensions of a society.

| Domain | Explore |
|---|---|
| **I. Resource & Material Base** | Production, distribution, allocation, consumption, waste, and circular flows |
| **II. Economy & Exchange** | Exchange mechanisms, work, ownership, property, and distribution |
| **III. Governance & Collective Decision-Making** | Authority, representation, decision procedures, delegation, and accountability |
| **IV. Law, Order & Conflict Resolution** | Rights, duties, enforcement, disputes, and agreements |
| **V. Social Organization & Relationships** | Households, communities, care, participation, and the life course |
| **VI. Knowledge, Education & Culture** | Learning, research, skills, archives, and cultural institutions |
| **VII. Health & Wellbeing** | Health services, care needs, exposure, prevention, and modeled health changes |
| **VIII. Infrastructure & Built Environment** | Housing, utilities, transport, digital networks, construction, and maintenance |
| **IX. Communication & Information** | Information access, verification, communication, privacy, and disclosure |
| **X. Environment & Human–Nature Relationship** | Ecological stocks, regeneration, resource limits, pollution, and land use |
| **XI. Meaning, Values & Identity** | Beliefs, belonging, participation, accommodation, and declared commitments |
| **XII. Security & Risk Management** | Hazards, preparedness, continuity, response, and technological risk |

These domains share the same people, assets, resources, institutions, geography, and timeline. Expanding education can require buildings, trained workers, energy, household arrangements, access rules, and an administering institution. Those dependencies remain connected and inspectable.

Geography and authority can overlap: a watershed need not follow a political boundary, and a care network can cross settlements. Aggregate views retain links to local conditions and population groups.

## Make a choice, inspect a mechanism

Each interview presents one decision at a time. A short problem statement explains the issue, followed by alternatives that describe their mechanisms and trade-offs. You can inspect original wording and sources alongside any AI explanation.

Choosing a card opens a preview. It shows affected accounts, scopes, dependencies, and findings before your design changes. Applying the choice records its context, alternatives, and model version in history.

You can leave questions unanswered, change a parameter, propose an alternative, or preserve an idea as a qualitative commitment. An unsupported mechanism is shown as a model gap rather than assigned invented numerical effects.

A shortage or contradiction is something to investigate. It does not end the sandbox, erase your choices, or trigger an automatic redesign.

## Understand the bars

The overview contains a small, configurable collection of indicators. Each one identifies its quantity, scope, time basis, interpretation, and model coverage.

| Color | Meaning |
|---|---|
| **Green** | The indicator's stated diagnostic condition is met |
| **Orange** | A defined warning boundary or uncertainty overlap applies |
| **Red** | A modeled shortage, breach, or adverse diagnostic condition is present |
| **Gray** | The result is incomplete, unresolved, unmodeled, or inapplicable; its label explains which |

Click an indicator to open its account or definition. Inspect supplies, claims, actual allocations, unmet demand, assumptions, thresholds, calculations, and excluded effects. Neutral indicators are used when there is no defensible good/bad direction.

Player targets and selected policy commitments are labeled separately. Green bars do not declare an optimal civilization, and missing information is never treated as zero.

## Explore the choice space

The **decision atlas** contains questions, selections, alternatives, assumptions, and open issues. Filter it by domain, scope, source, coverage, or current state.

The **dependency matrix** starts with the twelve domains and drills into branches, decisions, and scopes. Cells distinguish requirements, supplies, capacity competition, conflicts, influences, and historical supersession. Open a relationship to inspect its mechanism, affected account, and evidence.

The **world and institutions** view shows people and groups, locations, networks, jurisdiction, and obligations. The **branch history** shows how different arrangements emerged from earlier choices.

These are complementary views of the same civilization. A blank matrix cell means no relationship is recorded in the selected model; it does not prove independence.

## Experiment with change

Use the design workspace to ask what a different arrangement would require. Use a timeline to ask how an existing arrangement changes under its declared mechanisms.

Experiments can include scheduled policy changes, construction, maintenance, learning, demographic transitions, resource flows, ecological change, and hazards where the selected models support them. Events can be player-authored or generated from explicitly configured stochastic processes.

Each run records its opening state, model versions, assumptions, event schedule, and random realization. Replay a run, fork a past state, or compare the same arrangement under different conditions.

A policy change scheduled for the future is distinct from a counterfactual redesign of the past. Transition costs, delays, and responses are calculated only when their mechanisms are defined. Missing mechanisms stay visible.

Comparison shows changed choices, assumptions, outcomes, distributions, and unresolved questions. It checks units, scopes, time bases, and model compatibility before displaying numerical differences. It does not pick a winner.

## AI assistance and BYOK

Polyscope's assistant helps explain mechanisms, clarify interview questions, trace dependencies, inspect sources, compare branches, and propose alternatives. Connect your own provider key in **Settings → AI Providers**.

### OpenRouter

OpenRouter is a first-class provider with support for:

- Model discovery, variants, capability details, context limits, and pricing information.
- Provider routing, ordering and filtering, fallback preferences, and supported privacy/data-use controls.
- Streaming and nonstreaming generation, cancellation, sampling controls, and reasoning options.
- Tool calling and structured responses where the selected model supports them.
- Capability-aware multimodal content and explicit attachment sharing.
- Reported usage, generation metadata, cost estimates, and actual costs where available.
- Actionable authentication, credit, rate-limit, model, provider, and stream errors.

Choose the model and routing preferences yourself. Unsupported capabilities or settings are explained rather than silently discarded. Other OpenAI-compatible BYOK endpoints are supported according to their declared capabilities.

### What the assistant can change

The assistant can inspect facts, retrieve sources, validate a proposal, and request a preview. You apply changes through the ordinary interface. It cannot commit decisions, alter simulation code, create resource supplies, or turn prose into authoritative arithmetic.

Python calculates simulation outcomes. Generated explanations are labeled and remain separate from calculation traces and source evidence.

### Context and spending

You can inspect which decision text, facts, excerpts, and conversation context will be sent. Private notes, unrelated branches, and attachments have explicit inclusion controls.

Usage reports distinguish estimates, actual reported costs, and unknown costs. Local limits govern new requests; provider-side account limits govern hard spending caps. Cancelling a request does not guarantee that an upstream provider stops charging immediately.

Authored interviews and the core simulation remain available without a key or connection.

## Local data and privacy

Civilizations, history, experiments, and transcripts are stored locally. Core use requires no application account and performs no background upload of your civilization.

Provider keys are protected through the operating system's credential facilities. When secure persistent storage is unavailable, keys can be held for the current session. They are never included in civilization exports or exposed to the Python engine.

Enabling assistance sends the context you select to your configured provider and, with OpenRouter, its routed model providers. Provider privacy and retention preferences follow the capabilities and policies of those services.

Transcripts can be deleted independently of design history. Exporting private notes or transcripts is an explicit choice.

## Saves, branches, and reports

- **Portable civilizations** preserve choices, alternatives, branches, assumptions, experiments, source references, and model identities.
- **Markdown reports** explain the arrangement, observed outcomes, open questions, and evidence.
- **CSV exports** provide scoped quantities and measurements with units, time bases, and coverage.

Undo preserves later exploration as recoverable history. Branching keeps alternatives separate. Model updates create an explicit migration or comparison branch instead of silently changing old results.

Historical results remain inspectable even when their exact engine is unavailable. Recomputing them requires a compatible model/runtime. Imported archives contain data, not executable simulation code.

## Models and evidence

Polyscope distinguishes historical design choices, empirical evidence, hypothetical assumptions, and implemented mechanisms. Its catalogs and model packs preserve sources, versions, amendments, and coverage.

The [Society Redesign project](https://github.com/playa77/society) supplies a source corpus and reference arrangements. Its adopted choices are available for study; they do not become mandatory answers or player goals. The architecture also supports compatible content and models built from other documented assumptions.

Deterministic computation means the same versioned inputs and event realization produce the same numerical results within the recorded runtime contract. It does not mean that every assumption is certain or every social consequence can be predicted.

Institutional, cultural, and behavioral effects use explicit definitions and evidence. Undefined effects remain qualitative or unmodeled. Fairness, legitimacy, meaning, and wellbeing are not compressed into universal civilization scores.

## For educators

Share a reference setup, pose a question, and let learners explore different arrangements. Students can record an expectation, change one assumption, run an experiment, and report which mechanism explains the difference.

Reports retain evidence and model limitations alongside results. Classroom inquiry requires no instructor account, central server, assigned campaign, or hidden grading. The interface supports keyboard navigation, text equivalents for color, accessible matrix lists, and readable long-form choices.

## Architecture

| Layer | Technology | Responsibility |
|---|---|---|
| Desktop | Electron | Application lifecycle, files, secure keys, provider connections |
| Interface | React and TypeScript | Interviews, indicators, atlas, matrix, timelines, comparison |
| Simulation | Python | Shared world, domain mechanisms, arithmetic, transitions, constraints, traces |
| Storage | SQLite | Transactional revisions, branches, experiments, model archives |
| Integration | Typed JSON Lines over stdio | Desktop/engine communication without a local HTTP server |

All twelve domain modules use the same world entities, scope system, accounts, units, history, and explanation contracts. The renderer does not maintain a second simulation engine, and the assistant cannot bypass those contracts.

Read the [global game design architecture](docs/DESIGN.md) and [global technical architecture](docs/TECH_SPEC.md) for the full system design.

## Development

Development requires **Node.js 24 LTS**, **Python 3.12**, and **uv**. Clone the repository and run the following from its root:

```sh
npm ci
uv sync --frozen --python 3.12
npm run dev
```

The development command starts the desktop interface and managed Python engine. Packaged builds use the bundled engine rather than a user's system Python.

Validate content, contracts, and code with:

```sh
npm run content:validate
npm run contracts:check
npm run typecheck
uv run --frozen pytest
npm test
npm run test:desktop
```

Build a native desktop package with:

```sh
npm run package
```

Native packages are built on their target operating system and architecture. Signing and notarization use local or CI configuration, never committed credentials.

Tests cover independent numerical fixtures, conservation, scope aggregation, coupled mechanisms, timeline replay, history, archive safety, provider behavior, and desktop interaction. Ordinary tests use provider mocks; paid live-provider checks are explicit opt-in tests.

Enter development BYOK credentials through the application's settings. Keep real civilizations, transcripts, keys, and local configuration outside tracked source files.

## Contributing

Contributions can improve the application, accessibility, interviews, sources, model definitions, or validation fixtures.

For a model contribution, identify its mechanism, scopes, inputs, outputs, units, assumptions, and evidence. Include independently derived expectations and relevant invariants. Distinguish a proposed design from an observed fact and a structural validator from scientific validation.

New domain content uses the shared contracts. It must not duplicate resource stocks, silently choose political precedence, hide missing inputs, or introduce an overall civilization score.

Preserve source attribution and historical alternatives. Keep credentials and private data out of issues, test fixtures, logs, and pull requests.
