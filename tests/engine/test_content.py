"""Release integrity and real registry handoff; synthetic approval is not science."""
import json
from pathlib import Path

import pytest

from poliscope_engine.content import (Release, ContentError, load_release, bundled_release,
    review_digest, reviewed_registry, authorize_review)
from poliscope_engine.content.build import build
from poliscope_engine.contracts.content import ModelReview
from poliscope_engine.corpus import canonical
from poliscope_engine.packs import PackArchive, PackError, digest
from poliscope_engine.mechanisms import MechanismError, declaration_digest
from test_mechanism_registry import definitions, registry, activate

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / 'content/release-v1'


def snapshot():
    metadata = json.loads((RELEASE / 'release.json').read_bytes())
    artifacts = {a['path']: (RELEASE / a['path']).read_bytes() for a in metadata['artifacts']}
    return metadata, artifacts


def validate(metadata, artifacts):
    return Release(canonical(metadata), artifacts)


def repack(metadata, artifacts, path, change):
    value = json.loads(artifacts[path])
    change(value)
    archive = PackArchive(canonical(value))
    artifacts[path] = canonical(archive.pack.model_dump(mode='json'))
    next(a for a in metadata['artifacts'] if a['path'] == path)['digest'] = digest(artifacts[path])
    next(c for c in metadata['catalogs'] if c['artifact'] == path)['pack_digest'] = archive.digest


def test_pinned_release_has_exhaustive_gaps_original_options_and_no_rules():
    release = load_release(RELEASE)
    assert len(release.metadata.coverage) == 38 + 115
    assert sum(c.source_status == 'map_only' for c in release.metadata.coverage if c.branch_ref.count('/') == 3) == 108
    assert len(release.metadata.templates) == len(release.metadata.inquiries) == 12
    assert not release.metadata.activated_review_refs
    assert all(r.disposition == 'blocked' for r in release.metadata.reviews)
    pack = PackArchive(release.artifact('society.pack.json')).pack
    assert sum(d.kind == 'option' for d in pack.definitions) == 87
    assert all(d.modeling == 'unsupported' for d in pack.definitions)
    assert 'Permission is hereby granted' in next(f.text for f in pack.files if f.path == 'LICENSE')
    assert len(pack.sources) == 27


def test_rebuild_is_byte_identical_and_reader_detaches():
    metadata, artifacts = snapshot()
    release = validate(metadata, artifacts)
    report = json.loads(artifacts['society.inventory.json'])
    expected = build(PackArchive(artifacts['society.pack.json']), report, (ROOT / 'LICENSE').read_bytes(),
                     (ROOT / 'docs/roadmap/execution/society/review.md').read_bytes())
    assert expected == {'release.json': canonical(metadata), **artifacts}
    artifacts.clear()
    release.metadata.templates.clear()
    assert len(release.metadata.templates) == 12
    assert release.artifact('society.pack.json')


@pytest.mark.parametrize('mutation', [
    lambda m, a: a.pop('society.pack.json'),
    lambda m, a: a.update({'hidden.py': b'raise RuntimeError()'}),
    lambda m, a: a.update({'society.pack.json': b'{}'}),
    lambda m, a: m['catalogs'][0].update(pack_digest='sha256:' + '0' * 64),
    lambda m, a: m['coverage'].pop(),
    lambda m, a: m['coverage'].append(m['coverage'][0]),
    lambda m, a: m['templates'][0].update(domain_ref='society:absent'),
    lambda m, a: m['templates'][0]['question'].update(original_text='Silently edited template'),
    lambda m, a: m['templates'][0]['benefits'].pop(),
    lambda m, a: m['templates'][0]['options'].__setitem__(1, m['templates'][0]['options'][0]),
    lambda m, a: m['reviews'][0].update(evidence_refs=['society:absent']),
    lambda m, a: m['reviews'][0].update(validity_limits=' '),
    lambda m, a: m['activated_review_refs'].append(m['reviews'][0]['id']),
    lambda m, a: m['setups'][0].update(population='0'),
    lambda m, a: m['setups'][0].update(selected_option_refs=[m['setups'][2]['selected_option_refs'][0]]),
    lambda m, a: m['setups'][1].update(population='0.5'),
    lambda m, a: m['setups'][1].update(land_area='-1'),
    lambda m, a: m['setups'][1].update(land_area='NaN'),
    lambda m, a: m['setups'][2].update(selected_option_refs=['society:DEC-SYS-001']),
    lambda m, a: m['setups'][2].update(source_refs=[]),
    lambda m, a: m['inquiries'].clear(),
])
def test_tampered_release_fails_closed(mutation):
    metadata, artifacts = snapshot()
    mutation(metadata, artifacts)
    with pytest.raises((ValueError, KeyError)):
        validate(metadata, artifacts)


