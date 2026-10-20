"""Independent discovery expectations over the pinned corpus and actual revisions."""
import json
import pytest
from poliscope_engine import atlas, interviews
from poliscope_engine.contracts.atlas import AtlasQuery
from poliscope_engine.contracts.revisions import PreviewRequest, ApplyRequest
from test_interviews import setup, edit


def query(state, **changes):
    return dict(context=state.context.model_dump(), scope_id='home', **changes)


def all_rows(service, data):
    rows, seen = [], set()
    while True:
        page = atlas.page(service, data)
        rows.extend(page.items)
        if page.next_cursor is None:
            assert len(rows) == page.total
            return rows
        assert page.next_cursor not in seen
        seen.add(page.next_cursor)
        data = data | dict(cursor=page.next_cursor)


def test_full_corpus_pagination_search_filters_and_maintenance_exclusion(tmp_path):
    store, service, state = setup(tmp_path)
    rows = all_rows(service, query(state))
    ids = [r.question.id for r in rows]
    assert len(ids) == len(set(ids)) == 36  # 12 authored, 24 civic source rounds
    for excluded in ['DEC-018', 'DEC-023', 'DEC-024', 'DEC-022/round/2']:
        assert 'society:' + excluded not in ids
    first = next(r for r in rows if r.question.id == 'society:DEC-001')
    assert len(first.options) == 4
    assert [o.id for o in first.options if o.historical_status == 'adopted'] == ['society:DEC-001/option/A']
    assert first.selected_id is None
    assert first.domain_refs == ['society:domain/01']
    assert 'society:domain/01/1/1' in first.branch_refs
    assert len(all_rows(service, query(state, domain_ref='society:domain/12'))) == 1
    assert first in all_rows(service, query(state, branch_ref='society:domain/01/1/1'))
    assert len(all_rows(service, query(state, source_ref='interview:source/conventions'))) == 12
    assert len(all_rows(service, query(state, modeling='qualitative', evidence='hypothetical'))) == 12
    assert all_rows(service, query(state, selection='selected')) == []
    assert all_rows(service, query(state, issues='none')) == []
    assert len(all_rows(service, query(state, selection='unanswered'))) == 36
    assert first in all_rows(service, query(state, search='nutrition-complete'))  # alternative D
    assert len(atlas.page(service, query(state)).branches) >= 38
    assert all_rows(service, query(state, search='nonexistent canary')) == []
    store.close()


def test_cursor_bound_to_complete_filters_context_and_catalog(tmp_path):
    store, service, state = setup(tmp_path)
    first = atlas.page(service, query(state))
    for changes in [dict(search='water'), dict(domain_ref='society:domain/01'), dict(selection='selected'), dict(issues='open')]:
        with pytest.raises(ValueError):
            atlas.page(service, query(state, cursor=first.next_cursor, **changes))
    for invalid in [dict(scope_id='foreign'), dict(domain_ref='unknown'), dict(branch_ref='unknown'), dict(source_ref='unknown'), dict(cursor='bad:1')]:
        with pytest.raises(ValueError):
            atlas.page(service, query(state) | invalid)
    with pytest.raises(ValueError):
        AtlasQuery.model_validate(query(state, search='a'*257))
    store.close()


def apply(service, change, identity):
    preview = interviews.stage(service, change, identity)[3]
    return interviews.apply(service, dict(edit=change, candidate_digest=preview.candidate_digest), identity).state


def test_proposals_selected_unanswered_scope_and_private_text(tmp_path):
    store, service, state = setup(tmp_path)
    next_state = apply(service, edit(state, 'domain:3', choice_id='player:proposal', proposal='Voluntary rotating forum'), 'proposal')
    selected = all_rows(service, query(next_state, selection='selected'))
    assert len(selected) == 1 and selected[0].selected_id == 'player:proposal'
    assert len(selected[0].options) == 4 and selected[0].archive == 'retained'
    assert len(all_rows(service, query(next_state, selection='unanswered'))) == 35
    assert len(all_rows(service, query(next_state, selection='proposed', search='rotating forum'))) == 1
    assert 'Private rationale canary' not in atlas.page(service, query(next_state)).model_dump_json()
    assert all_rows(service, query(state, selection='selected')) == []
    assert len(all_rows(service, query(next_state, search='rotating forum'))) == 1
    store.close()


def test_source_interview_preview_and_archived_alternatives_survive_catalog_change(tmp_path):
    store, service, state = setup(tmp_path)
    row = next(r for r in all_rows(service, query(state)) if r.question.id == 'society:DEC-001')
    change = edit(state, choice_id='society:DEC-001/option/D', rationale='') | dict(query=row.interview.model_dump())
    next_state = apply(service, change, 'source-choice')
    selected = all_rows(service, query(next_state, selection='selected'))[0]
    assert selected.selected_id == 'society:DEC-001/option/D'
    assert len(selected.options) == 4
    assert next(o for o in selected.options if o.id.endswith('/A')).historical_status == 'adopted'
    # Replace the live catalog object at the query boundary with changed wording.
    original = atlas.catalogs
    def changed(release):
        definitions, packs = original(release)
        definitions[row.question.id] = row.question.model_copy(update={'original_text': 'REPLACED LIVE QUESTION'})
        definitions.pop('society:DEC-001/option/B')
        return definitions, packs
    from unittest.mock import patch
    with patch.object(atlas, 'catalogs', changed):
        archived = all_rows(service, query(next_state, selection='selected'))[0]
        assert archived.question == row.question and archived.options == selected.options
        interview = interviews.question(service, dict(row.interview.model_dump(), context=next_state.context.model_dump()))
        assert len(interview.options) == 4 and interview.definition == row.question
    assert not service.read(next_state.context).inputs.design.policies
    store.close()


