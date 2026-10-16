# Poliscope — Twelve-Domain Work Packages

All domain packages are **not started**. Parent plan: [implementation roadmap](../implementation_roadmap.md); dependencies refer to the [shared package register](work_packages.md). Validation scenarios and source-section coverage are in the [verification matrix](verification_matrix.md).

## 1. Domain delivery contract

The domain classification and state/interface responsibilities come from D §§4–5 and T §5. The candidate mechanism slices and fixtures below are proposed implementation scope, not claims of established social science. Choose parameters and empirical claims only through WP-026's evidence/model review. Synthetic fixtures are labeled hypothetical and independently derived. No package may invent universal scalar judgments for a domain.

Every package is size **L**, owned by a MODEL engineer and an ENG counterpart, with PRODUCT reviewing interviews and an independent MODEL/QA reviewer accepting claims/tests. Split into child issues before implementation; retain the parent's shared integration gate. The same person may implement several modules, but cannot replace independent evidence review with self-certification.

**Common start prerequisites:** WP-027 and its transitive dependencies, including world, units, registry, shared accounts, evidence packs and the headless slice. Domain content inventory can be prepared earlier through WP-025/WP-026. Each package's counterpart list below is an **integration acceptance dependency**, not a prerequisite to begin coding: domains can develop against the common harness, then test paired behavior together. This explicitly avoids circular start dependencies between naturally coupled domains.

**Two acceptance stages:**

- **Static/design acceptance (M3):** owned definitions, scoped interviews/options, reviewed executable mechanism/procedure, shared account/relationship interfaces, complete trace/evidence links, branch-level coverage inventory, independent positive/shortage/missing/conflict fixtures, and cross-domain counterpart checks. Implement at least one substantive mechanism per domain; schema registration or decorative prose alone is insufficient.
- **Dynamic acceptance (M4):** complete each selected model's declared transition behavior using WP-033–WP-036, with invariant/replay/checkpoint/cancellation fixtures. Mark unsupported transitions as gaps, not invented delays/effects. A domain may pass its static gate while its parent remains in progress until the dynamic stage finishes. WP-055 requires all parent packages verified.

**Required outputs per domain:** code under `engine/domains/<module>/`, versioned content/evidence definitions under `content/`, source/branch coverage inventory, reviewed mechanism cards, declared ports/state ownership, traces/diagnostics/indicator definitions, domain and paired integration tests, and contribution/limitations notes. Use shared UI components; a domain does not receive a separate renderer engine or database.

**Coverage inventory rule:** WP-025 inventories the actual source map's three levels. Every branch and relevant source decision receives a namespaced catalog entry or an explicit provenance-only/exclusion classification with rationale. Each candidate effect lists numerical/procedural/qualitative/partial/unsupported status, evidence status, supported scopes, static/transition availability, and next research task. All-branch catalog coverage is not all-branch numerical implementation. DEC-04 fixes the released mechanism inventory before scope is claimed complete.

All packages must demonstrate at least two relevant scopes/local groups and a boundary or overlap case; not every mechanism must claim applicability at every scope. Unsupported scopes are explicit. Paired fixtures reference shared entity/account IDs and verify finite budgets globally. Default civic answers remain unset, including choices imported from the historical source.

## 2. Domain packages

### DOM-01 — I. Resource & Material Base (`provisioning`)

**Branch scope:** production; distribution/logistics; consumption, waste and circular loops. **Sources:** D §§4, 5.2, 5.4; T §§5, 7.4. **Integration counterparts:** DOM-02, DOM-05, DOM-08, DOM-10, DOM-12.

**Work breakdown:**

