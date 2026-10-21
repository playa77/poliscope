"""Data-only canonical topology; no reachability, allocation or authority inference."""
from poliscope_engine.numeric import parse
from poliscope_engine.contracts.exploration import ExplorationQuery, ExplorationPage, ExplorationEdit, ExplorationPreview
from poliscope_engine.contracts.revisions import RevisionInputs, PreviewRequest, ApplyRequest
from poliscope_engine.contracts.interview import InterviewCommit
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.revisions import RevisionError
from poliscope_engine.workspace import select

KINDS = {
    'geography': {'containment', 'geographic_overlap'},
    'membership': {'cohort_membership'},
    'authority': {'jurisdiction', 'ownership', 'obligation'},
    'networks': {'connectivity', 'access', 'supplies', 'consumes', 'information_channel'},
}

def read(service, context, scope):
    record = service.read(context)
    if scope not in {s.id for s in record.inputs.scopes}:
        raise ValueError('unknown_scope')
    return record


def page(service, data):
    q = ExplorationQuery.model_validate(data)
    record = read(service, q.context, q.scope_id)
    inputs = record.inputs
    known = {e.id for e in inputs.entities} | {s.id for s in inputs.scopes}
    if q.identity is not None and q.identity not in known:
        raise ValueError('unknown_entity')
    edges = [r for r in inputs.relationships if (q.projection == 'all' or r.relationship_kind in KINDS[q.projection] or
              (q.projection == 'membership' and r.aggregation.kind != 'non_aggregating'))
             and (q.identity is None or q.identity in (r.from_id, r.to_id))]
    visible = {q.identity} if q.identity else set()
    visible.update(e for r in edges for e in (r.from_id, r.to_id))
    if q.projection == 'all' and q.identity is None:
        visible = known
    rows = []
    def add(identity, **fields):
        rows.append(dict(id=identity, entity=None, scope=None, relationship=None, value=None, inspector=None) | fields)
    for entity in inputs.entities:
        if entity.id in visible:
            add(entity.id, entity=entity)
    for scope in inputs.scopes:
        if scope.id in visible:
            add(scope.id, scope=scope)
    for edge in edges:
        add(edge.id, relationship=edge)
    for value in inputs.values:
        # Revision-owned public values only, never private rationale payloads.
        if value.entity_id in visible and (q.identity is not None or value.scope_id == q.scope_id):
            add(value.id, value=value, inspector=dict(context=q.context, scope_id=q.scope_id,
                collection='conditions', item_id=value.id, cursor=None, all_scopes=True)
                if value.partition == 'conditions' or value.property_id.startswith('world:relationship:') else None)
    batch = inputs.design.execution.batch
    if batch:
        for account in batch.accounts:
            if (q.identity is None and account.scope_id == q.scope_id) or account.id == q.identity:
                add('account:' + account.id, inspector=dict(context=q.context, scope_id=q.scope_id,
                    collection='accounts', item_id=account.id, cursor=None, all_scopes=True))
    rows.sort(key=lambda r: r['id'])
    prefix = digest([q.model_dump(exclude={'cursor'}), inputs.model_dump(mode='json')])
    offset = 0
    if q.cursor is not None:
        parts = q.cursor.rsplit(':', 1)
        if len(parts) != 2 or parts[0] != prefix or not parts[1].isascii() or not parts[1].isdigit():
            raise ValueError('invalid_exploration_cursor')
        offset = int(parts[1])
        if offset == 0 or offset % 25 or offset >= len(rows):
            raise ValueError('invalid_exploration_cursor')
    end = offset + 25
    reply = ExplorationPage(exploration_contract=1, query=q, versions=inputs.versions,
        effective_time=inputs.design.effective_time, items=rows[offset:end], total=len(rows),
        next_cursor=f'{prefix}:{end}' if end < len(rows) else None)
    if len(reply.model_dump_json().encode()) > 900000:
        raise ValueError('exploration_page_requires_chunking')
    return reply


def description(item):
    if hasattr(item, 'entity_kind'):
        return f'{item.entity_kind}: {item.label} ({item.id})'
    if hasattr(item, 'relationship_kind'):
        rule = item.aggregation.model_dump(exclude={'kind'})
        return f'{item.relationship_kind}: {item.from_id} → {item.to_id} · {item.relationship_version} · {item.aggregation.kind} {rule or ""}'
    value = item.value
    detail = (value.value + ' ' + value.unit_id + ' · period ' + str(value.time_basis_id) + ' · denominator ' + str(value.denominator_scope_id)) if value.kind == 'quantity' else value.value if value.kind == 'label' else value.kind
    return f'{item.entity_id} · {item.property_id} · {item.scope_id}: {detail}'


