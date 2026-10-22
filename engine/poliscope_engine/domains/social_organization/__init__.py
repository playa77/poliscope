"""Pure care evidence over canonical membership and the shared DOM-02 allocator."""
from poliscope_engine.accounts import fail, index
from poliscope_engine.contracts.social_organization import (
    CareRequest, CareEvaluation, ArrangementPopulation, CareResult,
)
from poliscope_engine.contracts.world import UnknownValue, QuantityValue
from poliscope_engine.domains.economy.exploration import report
from poliscope_engine.numeric import parse


def evaluate_care(request, *, graph, units):
    request = CareRequest.model_validate_json(request.model_dump_json())
    entities = {e.id: e for e in graph.registry.entities}
    scopes = {s.id: s for s in graph.registry.scopes}
    if request.scope_id not in scopes or scopes[request.scope_id].scope_kind not in ('settlement', 'region'):
        fail('invalid_care_scope')
    arrangements = index(request.arrangements)
    if len({a.scope_id for a in request.arrangements}) != len(arrangements):
        fail('duplicate_arrangement_scope')
    memberships = {}
    for arrangement in request.arrangements:
        entity, scope = entities.get(arrangement.id), scopes.get(arrangement.scope_id)
        expected = {'household': 'household_arrangement', 'community': 'community_arrangement'}
        if entity is None or scope is None or entity.entity_kind != expected.get(scope.scope_kind):
            fail('invalid_social_arrangement')
        memberships[arrangement.id] = {
            r.from_id for r in graph.relationships if r.relationship_kind == 'cohort_membership'
            and r.to_id == arrangement.scope_id}
        # Do not silently count non-cohort resources as people.
        if any(r.to_id == arrangement.scope_id and r.aggregation.kind != 'non_aggregating'
               and r.relationship_kind != 'cohort_membership' for r in graph.relationships):
            fail('invalid_arrangement_population')
    selected_members = set().union(*memberships.values())
    for value in graph.registry.values:
        if (value.entity_id in selected_members
                and value.property_id == request.population_property_id
                and value.partition == request.population_partition
                and isinstance(value.value, QuantityValue)):
            _validate_population(value.value, units)
    claims, accounts = index(request.work.batch.claims), index(request.work.batch.accounts)
    activities = {a.claim_id: a for a in request.work.activities}
    # The invocation shares one scope and period. No local procedure may allocate
    # another scope's time or silently introduce a second cohort budget.
    for claim in claims.values():
        account = accounts.get(claim.account_id)
        cohort = entities.get(claim.claimant_id)
        if account is None or account.scope_id != request.scope_id:
            fail('incompatible_care_work_scope')
        if cohort is None or cohort.entity_kind != 'population_cohort':
            fail('invalid_care_worker')
    index(request.obligations)
    work_ids = set()
    for duty in request.obligations:
        members = memberships.get(duty.arrangement_id, set())
        provider = entities.get(duty.provider_id)
        if duty.beneficiary_id not in members or provider is None or provider.entity_kind != 'population_cohort':
            fail('invalid_care_participants')
        if duty.authority_id is not None:
            authority = entities.get(duty.authority_id)
            if authority is None or authority.entity_kind != 'institution' or not any(
                r.relationship_kind == 'jurisdiction' and r.from_id == duty.authority_id
                and r.to_id in (request.scope_id, duty.beneficiary_id)
                for r in graph.relationships):
                fail('invalid_care_authority')
        claim, activity = claims.get(duty.claim_id), activities.get(duty.claim_id)
        if duty.claim_id in work_ids:
            fail('duplicate_care_work')
        work_ids.add(duty.claim_id)
        if (claim is None or activity is None or activity.kind != 'care'
                or claim.claimant_id != duty.provider_id or parse(claim.requested) <= 0):
            fail('invalid_care_claim')
    # Every care claim must have a beneficiary rather than disappearing in a
    # provider-only total. Other work categories remain visible in the report.
    if {a.claim_id for a in request.work.activities if a.kind == 'care'} != work_ids:
        fail('unmapped_care_claim')
    def population(scope_ids):
        value = graph.aggregate(scope_ids, property_id=request.population_property_id,
                                partition=request.population_partition)
        if isinstance(value, QuantityValue):
            _validate_population(value, units)
        return value
    rows = [ArrangementPopulation(arrangement_id=a.id, population=population([a.scope_id]))
            for a in request.arrangements]
    union = population([a.scope_id for a in request.arrangements])
    work = report(request.work, units)
    indicators = {i.claim_id: i for i in work.indicators}
    results = []
    for duty in request.obligations:
        indicator = indicators[duty.claim_id]
        results.append(CareResult(obligation_id=duty.id, beneficiary_id=duty.beneficiary_id,
            provider_id=duty.provider_id, claim_id=duty.claim_id, status=work.status,
            requested=indicator.requested, unit_id=indicator.unit_id, period_id=request.work.period_id,
            actual_before=indicator.actual_before, actual=indicator.actual, unmet=indicator.unmet, posting_ids=indicator.posting_ids))
    return CareEvaluation(contract_version=1,
        status='unresolved' if isinstance(union, UnknownValue) or work.status != 'resolved' else 'resolved',
        evidence_status='hypothetical', request=request, population=union,
        arrangements=rows, results=results, work=work)


def _validate_population(value, units):
    unit = units.unit(value.unit_id)
    if (unit.kind != 'count' or unit.dimension != (('population', 1),)
            or parse(value.value) < 0 or value.time_basis_id is not None
            or value.denominator_scope_id is not None):
        fail('invalid_arrangement_population')