1. Inventory resource types, production/transformation alternatives, logistics, storage, use and recycling claims. Declare ownership of provisioning-specific transformation/movement definitions while referencing canonical stock/asset/population IDs.
2. Implement a finite production → movement/storage → access-conditioned use chain with explicit inputs, yields, by-products, losses, throughput, labor/land/energy claims and finite external transfers. Allocation/access rules come from the selected economy/institutional mechanism, not an implicit provisioning winner.
3. Author scoped interview alternatives, account/flow traces, supply/claim/actual/unmet diagnostics and local distribution views. A physical shortfall differs from insufficient rights/access or missing delivery capacity.
4. Add selected replenishment, consumption, storage loss and circular-return transitions, with time basis and boundary conditions. Track extraction/waste through environment interfaces; do not create free recovered stock or unlimited imports.

**Static acceptance:** independent fixtures prove `opening + inflows = closing + outflows + losses`, yield/residual correctness, single reservation deduction and shared labor contention. A distant surplus with no throughput cannot satisfy a local claim; an access-denied group can lack food while aggregate food exists.

**Dynamic acceptance:** production/delivery/use boundaries conserve stock across checkpoint replay; pause/cancel cannot commit half a movement. Recycling returns only declared yields; seasonal/daily schedules cannot double-spend the same supply. Missing production or logistics models remain visible gaps.

### DOM-02 — II. Economy & Exchange (`economy`)

**Branch scope:** value/exchange; labor/work; ownership/property; wealth distribution. **Sources:** D §§4, 5.1–5.2; T §§5, 7.4. **Integration counterparts:** DOM-01, DOM-03, DOM-04, DOM-05, DOM-06, DOM-07, DOM-08.

**Work breakdown:**

1. Define ownership/access relationships, entitlements/transaction ledgers, work assignment and distribution interfaces. Preserve paid/unpaid work, employment, care and participation distinctions; currency does not automatically convert to goods.
2. Implement a selected explicit allocation/exchange procedure and labor/time assignment under finite shared budgets, with typed obligations, eligibility, transaction terms and declared precedence. At least two scoped alternatives must preview different access/distribution, not merely different labels.
3. Author ownership/exchange/work interviews and quantity/distribution views where definitions justify them; show totals and cohort/local outcomes, unsupported behavioral responses and assumptions.
4. Add selected transaction/entitlement settlement and work/service allocation transitions. Define each account's balancing invariant; do not impose physical conservation on every monetary/social quantity or assume funding creates physical capacity.

**Static acceptance:** stock exists but a group lacks entitlement; different declared access procedures allocate the same fixed stock differently without changing total supply. Work/care/training demands compete for one population/time budget. Unspecified allocation precedence yields conflict/unresolved status.

**Dynamic acceptance:** settlement and recurring allocation honor dated rights/rules and retain audit traces; no double settlement on replay/retry. Policy changes have explicit effective times; unmodeled price/behavior responses remain qualitative rather than automatic market equilibrium claims.

### DOM-03 — III. Governance & Collective Decision-Making (`governance`)

**Branch scope:** political structure; decision processes; power/accountability. **Sources:** D §§4, 5.3; T §§4.2, 5.2. **Integration counterparts:** DOM-02, DOM-04, DOM-06, DOM-09, DOM-11, DOM-12.

**Work breakdown:**

1. Define actors/roles, representation, jurisdiction, delegation, authority, oversight, publication obligations and administrative capacity referencing shared institutions/cohorts.
2. Implement a selected procedural decision mechanism with eligibility/quorum or other declared rules, stages, capacity/time requirements, decision outcome and audit trail. These are explicit institutional procedures, not a global legitimacy formula.
3. Author alternatives and previews exposing who can decide, who is represented, administrative demands and overlapping authority. Support explicit exclusivity/composition/delegation/floor/ceiling semantics through WP-013.
4. Add modeled queue/stage/adoption/publication transitions, including delayed/blocked procedures and resource demands. Distinguish a player's design selection from an institution's modeled decision-making process.

**Static acceptance:** overlapping jurisdiction or incompatible policy bindings yield a named institutional conflict until a declared resolution applies; file/ID order never chooses the authority. Representation/eligibility procedures match independent examples and administrative claims share labor/capacity with other services.