def test_legacy_save_recovers_original_complete_options_from_originating_revision(tmp_path):
    store, service, state = setup(tmp_path)
    next_state = apply(service, edit(state, choice_id='player:proposal', proposal='Legacy local council', rationale=''), 'legacy')
    record = service.read(next_state.context)
    inputs = record.inputs.model_dump(mode='json')
    for value in inputs['values']:
        if value['property_id'] == 'interview:commitment':
            data = json.loads(value['value']['value']); data.pop('options')
            value['value']['value'] = json.dumps(data)
    preview = PreviewRequest(revision_contract=1, context=next_state.context, changes=[dict(kind='replace_inputs', inputs=inputs)], decision=dict(alternatives=[], selected_id=None, rationale_ref=None))
    candidate = service.preview(preview)
    outcome = service.apply(ApplyRequest(revision_contract=1, operation_id='legacy-shape', preview=preview, candidate_digest=candidate.candidate_digest))
    legacy = next_state.model_copy(update={'context': outcome.context})
    legacy = apply(service, edit(legacy, 'domain:3', choice_id='player:proposal', proposal='Unrelated regional forum', rationale=''), 'other-proposal')
    selected = all_rows(service, query(legacy, selection='selected'))
    original = next(r for r in selected if r.question.id == 'interview:domain-1')
    assert len(selected) == 2 and len(original.options) == 4
    assert next(o.original_text for o in original.options if o.id == 'player:proposal') == 'Legacy local council'
    store.close()


def test_archived_source_pages_exact_text_license_and_no_paths(tmp_path):
    store, service, state = setup(tmp_path)
    data = dict(context=state.context.model_dump(), source_ref='society:source/06_global_decision_ledger.md')
    offset, texts = 0, []
    while True:
        page = atlas.source(service, data | dict(offset=offset))
        assert page.source.commit == '9ff539997dbd1bd3fa99deabcf6bc5907602df60'
        assert 'MIT License' in page.license_text
        texts.append(page.text)
        if page.next_offset is None:
            break
        assert page.next_offset > offset
        offset = page.next_offset
    _, packs = atlas.catalogs(atlas.bundled_release())
    original = next(f.text for p in packs for f in p.files if f.path == '06_global_decision_ledger.md')
    assert ''.join(texts) == original
    with pytest.raises(ValueError):
        atlas.source(service, data | dict(source_ref='../../etc/passwd'))
    store.close()


def test_scope_isolation_and_repeated_proposals_retain_catalog_choices(tmp_path):
    store, service, state = setup(tmp_path)
    state = apply(service, edit(state, 'domain:3', choice_id='player:proposal', proposal='First forum', rationale=''), 'first')
    selected = all_rows(service, query(state, selection='selected'))[0]
    update = edit(state, 'domain:3', choice_id='player:proposal', proposal='Second forum', rationale='') | dict(query=selected.interview.model_dump())
    current = apply(service, update, 'second')
    row = all_rows(service, query(current, selection='selected'))[0]
    assert len(row.options) == 4
    assert next(o.original_text for o in row.options if o.id == 'player:proposal') == 'Second forum'
    assert next(o.original_text for o in all_rows(service, query(state, selection='selected'))[0].options if o.id == 'player:proposal') == 'First forum'
    inputs = service.read(current.context).inputs.model_dump(mode='json')
    inputs['scopes'].append(dict(inputs['scopes'][0], id='elsewhere', label='Elsewhere'))
    preview = PreviewRequest(revision_contract=1, context=current.context, changes=[dict(kind='replace_inputs', inputs=inputs)], decision=dict(alternatives=[], selected_id=None, rationale_ref=None))
    candidate = service.preview(preview)
    outcome = service.apply(ApplyRequest(revision_contract=1, operation_id='other-scope', preview=preview, candidate_digest=candidate.candidate_digest))
    other = current.model_copy(update={'context': outcome.context})
    assert all_rows(service, query(other, selection='selected') | dict(scope_id='elsewhere')) == []
    assert len(all_rows(service, query(other, selection='unanswered') | dict(scope_id='elsewhere'))) == 36
    store.close()


def test_every_civic_source_round_previews_all_alternatives_without_activating_source_models(tmp_path):
    store, service, state = setup(tmp_path)
    for row in all_rows(service, query(state, source_ref='society:source/06_global_decision_ledger.md')):
        assert row.interview is not None
        q = interviews.question(service, row.interview.model_dump())
        assert [o.definition for o in q.options] == row.options
        change = edit(state, choice_id=row.options[-1].id, rationale='') | dict(query=row.interview.model_dump())
        preview = interviews.stage(service, change, row.question.id)[3]
        assert set(preview.alternatives) == {o.id for o in row.options}
        assert preview.accounts == []
    assert service.read(state.context).decision.alternatives == []
    store.close()
