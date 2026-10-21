"""Contextual authored templates and constrained changes into production revisions.

All prose is data. Templates use the shared Definition contract; they do not
register mechanisms or assert social effects. Full source/option definitions are
archived as approved design content in every alternative's typed value.
"""
import json
import os
import tempfile
from pathlib import Path
from poliscope_engine.contracts.interview import InterviewQuery, InterviewQuestion, InterviewEdit, InterviewPreview, InterviewCommit
from poliscope_engine.contracts.packs import Definition
from poliscope_engine.contracts.revisions import PreviewRequest, ApplyRequest
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.numeric import parse
from poliscope_engine.revisions import RevisionError
from poliscope_engine.workspace import select, DOMAIN_NAMES, PROVENANCE

# Original synthetic questions, not imported historical civic decisions.
TOPICS = (
    ('Materials in a settlement', 'Households and shared facilities need materials, but their quantities and access are still unanswered. How should people describe the arrangement they want to explore?',
     ('Household provisioning', 'Shared provisioning', 'Mixed provisioning')),
    ('Exchange and access', 'People need a way to obtain goods when their needs and contributions differ. Which access arrangement would you like to explore?',
     ('Direct exchange', 'Common provision', 'Mixed access')),
    ('Collective decisions', 'A settlement faces a decision that affects people beyond one household. Who should take part in deciding it?',
     ('Assembly', 'Delegated council', 'Nested deliberation')),
    ('Dispute procedures', 'Two groups disagree about an obligation. What process should hear their accounts and revisit the outcome?',
     ('Mediation', 'Formal hearing', 'Staged resolution')),
    ('Care and relationships', 'Care responsibilities overlap with work and participation. How should people describe coordination across households?',
     ('Household networks', 'Shared care circles', 'Mixed coordination')),
    ('Learning arrangements', 'Learners need time, support and places to learn. Which arrangement should be explored while those capacities remain unspecified?',
     ('Community learning', 'Dedicated institutions', 'Mixed learning')),
    ('Health and wellbeing', 'People need care at different times and with different capabilities. What arrangement should be explored for coordinating access?',
     ('Local care teams', 'Shared care centers', 'Linked care network')),
    ('Infrastructure stewardship', 'Facilities need upkeep as well as construction. Who should coordinate maintenance and report unmet needs?',
     ('Local stewardship', 'Shared maintenance body', 'Layered stewardship')),
    ('Communication and information', 'People need reliable information while personal details may require protection. How should communication be organized?',
     ('Community channels', 'Shared information service', 'Federated channels')),
    ('Environmental commitments', 'A proposed activity may change land and resource use. How should people describe review of those effects?',
     ('Local review', 'Shared ecological review', 'Layered review')),
    ('Meaning and identity', 'People hold different beliefs and practices. How should shared activities make room for those differences?',
     ('Voluntary associations', 'Shared accommodation forum', 'Multiple overlapping forums')),
    ('Continuity and risk', 'A disruption can interrupt services that depend on one another. How should people coordinate preparation?',
     ('Local preparedness', 'Shared continuity team', 'Linked preparedness')),
)
PROCEDURES = (
    ('Households arrange their own material purchases and storage, and record unmet needs locally.',
     'Participants pool specified material requirements through a shared store with an agreed access procedure.',
     'Household stores coexist with a shared reserve; participants must define when requests cross between them.'),
    ('Participants negotiate exchanges directly and specify what happens when someone cannot offer a counterpart.',
     'A common provision process receives requests and assigns access under an explicitly agreed procedure.',
     'Direct exchanges coexist with a common provision channel; their boundaries and eligibility must be stated.'),
    ('Affected participants meet in an assembly and agree how proposals, objections and decisions are recorded.',
     'Participants delegate decisions to named representatives, with explicit authority, reporting and recall rules.',
     'Local groups deliberate first and send unresolved shared questions to a wider forum with defined authority.'),
    ('A mediator helps the parties seek an agreement; participation and routes after failed mediation must be defined.',
     'A designated hearing body receives evidence and issues a decision under stated rules and appeal procedures.',
     'Parties attempt mediation first and may move to a formal hearing; the handoff and authority need agreement.'),
    ('Households coordinate care through their own relationships, recording who can ask for help and who is excluded.',
     'A shared care circle coordinates requests and volunteers under agreed responsibility and safeguarding rules.',
     'Household support and shared care coexist, with an explicit route for needs that either cannot meet.'),
    ('Community members organize learning activities and define how learners find mentors and support.',
     'Dedicated learning institutions coordinate staff, participation and facilities under an explicit access procedure.',
     'Community learning and dedicated institutions share referrals while keeping their responsibilities explicit.'),
    ('Local care teams receive requests and define what they can handle and when they must seek additional support.',
     'Shared care centers coordinate staff and facilities, with explicit access and referral procedures.',
     'Local teams and shared centers agree referrals and continuity responsibilities across the network.'),
    ('Local stewards maintain named facilities and record inspections, repairs and needs they cannot meet.',
     'A shared maintenance body coordinates repair requests and workers under an agreed scheduling procedure.',
     'Local stewards handle specified tasks while a wider body handles shared assets and unresolved repairs.'),
    ('Community-run channels publish information under local editorial and personal-data rules.',
     'A shared information service publishes common records, with explicit correction and privacy procedures.',
     'Independent channels exchange designated records under agreed interoperability, correction and privacy rules.'),
    ('Local participants review a proposed activity and record affected places, uncertainties and objections.',
     'A shared ecological review body examines proposals across places under defined authority and evidence rules.',
     'Local and wider review bodies divide responsibilities and specify when a proposal must move between them.'),
    ('Voluntary associations organize practices and state how participation, exit and access to shared spaces work.',
     'A shared forum hears accommodation requests and records procedures for disagreement and revision.',
     'Several forums handle different practices, with an agreed route for overlapping claims and unresolved requests.'),
    ('Local groups document critical needs and available responses, including dependencies they cannot cover.',
     'A shared continuity team coordinates preparation and requests under explicit authority and resource limits.',
     'Local groups and shared teams maintain linked plans, with named handoffs when disruption crosses boundaries.'),
)
BENEFITS = (
    'May preserve direct participation and local knowledge; this is a hypothesis rather than an evaluated benefit.',
    'May make shared coordination and specialist responsibility easier; no improvement is numerically inferred.',
    'May connect local knowledge with shared coordination; compatibility and access remain hypotheses to examine.',
)
COSTS = (
    'Needs participant time and a route for unmet needs; local capability and exclusion remain unresolved.',
    'Needs staff, oversight and an access procedure; concentrated authority and limited capacity need examination.',
    'Needs coordination across boundaries and clear handoffs; overlapping responsibilities can remain unresolved.',
)
LIMIT = 'Qualitative model gap: no registered social or transition mechanism; no numerical benefits, costs or sufficiency are inferred.'