**Dynamic acceptance:** a delayed procedure does not take effect early or conjure capacity; event ordering/replay preserves the same stage/outcome. Disclosure delay can interact with communication, oversight and risk response without inventing behavioral legitimacy effects.

### DOM-04 — IV. Law, Order & Conflict Resolution (`law_conflict`)

**Branch scope:** norms/rights; enforcement; dispute resolution; inter-group conflict. **Sources:** D §§4, 5.3; T §5. **Integration counterparts:** DOM-02, DOM-03, DOM-05, DOM-07, DOM-09, DOM-11, DOM-12.

**Work breakdown:**

1. Define explicit rights/duties/claims, eligibility, agreement terms, adjudication and enforcement procedures, case capacity and external interfaces. Keep legal entitlement separate from available supply and actual service.
2. Implement a scoped claim/adjudication procedure with queue/capacity, authority reference, declared resolution and obligations; model unresolved cases and incompatible rights as findings. No automatic enforcement or universal fairness score.
3. Author interviews/options and trace rights → claimant/group → responsible institution → service/case capacity → result or unresolved condition. Represent external agreements with explicit counterparty behavior/limits.
4. Add selected case arrival/processing/enforcement and dated agreement transitions. Requirements without mechanisms remain qualitative; conflict does not terminate or automatically redesign the sandbox.

**Static acceptance:** an eligible claimant with no available service retains both the right and the unmet claim. Adjudication cannot process more cases than declared capacity; conflicting authority remains explicit. Independent procedural fixtures verify outcome/rationale and group distribution.

**Dynamic acceptance:** cases/revisions/obligations persist across checkpoint replay and approved effective changes; pending cases are not erased by policy switches. Unspecified external enforcement cannot become guaranteed delivery or rescue.

### DOM-05 — V. Social Organization & Relationships (`social_organization`)

**Branch scope:** households/kinship; community; life-course and care. **Sources:** D §§3.1, 4, 5.1; T §§4–5. **Integration counterparts:** DOM-01, DOM-02, DOM-04, DOM-06, DOM-07, DOM-11.

**Work breakdown:**

1. Define cohort/household/community membership, aggregate arrangement counts, care obligations, participation and life-course needs using canonical population identities and explicit overlap weights/partitions.
2. Implement a care/participation arrangement that creates demand and allocates finite shared time/services, with access rules and institutional obligations. No requirement for individually simulated people.
3. Author interviews and previews for household/community arrangements with group-level impacts, unpaid-work definitions and missing behavioral assumptions. Do not infer family/belonging quality from a universal scalar.
4. Add selected care/time schedules and cohort/household arrangement transitions under declared population accounting. Demographic assumptions must agree with the selected population role and health models.

**Static acceptance:** one cohort shared by several community networks is counted once in civilization population and time supply. Care, employment and learning compete for the same represented time budget; a declared care obligation can remain unmet and is inspectable by affected group.

**Dynamic acceptance:** changing an arrangement updates obligations/membership coherently at its declared boundary without duplicating people or capacity. Cohort/household transitions replay identically; missing migration/life-course behavior is labeled instead of fabricated.

### DOM-06 — VI. Knowledge, Education & Culture (`knowledge_culture`)

**Branch scope:** research/archives; education/training; cultural production. **Sources:** D §§4, 5.5, 5.7; T §5. **Integration counterparts:** all other domains for the D §5.7 integration path; primary service interfaces DOM-02, DOM-03, DOM-05, DOM-08, DOM-09, DOM-11.

**Work breakdown:**

