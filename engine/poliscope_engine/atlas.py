"""Data-only discovery. Source adoption never selects a player's commitment."""
import json
from poliscope_engine.contracts.atlas import AtlasQuery, AtlasEntry, AtlasPage, AtlasSourceQuery, AtlasSourcePage
from poliscope_engine.contracts.packs import Definition
from poliscope_engine.contracts.interview import InterviewQuery
from poliscope_engine.content import bundled_release
from poliscope_engine.packs import PackArchive
from poliscope_engine.evaluation.identity import digest, serialized


def catalogs(release):
    packs = [PackArchive(release.artifact(c.artifact)).pack for c in release.metadata.catalogs]
    return {d.id: d for p in packs for d in p.definitions}, packs


def metadata(value):
    if value.property_id != 'interview:commitment' or value.value.kind != 'label':
        return None
    data = json.loads(value.value.value)
    Definition.model_validate(data['question'])
    Definition.model_validate(data['option'])
    return data


def retained(service, record, scope):
    """Legacy WP-021 saves archive each alternative in the originating revision.

    New saves include their complete question catalog in the commitment itself.
    Never substitute live wording when retained alternatives are unavailable.
    """
    result = {}
    for value in record.inputs.values:
        if value.scope_id != scope:
            continue
        saved = metadata(value)
        if saved is None:
            continue
        question = Definition.model_validate(saved['question'])
        options = saved.get('options')
        if options is None:
            current, seen = record, set()
            while True:
                if current.context.revision_id in seen or len(seen) >= 10000:
                    raise ValueError('archive_lineage_limit')
                seen.add(current.context.revision_id)
                candidates = []
                for alternative in current.decision.alternatives:
                    for change in alternative.changes:
                        values = change.inputs.values if change.kind == 'replace_inputs' else change.values
                        for candidate in values:
                            if candidate.id == value.id and candidate.scope_id == scope:
                                data = metadata(candidate)
                                if data and data['question'] == saved['question']:
                                    candidates.append(data['option'])
                parent = service.read(record.context.model_copy(update={'revision_id': current.parent_id})) if current.parent_id else None
                current_value = next((v for v in current.inputs.values if v.id == value.id), None)
                previous_value = next((v for v in parent.inputs.values if v.id == value.id), None) if parent else None
                if (candidates and current.decision.selected_id == saved['option']['id']
                        and current_value != previous_value):
                    options = candidates
                    break
                if parent is None:
                    raise ValueError('retained_alternatives_unavailable')
                current = parent
        parsed = {o.id: o for o in map(Definition.model_validate, options)}
        chosen = Definition.model_validate(saved['option'])
        parsed[chosen.id] = chosen
        if any(o.parent_ref != question.id for o in parsed.values()):
            raise ValueError('retained_alternative_parent')
        result[question.id] = (question, list(parsed.values()), chosen.id, saved)
    return result


def locations(release):
    inventory = json.loads(release.artifact('society.inventory.json'))
    documents, parents = {}, {}
    for domain in inventory['domains']:
        for branch in domain['branches']:
            parents[branch['id']] = domain['id']
            for leaf in branch['leaves']:
                parents[leaf['id']] = branch['id']
                for doc in leaf['documents']:
                    documents.setdefault(doc, []).append((domain['id'], leaf['id']))
    decisions = {}
    for decision in inventory['decisions']:
        refs = {pair for doc in decision['amends'] for pair in documents.get(doc, [])}
        decisions[decision['id']] = (sorted({r[0] for r in refs}), sorted({r[1] for r in refs}))
    return decisions, parents


def entries(service, record, scope, release=None):
    release = release or bundled_release()
    definitions, _ = catalogs(release)
    mapped, parents = locations(release)
    templates = {t.question.id: t for t in release.metadata.templates}
    archives = retained(service, record, scope)
    rows = []
    for key in sorted({d.id for d in definitions.values() if d.kind == 'question'} | archives.keys()):
        definition = definitions.get(key)
        if key in archives:
            definition, options, selected, saved = archives[key]
            domains = saved.get('domain_refs', [])
            branches = saved.get('branch_refs', [])
        else:
            options = [d for d in definitions.values() if d.kind == 'option' and d.parent_ref == key]
            selected, domains, branches = None, [], []
        if definition.historical_status == 'provenance':
            continue
        if key in templates:
            domains = [templates[key].domain_ref]
        elif key not in archives and definition.source_decision_id in mapped:
            domains, branches = mapped[definition.source_decision_id]
        if not domains and key not in archives:
            # Unmapped source decisions stay discoverable, without invented domain tags.
            domains = []
        expanded = set(branches)
        for branch in list(branches):
            while branch in parents:
                branch = parents[branch]
                if branch in definitions and definitions[branch].kind == 'branch':
                    expanded.add(branch)
        domain = 'domain:' + str(int(domains[0].rsplit('/', 1)[1])) if domains else 'domain:all'
        issues = []
        if definition.modeling not in ('numerical', 'procedural'):
            issues.append('No activated numerical or procedural model; quantities in source prose are unreviewed design claims.')
        if definition.evidence != 'supported':
            issues.append('Evidence: ' + definition.evidence)
        if definition.supersedes_refs or definition.historical_status == 'superseded':
            issues.append('Supersession is recorded; inspect original wording and history.')
        if not domains:
            issues.append('Domain/branch mapping is unresolved.')
        rows.append(AtlasEntry(question=definition, options=options, domain_refs=domains, branch_refs=sorted(expanded),
            selected_id=selected, archive='retained' if key in archives else 'current_catalog', issues=issues,
            interview=InterviewQuery(context=record.context, scope_id=scope, domain_id=domain, question_id=key) if domain and options else None))
    return rows