def definition(identity, kind, parent, text, origin='authored'):
    return Definition(id=identity, version='v1', kind=kind, parent_ref=parent,
        original_text=text, source_decision_id=None, source_refs=[], assumption_refs=[],
        supersedes_refs=[], mechanism_refs=[], variable_refs=[], origin=origin,
        modeling='qualitative', evidence='hypothetical', historical_status='unspecified')


def question(service, data):
    query = InterviewQuery.model_validate(data)
    if query.domain_id not in ['domain:' + str(i) for i in range(1, 13)] and not (query.domain_id == 'domain:all' and query.question_id is not None):
        raise ValueError('unknown_domain')
    record = service.read(query.context)
    if query.scope_id not in {s.id for s in record.inputs.scopes}:
        raise ValueError('unknown_scope')
    index = int(query.domain_id.split(':')[1]) - 1 if query.domain_id != 'domain:all' else 0
    from poliscope_engine.content import bundled_release
    template = next(t for t in bundled_release().metadata.templates
                    if t.domain_ref == f'society:domain/{index + 1:02}')
    if query.question_id is not None:
        from poliscope_engine.atlas import entries
        row = next((r for r in entries(service, record, query.scope_id) if r.question.id == query.question_id), None)
        if row is None or row.interview is None or row.interview.domain_id != query.domain_id:
            raise ValueError('unknown_question')
        # Reuse rich authored cards when available; imported prose remains data.
        cards = {o.id: dict(label=template.labels[n], benefit=template.benefits[n], cost=template.costs[n],
                           mechanism=template.mechanisms[n] + ' ' + template.coverage)
                 for n, o in enumerate(template.options)}
        options = [dict(definition=o, **cards.get(o.id, dict(label=o.id, benefit='Not evaluated',
                    cost='Source requirements are unreviewed', mechanism=LIMIT))) for o in row.options]
        prior = next((v.value.value for v in record.inputs.values if v.id == commitment_id(query) and v.value.kind == 'label'), None)
        return InterviewQuestion(interview_contract=1, query=query, definition=row.question, options=options,
            clarification='Source adoption is historical context. No source option is a player default. Preview before Apply. Numerical source claims are not activated models.',
            dependencies=row.issues[:12],
            conditions=[v for v in record.inputs.values if v.scope_id == query.scope_id and v.id in ('population:value', 'land:value')]
                if index == 0 and row.question.id == template.question.id else [], current_commitment=prior)
    options = [dict(definition=option, label=template.labels[n], benefit=template.benefits[n],
                    cost=template.costs[n], mechanism=template.mechanisms[n] + ' ' + template.coverage)
               for n, option in enumerate(template.options)]
    conditions = [v for v in record.inputs.values if v.scope_id == query.scope_id and v.id in ('population:value', 'land:value')] if index == 0 else []
    prior = next((v.value.value for v in record.inputs.values if v.id == commitment_id(query) and v.value.kind == 'label'), None)
    return InterviewQuestion(interview_contract=1, query=query,
        definition=template.question, options=options,
        clarification='These are original synthetic exploration templates. None is a default, recommendation or historical source choice. A card selects a draft; only Apply records it. Defer leaves the decision unanswered.',
        dependencies=[DOMAIN_NAMES[(index + 1) % 12] + ': capacities and procedures unresolved',
                      'Shared people, time, access and authority remain unspecified.'],
        conditions=conditions, current_commitment=prior)