def test_rehashed_missing_attribution_and_unsupported_numerics_still_fail():
    metadata, artifacts = snapshot()
    repack(metadata, artifacts, 'society.pack.json', lambda p: p['definitions'][0].update(source_refs=[]))
    with pytest.raises(ContentError, match='attribution_required'):
        validate(metadata, artifacts)
    metadata, artifacts = snapshot()
    repack(metadata, artifacts, 'society.pack.json', lambda p: p['definitions'][0].update(modeling='numerical'))
    with pytest.raises(ContentError, match='activation_inventory'):
        validate(metadata, artifacts)


def test_source_digest_license_and_duplicate_json_are_rejected():
    metadata, artifacts = snapshot()
    pack = json.loads(artifacts['society.pack.json'])
    pack['files'][0]['text'] += 'tampered'
    with pytest.raises(PackError, match='file_digest'):
        PackArchive(canonical(pack))
    pack = json.loads(artifacts['society.pack.json'])
    pack['licenses'].clear()
    with pytest.raises(PackError, match='source_license'):
        PackArchive(canonical(pack))
    with pytest.raises(PackError, match='duplicate_json_key'):
        Release(b'{"format_version":1,"format_version":1}', {})


def test_filesystem_links_and_unregistered_files_are_rejected(tmp_path):
    metadata, artifacts = snapshot()
    for name, value in {'release.json': canonical(metadata), **artifacts}.items():
        (tmp_path / name).write_bytes(value)
    (tmp_path / 'hidden.json').write_text('{}')
    with pytest.raises(ContentError, match='artifact_inventory'):
        load_release(tmp_path)
    (tmp_path / 'hidden.json').unlink()
    (tmp_path / 'source-review.md').unlink()
    (tmp_path / 'source-review.md').symlink_to(RELEASE / 'source-review.md')
    with pytest.raises(ContentError, match='unsafe_artifact'):
        load_release(tmp_path)


def test_safe_paths_and_bounds():
    metadata, artifacts = snapshot()
    metadata['artifacts'][0]['path'] = '../outside'
    artifacts['../outside'] = artifacts.pop('interview.pack.json')
    with pytest.raises(ContentError, match='unsafe_path'):
        validate(metadata, artifacts)
    with pytest.raises(ContentError, match='artifact_size'):
        Release(b' ' * (8 * 1024 * 1024 + 1), {})


def test_explicit_reference_setup_and_blank_world_neutrality():
    release = bundled_release()
    assert release.setup('blank').selected_option_refs == []
    for identity in ('reference:small-settlement', 'reference:society-dec-003'):
        with pytest.raises(ContentError, match='explicit_selection_required'):
            release.setup(identity)
        assert release.setup(identity, explicitly_selected=True).goals == []
    historical = release.setup('reference:society-dec-003', explicitly_selected=True)
    assert historical.selected_option_refs and historical.population is None
    from poliscope_engine.workspace import starting_inputs
    inputs = starting_inputs(dict(name='Blank', setup='blank', scope_name='Home', population=None, land_area=None), 'civ')
    assert not inputs.goals and not inputs.design.policies and not inputs.design.execution.dependencies.instances
    assert all(v.value.kind == 'unknown' for v in inputs.values)


