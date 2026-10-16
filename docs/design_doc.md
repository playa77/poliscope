# Poliscope — Global Game Design Architecture

Revision 0.2 · 2026-10-13

**Document scope:** the complete educational sandbox, across all twelve society domains, all supported social scales, design decisions, simulation, interviews, explanation, and exploration. This document defines the whole product. It does not define a work package, prototype, release slice, or implementation schedule.

**Companion:** [Global technical architecture and specification](tech_spec.md).

**Authority:** freeplay with player-defined purposes; Electron and Python; BYOK with full OpenRouter support. Architecture choices are made under the user's instruction to decide the stack. Civic choices belong to the player.

## 1. The game as a whole

Poliscope is an educational desktop game in which a player designs and explores a single civilization as an interconnected system. The civilization can contain many households, communities, settlements, regions, institutions, and jurisdictions. The surrounding environment and external societies exist as explicit conditions and interfaces to that civilization, rather than as competing playable empires.

The central activity is making choices about how people live together, seeing what those choices require, and exploring the consequences of combining them. Interviews make individual choices accessible. Resource accounts, institutional relationships, service systems, demographic aggregates, and declared behavioral models make their consequences inspectable. A decision atlas and dependency matrix make the entire arrangement navigable.

There is no campaign, victory condition, civilization ranking, assigned ideology, or mandatory target. The player may aim for resilience, autonomy, abundance, equality, ecological preservation, a particular institutional experiment, or no stated goal. The application does not combine those preferences into its own definition of an optimal civilization.

The game should support a curious student, an independent designer, and an educator facilitating discussion. Its educational value comes from exposing relationships, assumptions, and counterfactuals. Agreeing with the source project's choices is not an educational success criterion.

## 2. Product principles

| Principle | Whole-game consequence |
|---|---|
| Player purpose | Goals are optional and player-authored; no default weights or hidden score |
| Mechanisms before judgments | Effects identify what changes, through which mechanism, for whom, and at which scale |
| One system | Domains share people, resources, institutions, space, and time; they do not own separate copies |
| Inspectable consequences | Every calculated outcome links to inputs, rules, assumptions, and affected choices |
| Honest coverage | Unknown, qualitative, estimated, and calculated outcomes remain distinct |
| Reversible inquiry | Choices, timelines, assumptions, and model versions can be branched and compared |
| No forced progression | Players can enter any domain; dependencies explain missing prerequisites rather than create a campaign |
| Independent arithmetic | Python owns all simulation arithmetic; AI explains and proposes |
| Player-controlled AI | BYOK, explicit provider/model selection, visible context sharing, OpenRouter support |
| Local ownership | Saves and core simulation work locally; AI services are optional network dependencies |

An insufficient design remains a playable design. An institutional contradiction remains a question to investigate. Neither produces a game-over screen or an automatic correction.

## 3. World and society model

### 3.1 The world is a set of related scopes

The primary civilization contains geographically situated settlements and regions, population cohorts, household/community arrangements, institutions, infrastructure, and resource systems. These are explicit entities with stable identities, not twelve independent domain sheets.

The scope vocabulary is household, community/local, settlement, region, civilization-wide, and global/external. A decision attaches to a defined scope or group of scopes. The player can inspect a decision locally or aggregate it across the civilization.

Geography, membership, and authority are separate relationships. A watershed may cross political regions; a care network may span settlements; an institution may have jurisdiction over a resource rather than a territory. The design must express these overlaps without assigning every relationship to one geographic hierarchy.

Population is represented through cohorts and aggregate arrangements. Individually simulated citizens are not required for the game to represent households, dependency ratios, labor, migration, or service demand. A detailed behavioral model may exist within a model pack, but it must state what it represents and cannot stand in for every human motivation.

### 3.2 What is chosen, what is given, and what emerges

The interface distinguishes:

