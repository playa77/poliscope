"""Retained evidence workspace; private payloads never become model parameters."""
from poliscope_engine.contracts.workbench import (WorkbenchQuery, WorkbenchPage, WorkbenchRow,
    WorkbenchEdit, WorkbenchPreview, DeleteNote, DeleteNoteReply)
from poliscope_engine.contracts.revisions import RevisionInputs, PreviewRequest, ApplyRequest
from poliscope_engine.contracts.interview import InterviewCommit
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.overview import selected
from poliscope_engine.revisions import RevisionError
from poliscope_engine.workspace import select
from poliscope_engine import private_notes


def supported(record, assumption, definition, scope):
    return (definition is not None and definition.scope_id == scope and
        definition.origin in ('player_input', 'ai_proposed') and definition.uncertainty_form == 'point' and
        assumption.value.kind in ('quantity', 'label') and
        any(v.value_id == assumption.id for v in record.inputs.design.assumption_inputs))


def page(service, data):
    q = WorkbenchQuery.model_validate(data)
    record, saved = selected(service, q.context, q.scope_id)
    definitions = {r.id: r.assumption for r in saved.references if r.kind == 'assumption'
        and r.visibility == 'public' and r.availability == 'available'}
    rows = []
    if q.collection == 'rationale':
        from poliscope_engine.comparison import rationale
        reply = rationale(service, dict(context=q.context))
        if reply.reference:
            rows = [WorkbenchRow(id=reply.reference.id, rationale=reply.reference, text=reply.text,
                status=reply.reference.status if reply.reference.status in ('available', 'deleted') else 'unavailable')]
    elif q.collection == 'models':
        import json
        rows = [WorkbenchRow(id='model:' + digest([d['id'], d['version']]).split(':')[1], model_id=d['id'], model_version=d['version'])
            for d in json.loads(saved.evaluation.model_json)['definitions']] if saved.evaluation else []
    elif q.collection == 'assumptions':
        rows = [WorkbenchRow(id=a.id, assumption=a, definition=definitions.get(a.id),
            editable=supported(record, a, definitions.get(a.id), q.scope_id)) for a in record.inputs.assumptions
            if definitions.get(a.id) is None or definitions[a.id].scope_id == q.scope_id]
    elif q.collection == 'references':
        references = {(r.kind, r.id): r for r in saved.references}
        from poliscope_engine.atlas import metadata
        from poliscope_engine.contracts.measurements import EvidenceReference
        for value in record.inputs.values:
            for source in (metadata(value) or {}).get('archived_sources', []):
                references.setdefault(('source', source['id']), EvidenceReference(id=source['id'], kind='source',
                    visibility='public', availability='available', description='Retained source descriptor; excerpt availability is checked against its revision', source=source))
        rows = [WorkbenchRow(id='reference:' + digest([r.kind, r.id]).split(':')[1], reference=r) for r in references.values()]
    elif q.collection == 'goals':
        observations = {g.goal_id: g for g in saved.report.goals} if saved.report else {}
        scope_indicators = {m.id for m in record.inputs.measurements if m.scope_id == q.scope_id}
        scopes = {g.id: g.scope_id for g in record.inputs.goal_scopes}
        rows = [WorkbenchRow(id=g.id, goal=g, observation=observations.get(g.id)) for g in record.inputs.goals
            if scopes.get(g.id) in (None, q.scope_id) and (g.indicator_id is None or g.indicator_id in scope_indicators)]
    else:
        for ref in record.inputs.notes:
            if ref.scope_id == q.scope_id:
                status, kind, text = private_notes.read(service, q.context, ref)
                rows.append(WorkbenchRow(id=ref.id, note=ref, note_kind=kind, text=text, status=status))
    rows.sort(key=lambda r: r.id)
    prefix = digest(q.model_dump(exclude={'cursor'}))
    offset = 0
    if q.cursor:
        bound, part = q.cursor.rsplit(':', 1)
        if bound != prefix or not part.isascii() or not part.isdigit():
            raise ValueError('invalid_workbench_cursor')
        offset = int(part)
        if offset == 0 or offset % 25 or offset >= len(rows):
            raise ValueError('invalid_workbench_cursor')
    end = offset + 25
    reply = WorkbenchPage(workbench_contract=1, query=q, versions=record.inputs.versions,
        effective_time=record.inputs.design.effective_time,
        physical_output_digest=saved.report.physical_output_digest if saved.report else None,
        items=rows[offset:end], next_cursor=f'{prefix}:{end}' if end < len(rows) else None)
    if len(reply.model_dump_json().encode()) > 900000:
        raise ValueError('workbench_page_requires_chunking')
    return reply