def commitment_id(query):
    key = dict(scope=query.scope_id, domain=query.domain_id)
    if query.question_id is not None and not query.question_id.startswith('interview:domain-'):
        key['question'] = query.question_id
    return 'interview:' + digest(key)[:40]


def stage(service, data, identity):
    edit = InterviewEdit.model_validate(data)
    q = question(service, edit.query)
    options = list(q.options)
    is_proposal = edit.choice_id == 'player:proposal'
    if is_proposal:
        if not edit.proposal or not edit.proposal.strip():
            raise ValueError('empty_proposal')
        proposed = definition('player:proposal', 'option', q.definition.id, edit.proposal, 'player_proposed')
    elif edit.proposal is not None:
        raise ValueError('unexpected_proposal')
    if not is_proposal and edit.choice_id not in {o.definition.id for o in options}:
        raise ValueError('unknown_option')
    if edit.query.domain_id != 'domain:1' and (edit.population is not None or edit.land_area is not None):
        raise ValueError('unexpected_conditions')
    # Decimal rules remain entirely in Python. Null is explicitly unknown.
    for field, value in [('population', edit.population), ('land_area', edit.land_area)]:
        if value is not None:
            number = parse(value)
            if number < 0 or (field == 'population' and number != number.to_integral_value()):
                raise ValueError('invalid_condition')
    base = service.read(edit.query.context).inputs.model_dump(mode='json')
    domain_refs = ['society:domain/' + edit.query.domain_id.split(':')[1].zfill(2)]
    branch_refs = []
    if edit.query.question_id is not None:
        from poliscope_engine.atlas import entries
        location = next(r for r in entries(service, service.read(edit.query.context), edit.query.scope_id) if r.question.id == edit.query.question_id)
        domain_refs, branch_refs = location.domain_refs, location.branch_refs
    for condition in q.conditions:
        owner = next((o for o in base['owners'] if (o['entity_id'], o['property_id'], o['partition']) ==
                      (condition.entity_id, condition.property_id, condition.partition)), None)
        if owner is None or owner['writer_id'] != 'player':
            raise ValueError('condition_not_player_editable')
    cid = commitment_id(edit.query)
    from poliscope_engine.atlas import catalogs
    from poliscope_engine.content import bundled_release
    _, source_packs = catalogs(bundled_release())
    archived_sources = {s.reference.id: s.reference.model_dump(mode='json') for p in source_packs for s in p.sources}

    def changes(option):
        archived_options = {o.definition.id: o.definition.model_dump(mode='json') for o in q.options}
        archived_options[option.id] = option.model_dump(mode='json')
        inputs = json.loads(json.dumps(base))
        # Constrained host-authored structure edit. No arbitrary renderer graph.
        if not any(e['id'] == cid + ':entity' for e in inputs['entities']):
            inputs['entities'].append(dict(id=cid + ':entity', entity_kind='decision', label=TOPICS[int(edit.query.domain_id.split(':')[1])-1][0] if q.definition.id.startswith('interview:domain-') else q.definition.id, provenance=PROVENANCE))
            inputs['owners'].append(dict(entity_id=cid + ':entity', property_id='interview:commitment', partition='design', writer_id='player'))
        source_refs = set(q.definition.source_refs + [r for d in archived_options.values() for r in d['source_refs']])
        metadata = dict(archived_sources=[archived_sources[r] for r in sorted(source_refs) if r in archived_sources], question=q.definition.model_dump(mode='json'), option=option.model_dump(mode='json'),
                        scope_id=edit.query.scope_id, coverage=LIMIT, dependencies=q.dependencies,
                        options=list(archived_options.values()),
                        domain_refs=domain_refs, branch_refs=branch_refs,
                        card=next((dict(label=o.label, benefit=o.benefit, cost=o.cost, mechanism=o.mechanism) for o in q.options if o.definition.id == option.id),
                                  dict(label='Player qualitative alternative', benefit='Unreviewed proposal', cost='Unspecified requirements', mechanism=LIMIT)))
        value = dict(id=cid, entity_id=cid + ':entity', scope_id=edit.query.scope_id, partition='design', property_id='interview:commitment',
            effective_time=base['design']['effective_time'], provenance=PROVENANCE,
            value=dict(kind='label', value=json.dumps(metadata, separators=(',', ':'), ensure_ascii=False)))
        inputs['values'] = [v for v in inputs['values'] if v['id'] != cid] + [value]
        # A condition-only parameter variant can accompany any resource option.
        if edit.query.domain_id == 'domain:1':
            for original in q.conditions:
                row = next(v for v in inputs['values'] if v['id'] == original.id)
                token = edit.population if row['id'] == 'population:value' else edit.land_area
                unit = 'people' if row['id'] == 'population:value' else 'km2'
                row['value'] = dict(kind='unknown', reason='Starting condition unanswered') if token is None else dict(
                    kind='quantity', value=token, unit_id=unit, time_basis_id=None, denominator_scope_id=None)
                row['provenance'] = PROVENANCE
        return [dict(kind='replace_inputs', inputs=inputs)]

    alternatives = [dict(id=o.definition.id, changes=changes(o.definition)) for o in options if o.definition.id != 'player:proposal']
    if is_proposal:
        alternatives.append(dict(id='player:proposal', changes=changes(proposed)))
    chosen = next(a for a in alternatives if a['id'] == edit.choice_id)
    request = PreviewRequest.model_validate(dict(revision_contract=1, context=edit.query.context.model_dump(),
        changes=chosen['changes'], decision=dict(alternatives=alternatives, selected_id=edit.choice_id,
            rationale_ref=dict(id='rationale:' + digest(dict(identity=identity, text=edit.rationale)), visibility='private', status='available') if edit.rationale else None)))
    candidate = service.preview(request)
    after = candidate.request.changes[0].inputs
    projection = InterviewPreview(interview_contract=1, query=edit.query, candidate_digest=candidate.candidate_digest,
        affected_scope_ids=candidate.affected_scope_ids, changed_value_ids=candidate.changed_value_ids,
        coverage=LIMIT, findings=[f.category + ": " + f.status for f in candidate.report.findings][:99] + [LIMIT],
        dependencies=q.dependencies, accounts=[], alternatives=[a.id for a in request.decision.alternatives],
        selected_id=edit.choice_id, before=q.conditions,
        after=[v for v in after.values if v.id in {c.id for c in q.conditions}])
    return edit, request, candidate, projection