- **Conditions:** geography, opening population, stocks, available technology, external relationships, and environment.
- **Design choices:** institutions, rules, organization, service provision, infrastructure plans, and commitments.
- **Assumptions:** coefficients, behavior rules, uncertain estimates, and external responses.
- **State:** what currently exists, including stocks, operating capacity, population composition, active institutions, and current obligations.
- **Consequences:** calculations, distributions, shortages, dependencies, conflicts, and model-supported changes over time.
- **Player purposes:** notes, questions, and optional targets used to interpret the consequences.

The application never treats a player target as a physical fact, a historical source choice as a player choice, or an AI statement as a calculated outcome.

### 3.3 External relationships are explicit

The civilization may import, export, migrate, cooperate, exchange information, or face external hazards. External resources and responses have capacities, terms, schedules, or declared behavioral assumptions. A missing diplomatic mechanism cannot become a guaranteed delivery; an external market cannot become unlimited supply.

The player may model the surroundings in detail or use declared boundary conditions. Both approaches are visible in the experiment's record.

## 4. The twelve domains

The original three-level society map supplies the whole-game classification. Every domain and branch belongs in the catalog and can host questions, mechanisms, observations, and open issues. A domain's presence does not imply every possible social effect has already been quantified.

| Domain | Decisions and systems within its responsibility | Shared consequences and interfaces |
|---|---|---|
| **I. Resource & Material Base** | Production; distribution/logistics; consumption, waste, circular loops | Food, water, energy, materials, goods stocks and flows; claims on labor, land, infrastructure, and ecological sinks |
| **II. Economy & Exchange** | Value/exchange; labor/work; ownership/property; wealth distribution | Ownership and access, transactions, labor assignment, income/assets where modeled, resource allocation, service funding |
| **III. Governance & Collective Decision-Making** | Political structure; decision processes; power/accountability | Jurisdictions, authority, representation, procedure, obligations, oversight, decision capacity |
| **IV. Law, Order & Conflict Resolution** | Norms/rights; enforcement; dispute resolution; inter-group conflict | Rights and duties, claims, adjudication, enforcement capacity, conflict-resolution procedures and external agreements |
| **V. Social Organization & Relationships** | Households/kinship; community; life-course and care | Household composition, care obligations, dependency and participation arrangements, cohort-linked service demand |
| **VI. Knowledge, Education & Culture** | Research/archives; education/training; cultural production | Skills, learning/service capacity, knowledge access, technology assumptions, cultural institutions and participation |
| **VII. Health & Wellbeing** | Physical health; mental/emotional wellbeing; birth, life, death and care | Needs and service capacity, modeled health transitions, exposure, care demand, demographic consequences where justified |
| **VIII. Infrastructure & Built Environment** | Physical infrastructure; spatial organization; digital infrastructure | Asset capacity, connectivity, construction/maintenance claims, housing and service access, spatial constraints |
| **IX. Communication & Information** | Information flow/verification; communication; mediated information and privacy | Communication capacity, access/control, delays, information dependencies, disclosure and privacy rules |
| **X. Environment & Human–Nature Relationship** | Stewardship; resource sustainability; land/ecosystem relations | Ecological stocks/flows, regeneration, emissions/waste sinks, environmental constraints and exposure |
| **XI. Meaning, Values & Identity** | Belief; identity/belonging; purpose, ritual and aspiration | Declared values, collective institutions, participation and accommodation rules; qualitative tensions and explicitly defined indicators |
| **XII. Security & Risk Management** | Physical security; systemic risk; technological risk | Hazard/event assumptions, prevention/preparedness capacity, response systems, vulnerabilities and continuity requirements |

Each domain participates in the same architecture. Institutional and cultural domains are not deferred to decorative narrative around a resource simulator. They can define executable procedures and allocations where mechanisms are specified, qualitative requirements where they are not, and observable indicators with explicit definitions. They do not receive invented universal meters for legitimacy, happiness, fairness, or social cohesion.

## 5. Systems that cross all domains

