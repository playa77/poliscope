"""Bounded public scope projection and pure tools over a main-retained manifest.

No denied reference is probed. Error responses never contain arguments, backend
errors, counts, IDs, private-reference existence or data from outside the grant.
"""
import json
from poliscope_engine.contracts.grounding import (GroundingQuery, GroundingManifest,
    GroundingEntry, GroundingTool, GroundingResult)
from poliscope_engine.contracts.world import WorldValue
from poliscope_engine.contracts.workbench import WorkbenchEdit
from poliscope_engine.evaluation.identity import digest, serialized
from poliscope_engine.overview import selected
from pydantic import TypeAdapter

MAX_BYTES = 24000
DENIED = GroundingResult(status='unavailable', data_json='{"status":"unavailable"}')


def assemble(service, data):
    query = GroundingQuery.model_validate(data)
    record, saved = selected(service, query.context, query.selection.scope_id)
    scope, collections = query.selection.scope_id, set(query.selection.collections)
    if len(collections) != len(query.selection.collections):
        raise ValueError('duplicate_collection')
    public = {r.id: r for r in saved.references if r.visibility == 'public' and r.availability == 'available'}
    # Classifications propagate through retained provenance, including public
    # descriptors whose upstream source became private/unavailable. A public
    # label never declassifies a private derivative.
    while True:
        eligible = {identity: ref for identity, ref in public.items()
            if (ref.assumption is None or (ref.assumption.scope_id == scope and set(ref.assumption.source_refs) <= public.keys()))
            and (ref.source is None or set(ref.source.supersedes_refs) <= public.keys())}
        if eligible.keys() == public.keys():
            break
        public = eligible
    entries, used_refs = [], set()
    limited = False

    def safe(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ('source_refs', 'assumption_refs') and any(ref not in public or (public[ref].assumption is not None and public[ref].assumption.scope_id != scope) for ref in item):
                    return False
                if key == 'scope_id' and item is not None and item != scope:
                    return False
                if not safe(item):
                    return False
        elif isinstance(value, list):
            return all(safe(v) for v in value)
        return True

    def add(collection, identity, data, coverage):
        nonlocal limited
        raw = data.model_dump(mode='json') if hasattr(data, 'model_dump') else data
        if not safe(raw):
            return
        encoded = serialized(raw)
        if len(encoded) > 16000 or len(entries) >= 60 or sum(len(e.model_dump_json().encode()) for e in entries) + len(encoded.encode()) > MAX_BYTES:
            limited = True
            return
        entries.append(GroundingEntry(id=collection + ':' + digest(identity).split(':')[1], collection=collection,
            coverage=coverage, data_json=encoded))
        def refs(v):
            if isinstance(v, dict):
                for k, x in v.items():
                    if k in ('source_refs', 'assumption_refs'):
                        used_refs.update(x)
                    else:
                        refs(x)
            elif isinstance(v, list):
                for x in v:
                    refs(x)
        refs(raw)

    if 'facts' in collections or 'choices' in collections:
        for value in record.inputs.values:
            if value.scope_id != scope or value.provenance.origin == 'derived':
                continue
            collection = 'facts' if value.partition == 'conditions' else 'choices'
            if collection in collections:
                add(collection, value.id, value, 'missing_input' if value.value.kind == 'unknown' else 'declared input; not scientific validation')
    if 'assumptions' in collections:
        from poliscope_engine.workbench import supported
        for value in record.inputs.assumptions:
            ref = public.get(value.id)
            if ref and ref.assumption and ref.assumption.scope_id == scope:
                add('assumptions', value.id, dict(value=value.model_dump(mode='json'),
                    definition=ref.assumption.model_dump(mode='json'), editable=supported(record, value, ref.assumption, scope)), 'declared assumption; not scientific validation')
    report = saved.report
    scoped = set()
    if report:
        scoped = {t.id for t in report.traces if all(m.scope_id == scope for m in t.members)
            and all(m.scope_id == scope for m in t.mechanisms) and safe(t.model_dump(mode='json'))}
        # A transitive reference to an unapproved scope withholds the entire trace.
        while True:
            narrowed = {t.id for t in report.traces if t.id in scoped and set(t.dependency_refs) <= scoped}
            if narrowed == scoped:
                break
            scoped = narrowed
    if report and 'accounts' in collections and saved.evaluation:
        from poliscope_engine.overview import page
        q = dict(context=query.context, scope_id=scope, collection='accounts', item_id=None, cursor=None, all_scopes=False)
        while True:
            page_result = page(service, q)
            for row in page_result.items:
                if row.trace_refs and set(row.trace_refs) <= scoped and row.definition.scope_id == scope:
                    add('accounts', row.id, row, 'retained account evidence')
            if not page_result.next_cursor or limited:
                break
            q['cursor'] = page_result.next_cursor
    if report and 'traces' in collections:
        for trace in report.traces:
            if trace.id in scoped:
                add('traces', trace.id, trace, 'retained calculation; see member coverage')
    if 'sources' in collections:
        # Only references actually reached from approved rows, never the global
        # source catalog, private reference indexes or arbitrary file contents.
        for identity in list(used_refs):
            if public[identity].assumption:
                used_refs.update(public[identity].assumption.source_refs)
        for identity in sorted(used_refs):
            ref = public[identity]
            if ref.kind == 'source':
                add('sources', identity, ref, 'retained attribution; no remote retrieval')
    limitations = ['Only explicitly selected public collections in this scope; no notes, rationale, attachments, other branches or scopes.',
        'Public provenance-derived rows with private or out-of-scope dependencies are withheld.',
        'Source metadata is retained attribution, not scientific validation. Unknown values remain unknown.',
        'No tool may apply changes, edit models, mutate a timeline, read files or URLs, or retrieve keys.']
    if limited:
        limitations.append('Context budget reached; projection is partial. Narrow the selection for more detail.')
    raw = dict(grounding_contract=1, context=query.context, selection=query.selection,
        versions=record.inputs.versions, effective_time=record.inputs.design.effective_time,
        entries=entries, limitations=limitations)
    result = GroundingManifest(**raw, digest=digest(raw))
    if len(result.model_dump_json().encode()) > 32000:
        raise ValueError('context_budget')
    return result


def tool(service, manifest, data, request_id):
    try:
        manifest = GroundingManifest.model_validate(manifest)
        if digest(manifest.model_dump(exclude={'digest'})) != manifest.digest or not manifest.selection.tools:
            return DENIED
        query = GroundingTool.model_validate(data)
        entry = next((e for e in manifest.entries if e.id == query.entry_id), None)
        if entry is None:
            return DENIED
        raw = json.loads(entry.data_json)
        if query.operation in ('read', 'inspect', 'retrieve'):
            if query.other_id is not None or query.value_json is not None:
                return DENIED
            return GroundingResult(status='available', data_json=entry.model_dump_json())
        if query.operation == 'compare':
            other = next((e for e in manifest.entries if e.id == query.other_id), None)
            if other is None or other.collection != entry.collection or query.value_json is not None:
                return DENIED
            # An exact, data-only comparison, never an invented numerical score.
            return GroundingResult(status='available', data_json=serialized(dict(
                left=raw, right=json.loads(other.data_json), equal=entry.data_json == other.data_json)))
        if entry.collection != 'assumptions' or not raw['editable'] or query.other_id is not None:
            return DENIED
        value = TypeAdapter(WorldValue).validate_json(query.value_json or '')
        edit = WorkbenchEdit(context=manifest.context, scope_id=manifest.selection.scope_id,
            change=dict(kind='proposal', id=raw['value']['id'], value=value,
                origin='ai_proposed', source_request_id=request_id, coverage=entry.coverage, manifest_digest=manifest.digest))
        from poliscope_engine.workbench import stage
        stage(service, edit, request_id)
        # Pure preview checks preserve the same allowlist. Do not return unrelated
        # changed-observation counts, global digests or arbitrary backend errors.
        if value.kind != raw['value']['value']['kind']:
            return DENIED
        result = dict(status='valid', origin='ai_proposed', coverage=entry.coverage,
            assumption_id=raw['value']['id'], value=value.model_dump(mode='json'),
            limitation='Noncommitting proposal. Player must open ordinary preview and approve Apply.')
        return GroundingResult(status='available', data_json=serialized(result),
            proposal_json=edit.model_dump_json() if query.operation == 'preview' else None)
    except Exception:
        return DENIED
