"""Data-only history reads. No evaluation callback, ranking or silent conversion."""
import json
from decimal import DecimalException
from poliscope_engine.contracts.comparison import (LineageQuery, LineagePage, LineageRow,
    ChoiceSummary, HistoryAction, CompareQuery, ComparePage, ComparisonRow,
    ComparisonValue, DesignDifference, RationaleQuery, RationaleReply)
from poliscope_engine.contracts.revisions import HistoryQuery, BranchRequest
from poliscope_engine.evaluation.identity import digest, serialized
from poliscope_engine.numeric import parse, canonical, calculate


def wording(value):
    if value.property_id == 'interview:commitment' and value.value.kind == 'label':
        try:
            data = json.loads(value.value.value)
            text = data['option']['original_text']
            return text if isinstance(text, str) else 'Original wording unavailable'
        except (ValueError, KeyError, TypeError):
            return 'Original wording unavailable'
    return serialized(value.value)


def choices(record):
    rows = []
    for option in record.decision.alternatives:
        texts = []
        for change in option.changes:
            values = change.inputs.values if change.kind == 'replace_inputs' else change.values
            texts.extend(wording(v) for v in values if v.partition == 'design')
        rows.append(ChoiceSummary(id=option.id, wording=texts))
    return rows


def lineage(service, data):
    query = LineageQuery.model_validate(data)
    rows, cursor = [], query.cursor
    for _ in range(10):
        page = service.history(HistoryQuery(context=query.context, cursor=cursor, limit=1))
        if not page.items:
            cursor = None
            break
        summary = page.items[0]
        record = service.read(summary.context)
        row = LineageRow(context=summary.context, parent_id=summary.parent_id,
            selected_id=record.decision.selected_id, alternatives=choices(record), rationale=record.decision.rationale_ref)
        if len(serialized([*rows, row]).encode()) > 800000:
            if not rows:
                raise ValueError('history_item_requires_chunking')
            break
        rows.append(row)
        cursor = page.next_cursor
        if cursor is None:
            break
    return LineagePage(comparison_contract=1, query=query,
        can_undo=service.read(query.context).parent_id is not None, branch=service.branch(query.context),
        items=rows, next_cursor=cursor)


def rationale(service, data):
    query = RationaleQuery.model_validate(data)
    record = service.read(query.context)
    ref, text = record.decision.rationale_ref, None
    if ref is not None and ref.status == 'available':
        path = service.store.path.parent / 'private-interviews' / (digest(ref.id).split(':', 1)[1] + '.json')
        try:
            with path.open('rb') as stream:
                raw = stream.read(30001)
            if len(raw) > 30000:
                raise ValueError('private_payload_too_large')
            payload = json.loads(raw)
            if (set(payload) != {'classification', 'context', 'text'} or payload['classification'] != 'private' or
                    record.applied_preview is None or payload['context'] != record.applied_preview.context.model_dump() or
                    not isinstance(payload['text'], str) or len(payload['text']) > 2048):
                raise ValueError('private_payload_binding_mismatch')
            text = payload['text']
        except (OSError, ValueError, TypeError):
            ref = ref.model_copy(update={'status':'unavailable'})
    return RationaleReply(comparison_contract=1, query=query, classification='private', reference=ref, text=text)


def action(service, data, identity):
    from poliscope_engine.workspace import select
    query = HistoryAction.model_validate(data)
    outcome = service.change_branch(BranchRequest(revision_contract=1, operation_id='history:' + identity,
        context=query.context, expected_sequence=query.expected_sequence, action=query.action,
        target_revision_id=query.target_revision_id, name=query.name,
        new_branch_id='fork:' + identity if query.action == 'fork' else None))
    return select(service, dict(civilization_id=outcome.context.civilization_id,
        branch_id=outcome.context.branch_id, revision_id=outcome.context.revision_id))


def retained(saved, identity):
    report = saved.report
    definition = next((d for d in report.definitions if d.id == identity), None) if report else None
    observation = next((o for o in report.measurements if o.indicator_id == identity), None) if report else None
    trace_state = 'unavailable'
    if observation and observation.trace_refs:
        traces = {t.id: t for t in report.traces}
        pending, seen = list(observation.trace_refs), set()
        trace_state = 'complete'
        while pending:
            key = pending.pop()
            if key in seen:
                continue
            seen.add(key)
            if key not in traces:
                trace_state = 'incomplete'
                continue
            pending.extend(traces[key].dependency_refs)
        if any(r.availability != 'available' for r in saved.references):
            trace_state = 'incomplete'
    return ComparisonValue(origin='retained_evidence' if observation else 'unavailable',
        definition=definition, observation=observation, trace_state=trace_state)