### 5.1 People, time, and capacity

One shared population model supplies denominators, age/cohort membership, labor availability, care needs, learning participation, and service demand. Time spent in work, care, training, or administration must be accounted against the same available population/time budgets where the chosen model represents those commitments.

A person cannot simultaneously become a full worker in each domain merely because each branch calculates its needs independently. Different definitions of labor, employment, participation, and unpaid work remain visible.

### 5.2 Resources, access, and obligations

Physical quantities and institutional access are related but distinct. Food can physically exist while particular households lack access to it. An institution can promise care without enough trained people to provide it. The game displays both the gross account and the allocation or service relationship.

Resources have production, transformation, movement, storage, use, loss, and regeneration. Access mechanisms specify who can claim them and under what procedure. The engine cannot infer an allocation rule simply from an aggregate shortage.

### 5.3 Authority and conflict

Institutions have defined authority, scope, procedures, obligations, funding/capacity assumptions, and oversight. Choices can create overlaps or gaps. The game exposes which actors claim a decision and whether a resolution mechanism exists.

An authority diagram is inspectable from a matrix relationship. A conflict can be a calculable capacity competition, a contradictory policy rule, or an unresolved jurisdictional question; these are different findings.

### 5.4 Space, connectivity, and ecological context

Infrastructure connects people, services, and production across locations. Regions differ in resources and exposure. Ecological limits belong to physical systems and selected commitments, not to a civilization-wide morality score. Aggregation must not hide a local shortfall behind a distant surplus that cannot be delivered.

### 5.5 Knowledge, communication, and meaning

Knowledge capacity and communication systems affect how institutions and services can operate. Identity and values shape declared commitments and participation arrangements. Effects are modeled through specific procedures, capacities, or behavior assumptions; slogans do not become numerical coefficients.

### 5.6 Risk and change

Hazards interact with the arrangement already chosen. The same event can expose resource dependency, unequal access, institutional delay, infrastructure fragility, and communication failure together. Responses require explicit capacity and rules rather than automatic rescue.

### 5.7 A whole-system relationship path

Consider a player choosing how education is provided. The education mechanism defines participation, staffing, and service capacity in Domain VI. Facilities and connectivity refer to Domain VIII; energy, materials, and supplies refer to I; work allocation and funding/access rules refer to II. Household care and participation arrangements come from V, while any modeled health or care requirements refer to VII.

The actor authorized to administer the arrangement belongs to III. Rights, eligibility claims, and dispute procedures connect to IV. Communication and privacy connect to IX. Land, resource extraction, and environmental exposure connect to X. Language, belief, identity, and accommodation commitments connect to XI. Continuity during disruption connects to XII.

These relationships point to the same people, assets, institutions, accounts, and chosen rules. The model calculates the effects it actually represents and identifies the remaining requirements. It does not translate “more education” into an automatic civilization improvement score. This illustrates the global integration contract; it is not a prescribed starting scenario or a separate work package.

## 6. Modes of inquiry

These are views and activities within one sandbox, not campaign stages.

### 6.1 Design and inspect

The player can begin anywhere in the society map, answer an interview, edit an assumption, or inspect an existing arrangement. A proposed change is previewed before application. The preview shows affected quantities, populations/scopes, dependencies, and unresolved questions.

A new sandbox has no assigned goals or selected civic policies. Starting conditions may come from a named editable setup. Reference civilizations may populate a design only when explicitly selected.

Unanswered questions remain unanswered. The player may compare partly specified societies; the interface shows which comparisons have sufficient evidence.

### 6.2 Simulate and experiment

The player can run a modeled arrangement through time, schedule changes, introduce conditions, and observe supported consequences. Experiments record opening state, policy schedule, model versions, assumptions, time resolution, and optional random seed.

