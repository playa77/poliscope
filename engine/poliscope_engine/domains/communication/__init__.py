"""Pure finite delivery/verification prerequisites over one canonical account book."""
from poliscope_engine.accounts import AccountBook, fail, index, quantity
from poliscope_engine.allocations import allocate
from poliscope_engine.contracts.allocations import AllocationChoice, AllocationRequest, FundingRequirement
from poliscope_engine.contracts.communication import CommunicationRequest, CommunicationEvaluation, MessageReadiness


def evaluate_communication(request, *, graph, units):
    request = CommunicationRequest.model_validate_json(request.model_dump_json())
    entities = {e.id: e for e in graph.registry.entities}
    scopes = {s.id: s for s in graph.registry.scopes}
    relationships = {r.id: r for r in graph.relationships}
    if request.scope_id not in scopes or scopes[request.scope_id].scope_kind not in ('settlement', 'region'):
        fail('invalid_communication_scope')
    accounts, claims = index(request.batch.accounts), index(request.batch.claims)
    channels = {c.asset_id: c for c in request.channels}
    demands = {d.claim_id: d for d in request.demands}
    channel_accounts = [c.account_id for c in request.channels]
    verification_accounts = {d.verification_account_id for d in request.demands if d.verification_account_id is not None}
    if (len(channels) != len(request.channels) or len(channel_accounts) != len(set(channel_accounts))
            or set(channel_accounts) & verification_accounts
            or set(channel_accounts) | verification_accounts != set(accounts)):
        fail('duplicate_or_unmapped_communication_capacity')
    if len(demands) != len(request.demands) or set(demands) != set(claims):
        fail('invalid_communication_demands')

    def entity(eid, kinds):
        if eid not in entities or entities[eid].entity_kind not in kinds:
            fail('invalid_communication_entity')

    for channel in request.channels:
        entity(channel.asset_id, ('asset',))
        entity(channel.controller_id, ('institution',))
        rel = relationships.get(channel.ownership_relationship_id)
        if (rel is None or rel.relationship_kind != 'ownership'
                or rel.from_id != channel.controller_id or rel.to_id != channel.asset_id):
            fail('invalid_communication_control')
    for account in accounts.values():
        if (account.kind != 'capacity' or account.invariant != 'budget'
                or account.scope_id != request.scope_id or account.period_id != request.period_id
                or units.unit(account.unit_id).dimension != (('message_slot', 1),)):
            fail('invalid_communication_capacity')
    if len({a.unit_id for a in accounts.values()}) != 1:
        fail('incompatible_communication_units')

    choices, findings_by_claim = [], {}
    for demand in request.demands:
        claim = claims[demand.claim_id]
        channel = channels.get(demand.channel_asset_id)
        entity(demand.sender_id, ('institution', 'population_cohort'))
        entity(demand.recipient_id, ('institution', 'population_cohort'))
        if (channel is None or claim.account_id != channel.account_id
                or claim.claimant_id != demand.recipient_id or quantity(claim.requested) <= 0):
            fail('invalid_communication_claim')
        if (demand.verification_account_id is None) != (demand.verification_procedure_ref is None):
            fail('incomplete_communication_verification')
        reachable = demand.channel_relationship_id is not None
        if reachable:
            rel = relationships.get(demand.channel_relationship_id)
            if (rel is None or rel.relationship_kind != 'information_channel'
                    or rel.from_id != demand.sender_id or rel.to_id != demand.recipient_id):
                fail('invalid_communication_reach')
        findings = [] if reachable else ['no_declared_channel_reach']
        unknown = False
        for name, value in [('recorded', demand.recorded), ('available', demand.available)]:
            if value is None:
                unknown = True; findings.append('unknown_' + name)
            elif not value:
                findings.append('not_' + name)
        for name, value in [('publish_access', demand.publish_access),
                            ('receive_access', demand.receive_access), ('disclosure', demand.disclosure)]:
            if value == 'unknown':
                unknown = True; findings.append('unknown_' + name)
            elif value == 'denied':
                findings.append(name + '_denied')
        if channel.availability == 'unknown':
            unknown = True; findings.append('unknown_channel_availability')
        elif channel.availability == 'offline':
            findings.append('channel_offline')
        if demand.delay_ticks is None:
            unknown = True; findings.append('unknown_delay')
        findings_by_claim[demand.claim_id] = findings
        choices.append(AllocationChoice(claim_id=claim.id,
            access='unknown' if unknown else 'denied' if findings else 'allowed',
            access_limit=demand.access_limit, funding_known=True,
            requirements=[] if demand.verification_account_id is None else [FundingRequirement(
                account_id=demand.verification_account_id, per_unit='1', kind='funding')],
            outputs=[], loss_per_unit='0', mechanism_ref=request.mechanism_ref, source_refs=demand.source_refs))
    initial = AccountBook(request.batch, units).evaluate()
    prior = {r.claim_id: r.actual for r in initial.claims}
    allocation = allocate(AllocationRequest(contract_version=1, batch=request.batch,
        procedure=request.procedure, claim_order=request.claim_order, choices=choices,
        mechanism_ref=request.mechanism_ref, source_refs=request.source_refs), units)
    actuals = {a.claim_id: a for a in allocation.actuals}
    results = []
    for demand in request.demands:
        actual = actuals[demand.claim_id]
        findings = list(findings_by_claim[demand.claim_id])
        unresolved = allocation.status == 'unresolved'
        if unresolved:
            findings.append('unknown_capacity_allocation')
        elif quantity(actual.unmet) > 0 and not findings:
            findings.append('capacity_shortfall')
        results.append(MessageReadiness(claim_id=demand.claim_id,
            outcome='unresolved' if unresolved else 'blocked' if findings else 'capacity_ready',
            findings=findings, prior=prior[demand.claim_id],
            additional=None if unresolved else actual.allocated, unmet=None if unresolved else actual.unmet))
    return CommunicationEvaluation(contract_version=1, evidence_status='hypothetical',
        status=allocation.status, request=request, allocation=allocation, results=results)