1. Define learning/research/cultural services, participation/access, archives/knowledge references, training/skill stocks and technology assumptions. Evidence for learning or research outcomes is distinct from capacity arithmetic.
2. Implement an education/training service mechanism with participants, trained staff, facilities, time/supplies, eligibility/access and governance authority. Preserve simultaneous staff/student/care demands through shared cohort budgets.
3. Author alternatives and trace participation/capacity/coverage plus cultural/research commitments. Start from explicit inputs; no automatic technology advance or broad civilization-improvement multiplier.
4. Add selected completion/skill-stock/service-schedule transitions with delays and attrition only where defined and reviewed; preserve archives/access and communication/privacy obligations.

**Static acceptance:** the education integration fixture follows the same people/assets/accounts through provisioning, economy, care, health, authority/rights, information, ecology, identity and risk. Staffing or facility shortages constrain service, while unsupported learning/social effects remain explicit.

**Dynamic acceptance:** declared training duration cannot complete instantly; skills/capacity changes occur once at the defined boundary and replay from checkpoints. Unmodeled research/cultural effects remain qualitative without preventing service/account inspection.

### DOM-07 — VII. Health & Wellbeing (`health`)

**Branch scope:** physical health; mental/emotional wellbeing; birth, life, death and care. **Sources:** D §§4–5; T §§4.3, 5. **Integration counterparts:** DOM-01, DOM-02, DOM-04, DOM-05, DOM-06, DOM-08, DOM-09, DOM-10, DOM-12.

**Work breakdown:**

1. Define cohort-specific needs, eligibility/access, health/care services, trained capacity, exposure references and selected population/health state. Distinguish health indicators from universal wellbeing judgments.
2. Implement finite service capacity and care-demand allocation with supplies, facilities, staff/time and access rules. Show unmet need and coverage by group/location, separately from legal rights and physical stock.
3. Review any health/exposure/demographic or behavioral transition for operational definition, time scale, affected population, evidence and uncertainty. Mental/emotional effects may remain qualitative; no invented happiness coefficient.
4. Add only selected reviewed care/health/population transitions; coordinate births/deaths/migration with canonical cohort identities and population role so static input and dynamic population are not simultaneously assumed.

**Static acceptance:** aggregate staffed capacity can coexist with a locally inaccessible group; entitlement does not create actual treatment capacity. Independent fixtures check demand denominators, cohort totals and competing staff/time/supplies.

**Dynamic acceptance:** selected transitions remain bounded and reconcile population/services exactly as their model states, with explicit exposure timing and replay. Unavailable health/demographic models return coverage gaps rather than claimed causal forecasts.

### DOM-08 — VIII. Infrastructure & Built Environment (`infrastructure`)

**Branch scope:** physical infrastructure; spatial organization; digital infrastructure. **Sources:** D §§4, 5.4; T §§4–5, 8. **Integration counterparts:** DOM-01, DOM-02, DOM-03, DOM-06, DOM-07, DOM-09, DOM-10, DOM-12.

**Work breakdown:**

1. Define assets/networks, location/connectivity, housing/service reach, finite capacity, operating requirements and lifecycle states. Other domains reference these assets; they do not clone capacity.
2. Implement a selected network/facility capacity and reachability mechanism with throughput/availability, resource/labor/land claims and explicit access interfaces. Topology is explanatory and inspectable without mandatory terrain construction.
3. Author construction/maintenance/access alternatives and previews of actual service reach, local bottlenecks, obligation and ecological claims. Keep a planned asset distinct from available operating capacity.
4. Add declared construction, commissioning, maintenance/degradation, repair and retirement transitions, with time/resource requirements and risk exposure; missing lifecycle behavior is a coverage gap.

**Static acceptance:** a surplus service cannot cross a disconnected or undersized link; a facility ID supplies finite capacity once to competing domains. Housing/service quantities have dimensions and group/location denominators, and diagrams/tables show the same topology.

**Dynamic acceptance:** construction does not supply capacity before modeled completion; maintenance/repair competes for shared stock/labor and replay preserves lifecycle state. Hazard damage cannot be reversed by automatic unmodeled repair.