Timing belongs to the mechanisms: infrastructure can require construction and maintenance; institutions can have adoption or decision delays; education can affect skill stocks; ecological and demographic models can update over their declared intervals. These effects require explicit models and inputs. If a chosen pack lacks a transition mechanism, the game reports that limitation instead of inventing instant completion or a delay.

Experiments may be deterministic without hazards, use player-authored event schedules, or use declared stochastic processes. The random realization is reproducible and recorded. There is no compulsory disaster sequence.

### 6.3 Counterfactual design versus historical change

“What if this society had different rules?” forks a design or past state and compares alternatives. “What happens if these rules change next year?” schedules a change in an experiment. The interface names the difference so rebuilding a hypothetical civilization is not confused with transforming an existing one.

### 6.4 Reflect and compare

The player can compare designs, time histories, population groups, regions, assumptions, and model versions. Numerical differences are presented alongside changed mechanisms and missing evidence. No branch is crowned the winner.

Notes and optional targets help the player remember why they explored a branch. A student can record an expectation, run an experiment, and describe which assumption explains the result.

## 7. Interviews and decisions

An interview presents one substantive decision at a time. It opens with a concrete prose problem, then usually three or four clickable choices with short labels and readable explanations of mechanism, benefit, and cost. The scope and affected systems are visible.

The player can ask for clarification, inspect sources, preview alternatives, or defer the question. Choosing a card does not immediately modify the design; Apply records the decision. Numeric input controls are available when a question genuinely concerns a quantity.

Questions can originate from curated content, context-sensitive templates, or AI-assisted proposals. Their origin and modeling status are visible. A generated question does not acquire authority because it sounds persuasive.

The system supports existing options, parameter variants, and player-proposed alternatives. A new alternative may use existing validated mechanisms or remain a qualitative design commitment. Unsupported mechanisms are tracked as model gaps. They do not receive fabricated quantitative effects.

Decisions record rationale, scale, source, assumptions, dependencies, and full alternatives. Revising a decision preserves its history. A source project's chosen option is historical context, not the player's default answer.

The interview system can surface a relevant unresolved dependency, but the player controls where to go next. There are no level gates, skill trees, or hidden canonical answer sequences.

## 8. Global information architecture

| Workspace | Purpose | Main transitions |
|---|---|---|
| **Civilization overview** | Inspect a configurable small set of conditions and active findings | Open account, scope, decision, institution, or experiment |
| **Society map** | Navigate the twelve domains and their branches | Enter interview or inspect domain relationships |
| **Decision atlas** | Explore all choices, alternatives, commitments, and unanswered questions | Preview, revise, locate sources, fork |
| **Dependency matrix** | Explore relationships across domains, scopes, and decisions | Drill into mechanisms, resource competition, or authority gaps |
| **World and institutions** | Inspect locations, groups, networks, actors, and jurisdiction | Inspect scope-specific access, capacity, procedure, or obligation |
| **Timeline and experiments** | Advance, schedule, replay, and inspect change | Open event consequences, fork a state, compare a run |
| **History and comparison** | Explore the lineage of choices and outcomes | Restore/fork, compare revisions, annotate |
| **Evidence and models** | Inspect formulas, source material, assumptions, and coverage | Adjust a supported parameter, review a gap, compare model versions |
| **Assistant and provider settings** | Ask questions and manage BYOK/model/routing | Explain, propose a preview, inspect usage/context |

These views are synchronized around a selected civilization, branch, scope, and design revision or simulation time. A result always shows which state it describes. An assistant reply about an older revision cannot silently become an explanation of the current one.

The desktop layout uses a navigation rail, a central workspace, and an optional inspector. It favors prose, tables, modest charts, and network diagrams. It does not require a 3D world or individual-character animation. Geography is an explanatory map or topology, not a compulsory terrain-building game.

## 9. Bars, indicators, and explanation

The overview shows a player-configurable small collection of indicators rather than a dashboard containing every domain metric. Resource sufficiency, service coverage, available capacity, reserves, ecological exposure, and institutional findings can appear when their models justify them.