def review_case():
    definition = definitions()[0]
    record = ModelReview.model_validate(dict(id='synthetic:review', candidate_refs=[definition.id],
        mechanism_ref=definition.id, mechanism_version=definition.version, mechanism_artifact='mechanism.json',
        declaration_digest=declaration_digest(definition), graph_digest=None, model=dict(id='synthetic:model', version='v1'),
        disposition='approved', operational_definition='Synthetic mass passthrough.', formula_or_procedure='output = input',
        denominator_time_scope='kg stock at settlement; no time or population denominator', basis='hypothetical',
        uncertainty='Exact arithmetic fixture only.', evidence_refs=['synthetic:source'], evidence_digests={'synthetic:source': digest(b'Synthetic mass passthrough evidence')},
        fixtures=[dict(identity=dict(id='synthetic:positive', version='v1'), artifact='fixture.json', digest='sha256:' + '0' * 64, purpose='positive')],
        invariants='Output equals supplied input.', validity_limits='Synthetic positive-mass stock fixture.',
        unsupported_extrapolation='No empirical provisioning or welfare claim.', review_notes='Independent literal oracle for test handoff.'))
    artifacts = {'mechanism.json': canonical(definition.model_dump(mode='json')), 'fixture.json': canonical(dict(id='synthetic:positive', version='v1',
        derivation='Independent integer equality oracle: 7 kg in = 7 kg out.', cases=[dict(inputs={'kg': '7'}, expected={'kg': '7'})]))}
    record = ModelReview.model_validate(record.model_dump(mode='json') | {'fixtures': [record.fixtures[0].model_dump(mode='json') | {'digest': digest(artifacts['fixture.json'])}]})
    return record, artifacts


def test_host_approved_record_reaches_real_registry_without_rewriting_evidence():
    record, artifacts = review_case()
    base = registry(reviews=[])
    with pytest.raises(MechanismError, match='review_required'):
        activate(base)
    with pytest.raises(ContentError, match='host_review_required'):
        reviewed_registry(base, [record], artifacts=artifacts, evidence_payloads={'synthetic:source': b'Synthetic mass passthrough evidence'})
    reviewed = reviewed_registry(base, [record], artifacts=artifacts, trusted_approvals={review_digest(record)}, evidence_payloads={'synthetic:source': b'Synthetic mass passthrough evidence'})
    assert activate(reviewed).evidence == 'hypothetical'
    # The registry receives its detached review even after caller edits.
    record.evidence_refs.clear()
    assert activate(reviewed).evidence == 'hypothetical'


@pytest.mark.parametrize('field,value,code', [
    ('disposition', 'blocked', 'host_review_required'),
    ('model', dict(id='other', version='v1'), 'review_model'),
    ('basis', 'unresolved', 'unsupported_activation'),
    ('basis', 'empirical', 'unsupported_activation'),
    ('declaration_digest', 'sha256:' + '0' * 64, 'mechanism_artifact_digest'),
    ('graph_digest', 'sha256:' + '0' * 64, 'review_graph'),
    ('evidence_refs', [], 'review_evidence_digest'),
    ('fixtures', [], 'review_fixtures'),
])
def test_activation_review_cannot_bypass_closure_even_with_host_hash(field, value, code):
    record, artifacts = review_case()
    record = ModelReview.model_validate(record.model_dump(mode='json') | {field: value})
    with pytest.raises(ContentError, match=code):
        authorize_review(record, registry=registry(reviews=[]), artifacts=artifacts, trusted_approvals={review_digest(record)}, evidence_payloads={'synthetic:source': b'Synthetic mass passthrough evidence'})


def test_changed_fixture_requires_new_host_review_and_actual_expectations():
    record, artifacts = review_case()
    artifacts['fixture.json'] = canonical({'id': 'synthetic:positive', 'version': 'v1', 'derivation': '', 'cases': []})
    with pytest.raises(ContentError, match='fixture_digest'):
        authorize_review(record, registry=registry(reviews=[]), artifacts=artifacts, trusted_approvals={review_digest(record)}, evidence_payloads={'synthetic:source': b'Synthetic mass passthrough evidence'})


def test_unknown_unit_parameter_cannot_pass_integrity_validation():
    metadata, artifacts = snapshot()
    source = json.loads(artifacts['interview.pack.json'])['definitions'][0]
    parameter = source | dict(id='interview:parameter', kind='parameter', parent_ref=None,
        parameter=dict(scope_id='local', value=dict(kind='quantity', value='7', unit_id='absent', time_basis_id=None, denominator_scope_id=None), validity_limits='Synthetic test only.'))
    repack(metadata, artifacts, 'interview.pack.json', lambda p: p['definitions'].append(parameter))
    from poliscope_engine.numeric import NumericError
    with pytest.raises(NumericError, match='unknown_unit'):
        Release(canonical(metadata), artifacts, registry=registry())