def save_rationale(directory, identity, edit):
    # Classified active private payloads are separate from immutable revisions,
    # operation bindings and accepted evidence. No user-controlled path segments.
    location = Path(directory) / 'private-interviews'
    location.mkdir(mode=0o700, exist_ok=True)
    path = location / (digest(identity).split(':', 1)[1] + '.json')
    payload = json.dumps(dict(classification='private', context=edit.query.context.model_dump(), text=edit.rationale), ensure_ascii=True).encode()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=location, prefix='.pending-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)  # Complete payload appears atomically; never overwrite.
        except FileExistsError:
            with path.open('rb') as stream:
                if stream.read(len(payload) + 1) != payload:
                    raise ValueError('private_payload_binding_mismatch')
        if os.name != 'nt':
            descriptor = os.open(location, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)



def apply(service, data, identity):
    # Reconstruct exact preview from immutable base. Completed operations replay
    # before stale-head checks, preserving the same identity across lost replies.
    if set(data) != {'edit', 'candidate_digest'}:
        raise ValueError('invalid_apply')
    edit, request, candidate, _ = stage(service, data['edit'], identity)
    if candidate.candidate_digest != data['candidate_digest']:
        raise ValueError('candidate_digest_mismatch')
    mutation = ApplyRequest(revision_contract=1, operation_id='interview:' + identity,
        preview=request, candidate_digest=candidate.candidate_digest)
    outcome = service.status('apply', mutation)
    if outcome is None:
        if service.branch(edit.query.context).context.revision_id != edit.query.context.revision_id:
            return InterviewCommit(interview_contract=1, status='stale', state=select(service, dict(
                civilization_id=edit.query.context.civilization_id, branch_id=edit.query.context.branch_id, revision_id=None)))
        if edit.rationale:
            save_rationale(service.store.path.parent, request.decision.rationale_ref.id, edit)
        try:
            outcome = service.apply(mutation)
        except RevisionError as error:
            if str(error) != 'stale_revision':
                raise
            return InterviewCommit(interview_contract=1, status='stale', state=select(service, dict(
                civilization_id=edit.query.context.civilization_id, branch_id=edit.query.context.branch_id, revision_id=None)))
    return InterviewCommit(interview_contract=1, status='applied', state=select(service, dict(
        civilization_id=outcome.context.civilization_id, branch_id=outcome.context.branch_id, revision_id=outcome.context.revision_id)))