Every bar shows units, scope, time basis, model coverage, and a status label as well as color. Inspecting it opens the account or indicator definition, inputs, calculations, policy thresholds, sources, distribution across groups, and exclusions.

| Visual state | Interpretation |
|---|---|
| Green | The stated diagnostic condition is met under the displayed assumptions |
| Orange | A defined warning boundary or uncertainty overlap applies |
| Red | A modeled shortage, breach, or adverse diagnostic condition is present |
| Gray | The condition is unknown, unresolved, inapplicable, or insufficiently modeled; text distinguishes these cases |

Diagnostic thresholds belong to named definitions. The game does not apply a universal “10% margin” to every domain. Where a metric has no defensible good/bad direction, it is displayed neutrally. A chosen policy commitment or player target is identified as such. No set of green bars constitutes victory.

Goals can be narrative questions or structured targets. They are empty by default, do not change simulation behavior, and do not aggregate into a score. Target observations say “within your target” rather than “better.”

Explanation has three separate layers: Python calculation trace, source/model rationale, and optional generated explanation. The player can inspect each without treating them as equivalent evidence.

## 10. The explorable matrix of choices

The game's choice exploration has complementary representations:

- **Atlas:** decisions and their complete option sets, filtered by domain, scope, source, selection, coverage, and unresolved issues.
- **Domain matrix:** the twelve domains on each axis; cells show typed relationships and active consequences.
- **Decision matrix:** drill-down into selected decisions or branches, with requires, supplies, competes, conflicts, influences, and supersedes relationships.
- **Scope matrix:** compare decisions and outcomes across households/cohorts, settlements, regions, and the civilization.
- **Branch lineage:** the choices that distinguish alternate designs and experiments.

The row-to-column direction and relationship type are explicit. A dependency count is not a strength-of-effect score. Blank means no relationship recorded in the selected model, not independence. Historical supersession is visibly different from an active causal relationship.

A cell opens the participating choices, the mechanism or rule, the affected account, the relevant source, and the current condition. Players can follow an energy choice into infrastructure, environmental exposure, health-service demand, labor requirements, and governance obligations wherever the model documents those links.

The matrix is a navigable representation of the choice space. It does not enumerate every possible combination of all alternatives. Views are filtered, sparse, virtualized when necessary, and available as accessible lists.

## 11. AI and BYOK in the whole game

AI is an interviewer, explainer, contextual guide, and proposer of alternatives. It may help the player formulate a question, understand a mechanism, trace a contradiction, compare branches, or draft a new qualitative design. It does not define the player's goals or become the numerical simulation engine.

Python remains authoritative for formulas, allocations, transitions, constraints, and results. AI can request read-only calculations and previews using structured tools. Changes to the saved civilization require a visible player action through the same application flow used by ordinary choices.

The assistant distinguishes supported consequences from hypotheses. A proposal for a new mechanism may be stored and explored qualitatively; activating numerical behavior requires a validated model definition, not generated prose or executable generated code.

BYOK is part of the product architecture. OpenRouter receives dedicated support for model discovery/selection, provider routing, capability-aware generation, streaming/cancellation, tool calling, structured outputs, reasoning metadata, usage/costs, error handling, and privacy/data-use settings. Attachment and modality handling follows actual model/provider capabilities; unsupported combinations are explicit rather than silently discarded.

The player can inspect the context sent, select the model, change routing preferences, constrain requests, stop a reply, and inspect reported expenditure. Keys are protected locally and never included in a civilization save. Model/provider changes are recorded on assistant turns.

Authored interviews, simulation, matrix exploration, history, and reports remain usable offline. AI connection failure does not invalidate a civilization. Generated explanation is labeled, and model language is not promised to be deterministic.

## 12. Content, models, and evidence

The product separates four kinds of material:

1. **The society map:** domain and branch classification.
2. **Design content:** questions, options, institutional mechanisms, obligations, rationales, and alternatives.
3. **Simulation models:** quantities, rules, transitions, allocation and resolution procedures, uncertainty assumptions, and measurements.
4. **Evidence:** source passages, empirical references, estimates, and hypothetical assumptions.

They are versioned and linked. Adding an interview does not automatically add a causal model. A source range is not automatically a probability distribution. A binding decision in a source project is not an empirical law.

The `playa77/society` repository is a source corpus and an optional reference civilization. Its full twelve-domain structure guides classification; its ledger supplies preserved choices and rationale; its integration documents supply dependency and conflict candidates. Its current concentration of detailed work in production and logistics does not define the scope of the game.

The source essay is available as context. It does not impose a required worldview or success criterion on players. Other compatible model/content packs can represent different assumptions and arrangements with equivalent provenance requirements.

Amendments and superseded alternatives retain their lineage. Source/document-maintenance decisions are provenance, not game policies. Model coverage is shown independently of historical source status. Disputed source arithmetic is a model-review item, not a reason to silently rewrite the civic ledger.

## 13. History, reproducibility, and comparison

The game preserves two linked histories: the design choices and the simulated timeline. A timeline references the design/model versions that produced it and records effective changes, events, random realization, and assumptions. A branch can start from a design revision or a simulation state.

Undo restores a prior state without destroying subsequent exploration. Editing after undo preserves the previous future as a branch. Choices and their offered alternatives remain readable even after content updates.

Reproducing a numerical result requires the same inputs, model/rule versions, initial state, event schedule, and seed or recorded random draws. Updating a model creates an explicit new comparison branch; it does not reinterpret an old save invisibly.

Comparison aligns scopes, units, time bases, and model versions. It exposes differences across population groups and regions as well as aggregates. Where alignment is impossible, it explains the incompatibility. An absent outcome is not displayed as zero.

## 14. Educational use and ownership

Players can export a portable civilization and an explanatory report containing their questions, choices, assumptions, results, traces, sources, and notes. Educators can share reference setups and inquiry prompts without introducing mandatory goals, a campaign, or hidden grading.

A learner's report can separate expectation from observation and name the assumption on which a conclusion depends. The assistant can help express that distinction, but the calculation and source evidence remain available directly.

Saves are local and belong to the player. Sharing is an explicit export, not background telemetry. AI transcripts and private notes have independent inclusion controls; keys are never exportable as part of a civilization. A classroom does not require a central server or instructor account.

## 15. Whole-game quality criteria

The architecture is fulfilled when:

- All twelve domains use the same choice, scope, dependency, evidence, and model framework.
- A decision in any domain can affect and be inspected through other domains without copying their shared state.
- The same civilization can express overlapping jurisdictions and differing local arrangements.
- Players can design, simulate change, branch, compare, and explain outcomes without receiving an assigned goal.
- Every numerical result is traceable; every unsupported consequence is visibly unsupported.
- Capacity, access, distribution, institutional procedure, and environmental conditions can be inspected separately.
- Generated interviews and proposals enter the same provenance and validation framework as authored content.
- OpenRouter is a full provider integration with BYOK, not merely a substituted endpoint.
- Offline core use and local ownership survive AI/network failure.
- Every core action is keyboard-accessible; color is never the sole carrier of meaning.

These are architecture-level requirements for the entire product, not exit gates for a production work package.

## 16. Architectural boundaries

The game represents a civilization through explicit, inspectable models. It does not claim to discover the universally best society, predict human history in full, or convert all human experiences into scalar measurements.

The chosen architecture is local and single-player. The shared vocabulary permits rich regions, institutions, groups, and external relationships without requiring a multiplayer service, a persistent cloud world, or billions of individual agents. Those are different product architectures.

The technical specification defines how this whole-game design is represented, computed, stored, exposed, and extended. Specific equations and content remain model definitions governed by that architecture; they are not the organizing scope of these two documents.