def difference(identity, left, right, lrecord, rrecord, leval, reval):
    reasons, delta = [], None
    ld, rd, lo, ro = left.definition, right.definition, left.observation, right.observation
    if not all((ld, rd, lo, ro)):
        reasons.append('Outcome unavailable on one or both revisions')
    else:
        for field in ('version', 'name', 'procedure', 'inputs', 'unit_id', 'scope_id', 'aggregation', 'time_basis_id', 'denominator_scope_id'):
            if getattr(ld, field) != getattr(rd, field):
                reasons.append('Incompatible definition: ' + field)
        for field in ('model_id', 'numeric_runtime_id', 'catalog_id', 'world_schema'):
            if getattr(lrecord.inputs.versions, field) != getattr(rrecord.inputs.versions, field):
                reasons.append('Incompatible model semantics: ' + field)
        if leval is None or reval is None:
            reasons.append('Model identity unavailable')
        elif leval.identities.model_digest != reval.identities.model_digest:
            reasons.append('Incompatible executable model definitions')
        if lo.effective_time != ro.effective_time:
            reasons.append('Incompatible effective time')
        if lo.status != 'known' or ro.status != 'known':
            reasons.append('Coverage does not support numerical subtraction')
        if lo.value.kind != 'quantity' or ro.value.kind != 'quantity':
            reasons.append('Non-numerical or unknown outcome')
        else:
            for field in ('unit_id', 'time_basis_id', 'denominator_scope_id'):
                if getattr(lo.value, field) != getattr(ro.value, field):
                    reasons.append('Incompatible quantity: ' + field)
            if not reasons:
                try:
                    value = canonical(calculate(parse(ro.value.value), parse(lo.value.value), 'subtract'))
                    delta = lo.value.model_copy(update={'value': value})
                except (ValueError, DecimalException):
                    reasons.append('Difference exceeds supported numerical precision')
    return ComparisonRow(id=identity, left=left, right=right, delta=delta, reasons=reasons)


def compare(service, data):
    query = CompareQuery.model_validate(data)
    if (query.context.data_store_id, query.context.civilization_id) != (query.other.data_store_id, query.other.civilization_id):
        raise ValueError('comparison_outside_civilization')
    left, right = service.read(query.context), service.read(query.other)
    ls, rs = service.evidence(query.context), service.evidence(query.other)
    ids = sorted({d.id for saved in (ls, rs) if saved.report for d in saved.report.definitions})
    rows = [difference(i, retained(ls, i), retained(rs, i), left, right, ls.evaluation, rs.evaluation) for i in ids]
    changes = []
    for kind, before, after in [('value', left.inputs.values, right.inputs.values), ('assumption', left.inputs.assumptions, right.inputs.assumptions),
            ('policy', left.inputs.design.policies, right.inputs.design.policies), ('goal', left.inputs.goals, right.inputs.goals),
            ('reference', ls.references, rs.references)]:
        a, b = {v.id: v for v in before}, {v.id: v for v in after}
        for key in sorted(a.keys() | b.keys()):
            if a.get(key) != b.get(key):
                def text(v):
                    if v is None:
                        return None
                    return wording(v) if kind == 'value' else serialized(v)
                changes.append(DesignDifference(kind=kind, id=key, before=text(a.get(key)), after=text(b.get(key))))
    combined = rows + changes
    prefix = digest(dict(query=query.model_dump(exclude={'cursor'}), evidence=[ls.closure_digest, rs.closure_digest]))
    offset = 0
    if query.cursor:
        bound, raw = query.cursor.rsplit(':', 1)
        offset = int(raw)
        if bound != prefix or str(offset) != raw or not 0 < offset < len(combined):
            raise ValueError('invalid_comparison_cursor')
    batch = []
    for row in combined[offset:offset+10]:
        if len(serialized([*batch, row]).encode()) > 800000:
            if not batch:
                raise ValueError('comparison_item_requires_chunking')
            break
        batch.append(row)
    end = offset + len(batch)
    return ComparePage(comparison_contract=1, query=query, left_evidence=ls.state, right_evidence=rs.state,
        left_versions=left.inputs.versions, right_versions=right.inputs.versions, items=[r for r in batch if isinstance(r, ComparisonRow)],
        changes=[r for r in batch if isinstance(r, DesignDifference)], next_cursor=prefix + ':' + str(end) if end < len(combined) else None)