def test_full_release_activation_requires_exact_trusted_declaration_evidence_and_fixtures():
    metadata, artifacts = snapshot()
    record, model_artifacts = review_case()
    definition = definitions()[0]
    source_text = 'Synthetic mass passthrough evidence'
    license_text = (ROOT / 'LICENSE').read_text()
    files = {'LICENSE': license_text, 'evidence.md': source_text}
    summary = dict(id=definition.id, version=definition.version, kind='mechanism', parent_ref=None,
        original_text='Synthetic mass passthrough; not empirical content.', source_decision_id=None,
        source_refs=definition.source_refs, assumption_refs=definition.assumption_refs, supersedes_refs=[],
        mechanism_refs=[], variable_refs=[], origin=definition.origin, modeling=definition.modeling,
        evidence=definition.evidence, historical_status='unspecified')
    pack = PackArchive(canonical(dict(manifest=dict(format_version=1, id='synthetic:catalog', version='v1',
        identities={key: dict(id='synthetic-' + key, version='v1') for key in ('application', 'schema_identity', 'catalog', 'model', 'numeric')},
        engine_versions=['v1'], dependencies=[], files={p: digest(t.encode()) for p, t in files.items()}),
        files=[dict(path=p, text=t) for p, t in files.items()],
        licenses=[dict(id='test-mit', file='LICENSE', digest=digest(license_text.encode()))],
        sources=[dict(reference=dict(id='synthetic:source', repository_id='synthetic-tests', document_id='evidence.md',
            revision_id='0' * 40, location='Synthetic fixture only.', excerpt_digest=digest(source_text.encode()),
            license_id='test-mit', historical_status='unknown', supersedes_refs=[]), commit='0' * 40,
            excerpt_file='evidence.md', license_digest=digest(license_text.encode()))],
        definitions=[summary], assumptions=[], variables=[], distributions=[], dependence=[])))
    artifacts.update(model_artifacts | {'synthetic.pack.json': canonical(pack.pack.model_dump(mode='json'))})
    metadata['catalogs'].append(dict(artifact='synthetic.pack.json', pack_digest=pack.digest, role='authored'))
    metadata['artifacts'] = [dict(path=p, digest=digest(b)) for p, b in artifacts.items()]
    metadata['reviews'].append(record.model_dump(mode='json'))
    metadata['activated_review_refs'].append(record.id)
    with pytest.raises(ContentError, match='host_review_required'):
        Release(canonical(metadata), artifacts, registry=registry(reviews=[]))
    validated = Release(canonical(metadata), artifacts, registry=registry(reviews=[]), trusted_approvals={review_digest(record)})
    assert validated.metadata.activated_review_refs == [record.id]
    # Changing expected outputs while rehashing the release cannot reuse approval.
    changed = json.loads(artifacts['fixture.json'])
    changed['cases'][0]['expected'] = {'kg': '8'}
    artifacts['fixture.json'] = canonical(changed)
    metadata['reviews'][-1]['fixtures'][0]['digest'] = digest(artifacts['fixture.json'])
    next(a for a in metadata['artifacts'] if a['path'] == 'fixture.json')['digest'] = digest(artifacts['fixture.json'])
    with pytest.raises(ContentError, match='host_review_required'):
        Release(canonical(metadata), artifacts, registry=registry(reviews=[]), trusted_approvals={review_digest(record)})


def test_review_change_and_evidence_change_cannot_reuse_a_host_approval():
    record, artifacts = review_case()
    changed = record.model_copy(update={'validity_limits': 'Changed population extrapolation.'})
    with pytest.raises(ContentError, match='host_review_required'):
        authorize_review(changed, registry=registry(reviews=[]), artifacts=artifacts,
            trusted_approvals={review_digest(record)}, evidence_payloads={'synthetic:source': b'Synthetic mass passthrough evidence'})
    with pytest.raises(ContentError, match='review_evidence_digest'):
        authorize_review(record, registry=registry(reviews=[]), artifacts=artifacts,
            trusted_approvals={review_digest(record)}, evidence_payloads={'synthetic:source': b'Changed evidence'})