def page(service, data, *, release=None):
    query = AtlasQuery.model_validate(data)
    record = service.read(query.context)
    if query.scope_id not in {s.id for s in record.inputs.scopes}:
        raise ValueError('unknown_scope')
    release = release or bundled_release()
    definitions, packs = catalogs(release)
    domains = [dict(id=d.id, label=d.original_text) for d in definitions.values() if d.kind == 'domain']
    branches = [dict(id=d.id, label=d.original_text) for d in definitions.values() if d.kind == 'branch' and d.id.startswith('society:domain/')]
    sources = [dict(id=s.reference.id, label=s.reference.document_id) for p in packs for s in p.sources]
    for field, directory in [('domain_ref', domains), ('branch_ref', branches), ('source_ref', sources)]:
        if getattr(query, field) is not None and getattr(query, field) not in {r['id'] for r in directory}:
            raise ValueError('unknown_' + field)
    rows = []
    for row in entries(service, record, query.scope_id, release):
        definitions_in_row = [row.question, *row.options]
        if query.domain_ref and query.domain_ref not in row.domain_refs:
            continue
        if query.branch_ref and query.branch_ref not in row.branch_refs:
            continue
        if query.source_ref and not any(query.source_ref in d.source_refs for d in definitions_in_row):
            continue
        if query.selection == 'selected' and row.selected_id is None or query.selection == 'unanswered' and row.selected_id is not None:
            continue
        if query.selection == 'proposed' and not any(d.origin in ('player_proposed', 'ai_proposed') for d in row.options):
            continue
        if query.modeling and not any(d.modeling == query.modeling for d in definitions_in_row):
            continue
        if query.evidence and not any(d.evidence == query.evidence for d in definitions_in_row):
            continue
        if query.issues == 'open' and not row.issues or query.issues == 'none' and row.issues:
            continue
        if query.search.strip().casefold() not in serialized(row).casefold():
            continue
        rows.append(row)
    bound = digest(dict(query=query.model_dump(exclude={'cursor'}), release=release.digest))
    offset = 0
    if query.cursor:
        prefix, token = query.cursor.rsplit(':', 1)
        offset = int(token)
        if prefix != bound or str(offset) != token or not 0 < offset < len(rows):
            raise ValueError('invalid_atlas_cursor')
    items = []
    for row in rows[offset:offset+5]:
        if len(serialized([*items, row]).encode()) > 700000:
            if not items:
                raise ValueError('atlas_item_requires_chunking')
            break
        items.append(row)
    end = offset + len(items)
    return AtlasPage(atlas_contract=1, query=query, catalog_digest=release.digest, items=items, total=len(rows),
        next_cursor=bound + ':' + str(end) if end < len(rows) else None, domains=domains, branches=branches, sources=sources)


def source(service, data):
    query = AtlasSourceQuery.model_validate(data)
    service.read(query.context)
    _, packs = catalogs(bundled_release())
    for pack in packs:
        archived = next((s for s in pack.sources if s.reference.id == query.source_ref), None)
        if archived:
            text = next(f.text for f in pack.files if f.path == archived.excerpt_file)
            license = next(l for l in pack.licenses if l.id == archived.reference.license_id)
            license_text = next(f.text for f in pack.files if f.path == license.file)
            if query.offset > len(text):
                raise ValueError('invalid_source_offset')
            end = min(query.offset + 12000, len(text))
            return AtlasSourcePage(atlas_contract=1, query=query, source=archived, text=text[query.offset:end],
                license_text=license_text, next_offset=end if end < len(text) else None)
    raise ValueError('archived_source_unavailable')