def stage(service, data):
    edit = ExplorationEdit.model_validate(data)
    record = read(service, edit.context, edit.scope_id)
    raw = record.inputs.model_dump(mode='json')
    change = edit.change
    before = ''
    if change.kind == 'value':
        old = next((v for v in record.inputs.values if v.id == change.value_id), None)
        if old is None or old.scope_id != edit.scope_id or old.partition != 'conditions':
            raise ValueError('unsupported_world_value_edit')
        owner = next((o for o in record.inputs.owners if (o.entity_id, o.property_id, o.partition) ==
                      (old.entity_id, old.property_id, old.partition)), None)
        if owner is None or owner.writer_id != 'player':
            raise ValueError('world_value_write_denied')
        if old.value.kind not in ('quantity', 'label') or change.value.kind != old.value.kind:
            raise ValueError('unsupported_world_value_type')
        if old.property_id in ('people', 'area') and change.value.kind == 'quantity':
            amount = parse(change.value.value)
            if amount < 0 or (old.property_id == 'people' and amount != amount.to_integral_value()):
                raise ValueError('invalid_starting_condition')
        if old.value.kind == 'quantity' and change.value.kind == 'quantity' and (
            old.value.unit_id, old.value.time_basis_id, old.value.denominator_scope_id) != (
            change.value.unit_id, change.value.time_basis_id, change.value.denominator_scope_id):
            raise ValueError('world_value_metadata_changed')
        replacement = old.model_copy(update={'value': change.value})
        changes = [dict(kind='set_values', writer_id='player', partition='conditions', values=[replacement])]
        before, after = description(old), description(replacement)
    else:
        collection = 'entities' if change.kind == 'entity' else 'relationships'
        item = change.entity if change.kind == 'entity' else change.relationship
        old = next((r for r in raw[collection] if r['id'] == item.id), None)
        if old is not None:
            if change.kind == 'entity' and old['entity_kind'] != item.entity_kind:
                raise ValueError('identity_rebound')
            if change.kind == 'relationship' and old['relationship_version'] == item.relationship_version:
                raise ValueError('relationship_version_required')
            before = description(type(item).model_validate(old))
        if change.kind == 'entity' and item.entity_kind == 'population_cohort':
            role = next((p for p in raw['populations'] if p['entity_id'] == item.id), None)
            if role is None:
                if change.population_role is None:
                    raise ValueError('population_role_required')
                raw['populations'].append(dict(entity_id=item.id, role=change.population_role))
            elif change.population_role is not None and role['role'] != change.population_role:
                raise ValueError('population_role_rebound')
        elif change.kind == 'entity' and change.population_role is not None:
            raise ValueError('unexpected_population_role')
        if item.provenance.origin != 'player_input' or item.provenance.source_refs or item.provenance.assumption_refs:
            raise ValueError('world_edit_provenance')
        if old is not None:
            item = item.model_copy(update={'provenance': item.provenance.model_copy(update={
                'source_refs': old['provenance']['source_refs'], 'assumption_refs': old['provenance']['assumption_refs']})})
        raw[collection] = [r for r in raw[collection] if r['id'] != item.id] + [item.model_dump(mode='json')]
        if change.kind == 'relationship' and change.terms is not None:
            terms_id = 'world:terms:' + digest(item.id).split(':')[-1][:40]
            previous = next((v for v in raw['values'] if v['id'] == terms_id), None)
            if previous is not None and previous['scope_id'] != edit.scope_id:
                raise ValueError('world_terms_scope_changed')
            terms = dict(id=terms_id, entity_id=item.from_id, scope_id=edit.scope_id,
                partition='design', property_id='world:relationship:' + digest(item.id).split(':')[-1][:40],
                value=dict(kind='label', value=change.terms), effective_time=raw['design']['effective_time'],
                provenance=dict(origin='player_input', source_refs=[], assumption_refs=[]))
            raw['values'] = [v for v in raw['values'] if v['id'] != terms_id] + [terms]
            owner = dict(entity_id=item.from_id, property_id=terms['property_id'], partition='design', writer_id='player')
            if owner not in raw['owners']:
                raw['owners'].append(owner)
        candidate_inputs = RevisionInputs.model_validate(raw)
        changes = [dict(kind='replace_inputs', inputs=candidate_inputs)]
        after = description(item)
        if change.kind == 'relationship' and change.terms is not None:
            before += '\nPrevious declared terms: ' + (previous['value']['value'] if previous else 'None recorded')
            after += '\nProposed declared terms: ' + change.terms
    request = PreviewRequest(revision_contract=1, context=edit.context, changes=changes,
        decision=dict(alternatives=[dict(id='world:edit', changes=changes)], selected_id='world:edit', rationale_ref=None))
    candidate = service.preview(request)
    return edit, request, candidate, before, after


def preview(service, data):
    edit, request, candidate, before, after = stage(service, data)
    return ExplorationPreview(exploration_contract=1, edit=edit, candidate_digest=candidate.candidate_digest,
        before=before, after=after,
        coverage='Canonical revision edit. Relationships record declared geography, membership, authority or topology; they do not create transport, allocation or scientific mechanisms. Inspect retained account evidence for local capacity and unmet demand.')


def apply(service, data, identity):
    if set(data) != {'edit', 'candidate_digest'}:
        raise ValueError('invalid_world_apply')
    edit, request, candidate, _, _ = stage(service, data['edit'])
    if candidate.candidate_digest != data['candidate_digest']:
        raise ValueError('candidate_digest_mismatch')
    mutation = ApplyRequest(revision_contract=1, operation_id='world:' + identity,
        preview=request, candidate_digest=candidate.candidate_digest)
    outcome = service.status('apply', mutation)
    if outcome is None:
        try:
            outcome = service.apply(mutation)
        except RevisionError as error:
            if str(error) != 'stale_revision':
                raise
            return InterviewCommit(interview_contract=1, status='stale', state=select(service, dict(
                civilization_id=edit.context.civilization_id, branch_id=edit.context.branch_id, revision_id=None)))
    return InterviewCommit(interview_contract=1, status='applied', state=select(service, dict(
        civilization_id=outcome.context.civilization_id, branch_id=outcome.context.branch_id, revision_id=outcome.context.revision_id)))