### DOM-09 — IX. Communication & Information (`communication`)

**Branch scope:** information flow/verification; communication; mediated information and privacy. **Sources:** D §§4, 5.5; T §5. **Integration counterparts:** DOM-03, DOM-04, DOM-06, DOM-07, DOM-08, DOM-11, DOM-12.

**Work breakdown:**

1. Define channels, access/control, finite communication/service capacity, verification procedures, disclosure obligations, privacy rules and modeled information delay with shared asset/institution references.
2. Implement a scoped publication/access/verification procedure and capacity/delay accounting. Distinguish information recorded, available, delivered and verified; no automatic “truth” or social trust score.
3. Author alternatives showing who can receive/publish, supporting capacity and institutional obligations. Keep simulated societal privacy rules distinct from the desktop application's mandatory key/data protections.
4. Add modeled delivery/disclosure/queue transitions and interaction with governance, education/health messaging and response. Unsupported persuasion, misinformation or behavior effects remain hypotheses.

**Static acceptance:** eligibility and channel reach can differ; claimed publication without delivery/verification capacity remains incomplete. Two domains compete for the same represented channel capacity; sources/explanations distinguish documentary influence from numerical dependence.

**Dynamic acceptance:** declared delay affects institutional/response timing through explicit ports, not a global communication multiplier. Replay preserves delivery states and privacy/access rules; a policy change cannot expose actual application secrets or share player data.

### DOM-10 — X. Environment & Human–Nature Relationship (`environment`)

**Branch scope:** stewardship; resource sustainability; land/ecosystem relations. **Sources:** D §§4, 5.4; T §§5, 7.4. **Integration counterparts:** DOM-01, DOM-06, DOM-07, DOM-08, DOM-12.

**Work breakdown:**

1. Define ecological stocks/flows, land claims, regeneration, extraction/emissions/waste sinks, exposure and finite boundary interfaces. A watershed can overlap jurisdictions without duplicating its physical accounts.
2. Implement selected resource/sink accounting and explicit regenerative or exposure rules only where reviewed. Keep physical constraints, uncertain capacity estimates and selected ecological policy commitments separate.
3. Author alternatives, conservation/constraint diagnostics and source/assumption traces with local distributions. No universal morality or environment-success score; neutral quantities remain neutral where no defensible direction exists.
4. Add reviewed regeneration/accumulation/seasonal and land/lifecycle transitions, linked to production/infrastructure/health/risk timing. Unknown sink/regeneration capacity does not mean unlimited absorption or zero impact.

**Static acceptance:** extraction/emissions reference the same physical stocks/sinks across regions; weighted scope views cannot spend them twice. Independent units/time/area fixtures verify accounting; a chosen limit breach is distinct from a physical shortage or uncertain boundary.

**Dynamic acceptance:** inflow/extraction/regeneration/loss transitions reconcile at defined time steps and retain uncertainty/coverage. Source ranges are not sampled without declared distributions; checkpoint replay preserves shared ecological state.

### DOM-11 — XI. Meaning, Values & Identity (`meaning_identity`)

**Branch scope:** belief; identity/belonging; purpose, ritual and aspiration. **Sources:** D §§4, 5.5; T §§5, 9. **Integration counterparts:** DOM-03, DOM-04, DOM-05, DOM-06, DOM-09.

**Work breakdown:**

1. Define declared commitments, affiliations/membership, participation and accommodation rules with explicit scope and provenance. Keep societal commitments distinct from player goals and source-project ideology.
2. Implement a substantive accommodation/participation procedure: eligible groups, institution/authority, requested space/time/service, access rule, finite capacity and unresolved conflicting obligations. Quantify actual service/participation capacity only where meaningful, not belief quality.
3. Author belief/belonging/cultural alternatives and qualitative tensions with full evidence/coverage labels. No legitimacy, cohesion, purpose or identity scalar is introduced without a defensible explicitly selected model; unmodeled effects stay qualitative.
4. Add selected participation schedules, accommodation queue or membership-rule effective changes. Changes must respect canonical groups, rights, cultural services and communication/access rules without pretending to simulate inner experience.