def stage(service, data, identity):
    edit = WorkbenchEdit.model_validate(data)
    record, saved = selected(service, edit.context, edit.scope_id)
    raw = record.inputs.model_dump(mode='json')
    change, ref = edit.change, None
    disclosure = ''
    if change.kind in ('assumption', 'proposal'):
        old = next((a for a in record.inputs.assumptions if a.id == change.id), None)
        definition = next((r.assumption for r in saved.references if r.id == change.id and
            r.kind == 'assumption' and r.visibility == 'public' and r.availability == 'available'), None)
        if old is None or not supported(record, old, definition, edit.scope_id):
            raise ValueError('unsupported_assumption_edit')
        if old.value.kind != change.value.kind:
            raise ValueError('assumption_type_changed')
        if old.value.kind == 'quantity' and any(getattr(old.value, f) != getattr(change.value, f)
                for f in ('unit_id', 'time_basis_id', 'denominator_scope_id')):
            raise ValueError('assumption_metadata_changed')
        raw['assumptions'] = [a | dict(value=change.value.model_dump()) if a['id'] == change.id else a for a in raw['assumptions']]
        if change.kind == 'proposal':
            import json
            # Retained public evidence records origin and coverage; never alter
            # mechanism definitions or activate unsupported numerical models.
            receipt = dict(origin=change.origin, source_request_id=change.source_request_id,
                coverage=change.coverage, manifest_digest=change.manifest_digest)
            for item in raw['references']:
                if item['id'] == change.id and item.get('assumption'):
                    item['assumption']['origin'] = change.origin
                    item['description'] = json.dumps(receipt, sort_keys=True)
        else:
            for item in raw['references']:
                if item['id'] == change.id and item.get('assumption'):
                    item['assumption']['origin'] = 'player_input'
                    if definition.origin == 'ai_proposed':
                        item['description'] = 'Player-edited parameter; prior AI origin and coverage remain in immutable history.'
        disclosure = 'This parameter becomes ordinary simulation input. Its retained definition, units, scope and uncertainty form stay fixed. Compare branches to inspect supported consequences; this does not validate scientific extrapolation.'
    elif change.kind == 'goal':
        goal = change.goal
        if goal.kind == 'narrative':
            if any(v is not None for v in (goal.indicator_id, goal.operation, goal.threshold)):
                raise ValueError('invalid_narrative_goal')
        else:
            indicator = next((m for m in record.inputs.measurements if m.id == goal.indicator_id and m.scope_id == edit.scope_id), None)
            if indicator is None or goal.operation is None or goal.threshold is None:
                raise ValueError('invalid_goal_indicator')
            if (goal.threshold.unit_id, goal.threshold.time_basis_id, goal.threshold.denominator_scope_id) != (
                    indicator.unit_id, indicator.time_basis_id, indicator.denominator_scope_id):
                raise ValueError('goal_metadata_mismatch')
        old = next((g for g in record.inputs.goals if g.id == goal.id), None)
        if change.remove and old is None:
            raise ValueError('unknown_goal')
        if old and (old.indicator_id != goal.indicator_id or any(s.id == old.id and s.scope_id != edit.scope_id for s in record.inputs.goal_scopes)):
            raise ValueError('goal_identity_rebound')
        raw['goals'] = [g for g in raw['goals'] if g['id'] != goal.id]
        raw['goal_scopes'] = [s for s in raw['goal_scopes'] if s['id'] != goal.id]
        if not change.remove:
            raw['goals'].append(goal.model_dump())
            raw['goal_scopes'].append(dict(id=goal.id, scope_id=edit.scope_id))
        disclosure = 'The question and typed target shown here become ordinary goal content in immutable history. Use a private note for private inquiry. Goals only interpret observations; they do not alter physics, allocations or model coverage.'
    else:
        old = next((n for n in record.inputs.notes if n.id == change.id), None)
        if change.id is not None and (old is None or old.scope_id != edit.scope_id):
            raise ValueError('unknown_scoped_note')
        if old and private_notes.read(service, edit.context, old)[0] == 'deleted':
            raise ValueError('note_deleted')
        from poliscope_engine.contracts.annotations import NoteReference
        ref = NoteReference(id=change.id or 'note:' + identity, version='note-version:' + identity,
            scope_id=edit.scope_id, classification='private')
        raw['notes'] = [n for n in raw['notes'] if n['id'] != ref.id] + [ref.model_dump()]
        disclosure = 'Private note text and its kind stay in the classified local payload store. Immutable history retains a noncontent reference. Model gaps and proposals remain qualitative; use a separate supported design edit and its Preview to promote content. No arithmetic or mechanism is activated.'
    inputs = RevisionInputs.model_validate(raw)
    changes = [dict(kind='replace_inputs', inputs=inputs)]
    request = PreviewRequest(revision_contract=1, context=edit.context, changes=changes,
        decision=dict(alternatives=[dict(id='workbench:edit', changes=changes)], selected_id='workbench:edit', rationale_ref=None))
    candidate = service.preview(request)
    reply = WorkbenchPreview(workbench_contract=1, edit=edit, candidate_digest=candidate.candidate_digest,
        physical_before=saved.report.physical_output_digest if saved.report else None,
        physical_after=candidate.report.physical_output_digest,
        changed_observations=len(candidate.differences), disclosure=disclosure)
    if change.kind in ('goal', 'note') and reply.physical_before != reply.physical_after:
        raise ValueError('annotation_changed_physics')
    return edit, request, ref, reply


def preview(service, data, identity):
    return stage(service, data, identity)[3]


def apply(service, data, identity):
    if set(data) != {'edit', 'candidate_digest'}:
        raise ValueError('invalid_workbench_apply')
    edit, request, ref, candidate = stage(service, data['edit'], identity)
    if candidate.candidate_digest != data['candidate_digest']:
        raise ValueError('candidate_digest_mismatch')
    mutation = ApplyRequest(revision_contract=1, operation_id='workbench:' + identity,
        preview=request, candidate_digest=candidate.candidate_digest)
    outcome = service.status('apply', mutation)
    if outcome is None:
        if service.branch(edit.context).context.revision_id != edit.context.revision_id:
            return committed(service, edit, None)
        if ref:
            private_notes.save(service, edit.context, ref, edit.change.note_kind, edit.change.text)
        try:
            outcome = service.apply(mutation)
        except RevisionError as error:
            if str(error) != 'stale_revision':
                raise
    return committed(service, edit, outcome)


def committed(service, edit, outcome):
    return InterviewCommit(interview_contract=1, status='applied' if outcome else 'stale',
        state=select(service, dict(civilization_id=edit.context.civilization_id,
            branch_id=edit.context.branch_id, revision_id=outcome.context.revision_id if outcome else None)))


def delete(service, data):
    q = DeleteNote.model_validate(data)
    record, _ = selected(service, q.context, q.scope_id)
    ref = next((n for n in record.inputs.notes if n.id == q.id and n.scope_id == q.scope_id), None)
    if ref is None:
        rationale = record.decision.rationale_ref
        if rationale is None or rationale.id != q.id:
            raise ValueError('unknown_scoped_note')
        path = service.store.path.parent / 'private-interviews' / (digest(rationale.id).split(':')[1] + '.json')
        private_notes.atomic(path.with_suffix('.deleted'), dict(classification='private', status='deleted'))
        path.unlink(missing_ok=True)
        # This owner currently creates no rationale indexes or derived files.
    else:
        private_notes.delete(service, q.context, ref)
    return DeleteNoteReply(workbench_contract=1, query=q, status='deleted')