**Static acceptance:** two groups with different accommodation needs can share institutions/resources and generate inspectable capacity/rights conflicts. The procedure produces executable eligibility/obligation results; catalog text alone does not pass. Neither player goals nor inherited source commitments silently alter world state.

**Dynamic acceptance:** dated accommodation/participation rules update obligations once, with deterministic schedule/replay and explicit unavailable effects. Editing an aspiration cannot produce stock, hazard, health or behavioral changes unless a reviewed mechanism explicitly supplies the link.

### DOM-12 — XII. Security & Risk Management (`security_risk`)

**Branch scope:** physical security; systemic risk; technological risk. **Sources:** D §§4, 5.6, 6.2; T §§5, 7.5, 8. **Integration counterparts:** all domains with exposed capacity or obligations; primary fixtures DOM-01, DOM-03, DOM-07, DOM-08, DOM-09, DOM-10.

**Work breakdown:**

1. Define hazards/events, exposure, preparedness/prevention, continuity/response, dependencies and finite external aid assumptions. Events are authored or come from explicitly selected stochastic distributions, never a compulsory disaster progression.
2. Implement a selected continuity/response-capacity mechanism with reserve, staff/asset/service claims, authority and disclosure requirements. Preserve distinct physical vulnerability, institutional delay, unmet response and qualitative risk hypotheses.
3. Author alternatives and traces showing whose capacity/obligations are affected and by which assumptions. Technological risk includes unsupported-effect status rather than fabricated precise probabilities.
4. Add deterministic disruption/response schedules and registered stochastic hazards through WP-035's isolated streams. Coordinate damage/repair/health/logistics updates through the common reducer; no automatic rescue or game over.

**Static acceptance:** preparedness reserves are deducted once and compete with ordinary service demands; external help remains finite/conditional. Exposure/continuity findings have defined scope/time/evidence and no universal security score.

**Dynamic acceptance:** the same realization replays across checkpoint/resume, unrelated module changes do not shift its random stream, and a disruption produces consistent coupled service/resource/authority findings. Failure leaves the design playable; unmodeled recovery remains an unresolved requirement.

## 3. Cross-domain integration ownership

| Integrated fixture | Coordinating packages | Minimum shared behavior and failure case |
|---|---|---|
| Finite goods, labor, access and delivery | DOM-01/02/05/08/10; WP-015/032 | One population/time/stock/asset identity; local unmet claim survives aggregate surplus; no free external supply |
| Education relationship path | DOM-06 and every other domain; WP-032 | All-domain requirements traced through actual mechanism/procedural/qualitative links; incomplete human effects are not invented |
| Authority, rights and accommodation | DOM-03/04/09/11 with DOM-05/06; WP-013/032 | Overlapping authority, eligible but unserved group, disclosure/privacy and explicit unresolved conflict |
| Health/care/environmental exposure | DOM-05/07/10 with DOM-01/08; WP-034/055 | Cohort demand, care time, service capacity and exposure agree at each declared boundary |
| Disruption and continuity | DOM-12 with all affected domains; WP-035/036/055 | Resource, institution, channel, asset and health effects commit atomically; replay/repair demands conserve shared budgets |
| Local scope and overlap | Every domain; WP-007/027/030 | At least two groups/scopes with weighted membership/jurisdiction overlap; no population or stock duplication |

An integration fixture fails if interfaces merely exchange plausible-looking UI values while their underlying entity identities, revisions, units, assumptions or accounts disagree. WP-032 owns the static all-domain gate; WP-034/WP-036 plus WP-055 own dynamic and release acceptance. Model gaps may be legitimate, but each release's declared inventory must show them explicitly and still satisfy substantive executable behavior in every domain.
