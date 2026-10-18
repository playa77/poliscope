"""Synthetic archives only; independently computed digest/tamper expectations."""
import copy
import hashlib
import json
import pytest
from poliscope_engine.contracts.packs import PackIdentities
from poliscope_engine.packs import PackArchive, PackError, MAX_PACK_BYTES


def sha(text):
    return 'sha256:' + hashlib.sha256(text.encode()).hexdigest()


def definition(identity='test:mechanism', **changes):
    return dict(id=identity, version='v1', kind='mechanism', parent_ref=None,
                original_text='Synthetic complete original alternative', source_decision_id='1.a',
                source_refs=['test:source'], assumption_refs=[], supersedes_refs=[],
                mechanism_refs=[], variable_refs=[], origin='imported', modeling='qualitative',
                evidence='hypothetical', historical_status='adopted') | changes


def fixture():
    identities = {key: dict(id=key, version='v1') for key in
                  ('application', 'schema_identity', 'catalog', 'model', 'numeric')}
    return dict(manifest=dict(format_version=1, id='test:pack', version='v1',
                             identities=identities, engine_versions=['v1'], dependencies=[],
                             files={'excerpt.txt': sha('Original source'), 'LICENSE': sha('Synthetic license')}),
                files=[dict(path='excerpt.txt', text='Original source'), dict(path='LICENSE', text='Synthetic license')],
                licenses=[dict(id='synthetic', file='LICENSE', digest=sha('Synthetic license'))],
                sources=[dict(reference=dict(id='test:source', repository_id='synthetic', document_id='design',
                                             revision_id='a'*40, location='section 1', excerpt_digest=sha('Original source'),
                                             license_id='synthetic', historical_status='current', supersedes_refs=[]),
                              commit='a'*40, excerpt_file='excerpt.txt', license_digest=sha('Synthetic license'))],
                assumptions=[], definitions=[definition()], variables=[], distributions=[], dependence=[])


def archive(data=None):
    return PackArchive(json.dumps(data if data is not None else fixture()).encode())


def compatibility(value, **changes):
    args = dict(identities=value.pack.manifest.identities, engine_version='v1', mechanisms=frozenset())
    return value.compatibility(**(args | changes))


def test_qualitative_history_retains_adoption_without_player_default_or_activation():
    value = archive()
    assert value.pack.definitions[0].historical_status == 'adopted'
    assert value.pack.definitions[0].modeling == 'qualitative'
    assert compatibility(value).executable
    assert 'selected' not in value.pack.definitions[0].model_dump()


def test_detachment_and_semantic_digest():
    data = fixture()
    value = archive(data)
    data['files'][0]['text'] = 'changed'
    value.pack.manifest.files.clear()
    assert len(value.pack.files) == 2
    assert value.digest == archive().digest
    assert value.digest == sha(json.dumps(value.pack.model_dump(mode="json"), sort_keys=True, separators=(",", ":")))


@pytest.mark.parametrize('mutation,code', [
    (lambda p: p['files'][0].update(text='tampered'), 'file_digest'),
    (lambda p: p['files'].pop(), 'file_inventory'),
    (lambda p: p['files'].append(p['files'][0]), 'duplicate_identity'),
    (lambda p: p['licenses'][0].update(digest='sha256:'+'0'*64), 'license_digest'),
    (lambda p: p['sources'][0].update(license_digest='sha256:'+'0'*64), 'source_license'),
    (lambda p: p['sources'][0].update(commit='b'*40), 'source_revision'),
    (lambda p: p['sources'][0]['reference'].update(excerpt_digest='sha256:'+'0'*64), 'source_digest'),
    (lambda p: p['sources'][0]['reference'].update(supersedes_refs=['test:missing']), 'missing_reference'),
    (lambda p: p['sources'][0]['reference'].update(supersedes_refs=['test:source']), 'dependency_cycle'),
    (lambda p: p['definitions'].append(p['definitions'][0]), 'duplicate_identity'),
    (lambda p: p['definitions'][0].update(id='foreign:rule'), 'foreign_namespace'),
    (lambda p: p['definitions'][0].update(source_refs=['test:absent']), 'missing_reference'),
    (lambda p: p['definitions'][0].update(mechanism_refs=['test:absent']), 'missing_reference'),
    (lambda p: p['definitions'][0].update(variable_refs=['test:absent']), 'missing_reference'),
    (lambda p: p['definitions'][0].update(parent_ref='test:mechanism'), 'dependency_cycle'),
    (lambda p: p['definitions'][0].update(kind='question'), 'missing_alternatives'),
    (lambda p: p['definitions'][0].update(kind='option'), 'option_parent'),
])
def test_invalid_archive(mutation, code):
    data = fixture()
    mutation(data)
    with pytest.raises(PackError, match=code):
        archive(data)


@pytest.mark.parametrize('path', ['/absolute', '../escape', 'a/../escape', 'a//b', './a', '.'])
def test_paths_never_escape_or_alias(path):
    data = fixture()
    data['files'][0]['path'] = path
    data['manifest']['files'][path] = data['manifest']['files'].pop('excerpt.txt')
    with pytest.raises(PackError, match='unsafe_path'):
        archive(data)


@pytest.mark.parametrize('payload', [b'{"files":[],"files":[]}', b'\xff', b'[]', b'{'*2000])
def test_malformed_inputs(payload):
    with pytest.raises(PackError):
        PackArchive(payload)


def test_size_and_extra_code_fields_rejected():
    with pytest.raises(PackError, match='pack_size'):
        PackArchive(b' '*(MAX_PACK_BYTES+1))
    data = fixture()
    data['definitions'][0]['python'] = 'raise Exception()'
    with pytest.raises(PackError):
        archive(data)


def test_source_text_is_data_only(tmp_path):
    target = tmp_path / 'executed'
    data = fixture()
    text = f"__import__('pathlib').Path({str(target)!r}).touch()"
    data['files'][0]['text'] = text
    data['manifest']['files']['excerpt.txt'] = sha(text)
    data['sources'][0]['reference']['excerpt_digest'] = sha(text)
    archive(data)
    assert not target.exists()


def test_original_compound_question_alternatives_and_citation_ids():
    data = fixture()
    data['definitions'] = [definition('test:question', kind='question'),
                           definition('test:option/a', kind='option', parent_ref='test:question'),
                           definition('test:option/b', kind='option', parent_ref='test:question')]
    result = archive(data).pack
    assert [d.source_decision_id for d in result.definitions] == ['1.a']*3
    assert len({d.id for d in result.definitions}) == 3
    assert all(d.original_text == 'Synthetic complete original alternative' for d in result.definitions)


def test_unavailable_historical_mechanism_is_readable_but_not_executable():
    data = fixture()
    data['definitions'][0].update(modeling='numerical', evidence='supported')
    value = archive(data)
    assert 'mechanism_unavailable:test:mechanism' in compatibility(value).reasons
    assert compatibility(value, mechanisms=frozenset({('test:mechanism', 'v1')})).executable
    assert not compatibility(value, mechanisms=frozenset({('test:mechanism', 'old')})).executable
    data['definitions'][0]['evidence'] = 'hypothetical'
    assert not compatibility(archive(data), mechanisms=frozenset({('test:mechanism', 'v1')})).executable


def test_identity_and_engine_compatibility_are_separate_from_readability():
    value = archive()
    assert not compatibility(value, engine_version='old').executable
    for key in ('application', 'schema_identity', 'catalog', 'model', 'numeric'):
        identities = value.pack.manifest.identities.model_dump()
        identities[key]['version'] = 'old'
        assert not compatibility(value, identities=PackIdentities.model_validate(identities)).executable


def test_pinned_dependencies_and_transitive_closure():
    leaf_data = json.loads(json.dumps(fixture()).replace('test:', 'leaf:'))
    leaf = archive(leaf_data)
    middle_data = json.loads(json.dumps(fixture()).replace('test:', 'middle:'))
    middle_data['manifest']['dependencies'] = [dict(id='leaf:pack', version='v1', digest=leaf.digest)]
    middle = archive(middle_data)
    root_data = fixture()
    root_data['manifest']['dependencies'] = [dict(id='middle:pack', version='v1', digest=middle.digest)]
    root = archive(root_data)
    assert not compatibility(root).executable
    assert not compatibility(root, dependencies=[middle]).executable
    assert compatibility(root, dependencies=[middle, leaf]).executable
    for key, value in [('version', 'v2'), ('digest', 'sha256:'+'0'*64)]:
        changed = copy.deepcopy(root_data)
        changed['manifest']['dependencies'][0][key] = value
        assert not compatibility(archive(changed), dependencies=[middle, leaf]).executable


def uncertainty(data):
    data['variables'] = [dict(id=f'test:{name}', version='v1', scope_id='local', form='distribution',
                              definition='Synthetic uncertain input', distribution_ref='test:joint', source_refs=['test:source'])
                         for name in ('rain', 'yield')]
    data['distributions'] = [dict(id='test:joint', version='v1', kind='joint', variable_refs=['test:rain', 'test:yield'],
                                 conditioning_refs=[], definition='Synthetic correlated distribution', sampling_rule_ref=None)]
    data['dependence'] = [dict(id='test:dependence', version='v1', variable_refs=['test:rain', 'test:yield'],
                              kind='joint', definition_ref='test:joint', rationale='Shared rain realization')]
    data['definitions'][0]['variable_refs'] = ['test:rain', 'test:rain', 'test:yield']
    return data


def test_shared_variable_is_preserved_and_not_resampled():
    value = archive(uncertainty(fixture()))
    assert value.pack.definitions[0].variable_refs == ['test:rain', 'test:rain', 'test:yield']
    assert value.pack.dependence[0].kind == 'joint'


@pytest.mark.parametrize('mutation,code', [
    (lambda p: p.update(dependence=[]), 'undeclared_dependence'),
    (lambda p: p['dependence'].append(p['dependence'][0] | dict(id='test:other')), 'ambiguous_dependence'),
    (lambda p: p['dependence'][0].update(definition_ref='test:missing'), 'missing_reference'),
    (lambda p: p['distributions'][0].update(variable_refs=['test:rain']), 'distribution_membership'),
    (lambda p: p['variables'][0].update(distribution_ref=None), 'missing_distribution'),
    (lambda p: p['distributions'][0].update(conditioning_refs=['test:rain']), 'duplicate_distribution_variable'),
])
def test_no_implicit_independence_or_broken_uncertainty(mutation, code):
    data = uncertainty(fixture())
    mutation(data)
    with pytest.raises(PackError, match=code):
        archive(data)


@pytest.mark.parametrize('kind', ['independent', 'unresolved', 'common_cause', 'conditional'])
def test_explicit_dependency_models(kind):
    data = uncertainty(fixture())
    relation = data['dependence'][0]
    relation.update(kind=kind, definition_ref=None)
    if kind != 'conditional':
        data['distributions'] = [dict(id='test:dist-'+name, version='v1', kind='marginal',
                                     variable_refs=['test:'+name], conditioning_refs=[],
                                     definition='Synthetic marginal', sampling_rule_ref=None)
                                 for name in ('rain', 'yield')]
        for variable in data['variables']:
            variable['distribution_ref'] = 'test:dist-' + variable['id'].split(':')[1]
    if kind == 'common_cause':
        data['variables'].append(dict(id='test:climate', version='v1', scope_id='local', form='qualitative',
                                      definition='Common climate cause', distribution_ref=None, source_refs=[]))
        relation['definition_ref'] = 'test:climate'
        for child in ('rain', 'yield'):
            data['dependence'].append(dict(id='test:climate-'+child, version='v1', variable_refs=['test:climate', 'test:'+child],
                                          kind='unresolved', definition_ref=None, rationale='No implicit independence'))
    if kind == 'conditional':
        data['distributions'][0].update(kind='conditional', variable_refs=['test:yield'], conditioning_refs=['test:rain'])
        data['variables'][0].update(form='qualitative', distribution_ref=None)
        relation['definition_ref'] = 'test:joint'
    assert archive(data).pack.dependence[0].kind == kind


def test_assumption_validity_and_version_binding():
    data = uncertainty(fixture())
    data['assumptions'] = [dict(reference=dict(id='test:assumption', scope_id='local', definition_id='test:mechanism',
                                             definition_version='v1', origin='authored', uncertainty_form='distribution',
                                             uncertainty_definition_ref='test:rain', rationale='Synthetic rationale', source_refs=['test:source']),
                                validity_limits='Synthetic local scope only')]
    data['definitions'][0]['assumption_refs'] = ['test:assumption']
    assert archive(data).pack.assumptions[0].validity_limits == 'Synthetic local scope only'
    data['assumptions'][0]['reference']['definition_version'] = 'old'
    with pytest.raises(PackError, match='assumption_version'):
        archive(data)


def test_expected_archive_digest_detects_metadata_tampering_and_key_order_is_stable():
    data = fixture()
    first = archive(data)
    PackArchive(json.dumps(data, sort_keys=True).encode(), expected_digest=first.digest)
    data['definitions'][0]['historical_status'] = 'alternative'
    with pytest.raises(PackError, match='pack_digest'):
        PackArchive(json.dumps(data).encode(), expected_digest=first.digest)


def test_distribution_and_unresolved_dependence_never_gain_execution_by_parsing():
    data = uncertainty(fixture())
    assert 'sampling_unavailable:test:joint' in compatibility(archive(data)).reasons
    data['dependence'][0].update(kind='unresolved', definition_ref=None)
    with pytest.raises(PackError, match='conflicting_dependence'):
        archive(data)
    data['variables'][0].update(form='qualitative', distribution_ref=None)
    data['variables'][1].update(form='qualitative', distribution_ref=None)
    data['distributions'] = []
    assert 'dependence_unresolved:test:dependence' in compatibility(archive(data)).reasons


@pytest.mark.parametrize('kind', ['parameter', 'measurement'])
def test_typed_declarations_are_required(kind):
    data = fixture()
    data['definitions'][0]['kind'] = kind
    with pytest.raises(PackError, match=kind+'_declaration'):
        archive(data)
    data['definitions'][0][kind] = (dict(scope_id='local', value=dict(kind='unknown', reason='unmeasured'),
                                        validity_limits='Only synthetic local data') if kind == 'parameter' else
                                    dict(scope_id='local', unit_id='kg', time_basis_id='year',
                                         interpretation='Annual synthetic output', coverage_limits='No empirical claim'))
    assert getattr(archive(data).pack.definitions[0], kind).scope_id == 'local'


def test_sampling_reference_must_name_available_trusted_implementation():
    data = uncertainty(fixture())
    data['distributions'][0]['sampling_rule_ref'] = 'test:mechanism'
    assert not compatibility(archive(data), mechanisms=frozenset({('test:mechanism', 'v1')})).executable
    data['definitions'][0].update(modeling='numerical', evidence='supported')
    assert compatibility(archive(data), mechanisms=frozenset({('test:mechanism', 'v1')})).executable


def test_self_and_duplicate_dependencies_are_rejected_before_compatibility():
    data = fixture()
    data['manifest']['dependencies'] = [dict(id='test:pack', version='v1', digest='sha256:'+'0'*64)]
    with pytest.raises(PackError, match='dependency_cycle'):
        archive(data)
    data = fixture()
    row = dict(id='test:dependency', version='v1', digest='sha256:'+'0'*64)
    data['manifest']['dependencies'] = [row, row]
    with pytest.raises(PackError, match='duplicate_identity'):
        archive(data)


def test_dependency_bundle_rejects_colliding_canonical_game_ids():
    dependency_data = fixture()
    dependency_data['manifest']['id'] = 'test:other-pack'
    dependency = archive(dependency_data)
    data = fixture()
    data['manifest']['dependencies'] = [dict(id='test:other-pack', version='v1', digest=dependency.digest)]
    with pytest.raises(PackError, match='duplicate_bundle_identity'):
        compatibility(archive(data), dependencies=[dependency])


def test_joint_distribution_cannot_be_relabelled_as_independent():
    data = uncertainty(fixture())
    data['dependence'][0].update(kind='independent', definition_ref=None)
    with pytest.raises(PackError, match='conflicting_dependence'):
        archive(data)


def test_conditional_cycle_is_not_implicitly_sampled():
    data = uncertainty(fixture())
    data['distributions'] = [dict(id='test:rain-given-yield', version='v1', kind='conditional',
                                 variable_refs=['test:rain'], conditioning_refs=['test:yield'],
                                 definition='Synthetic', sampling_rule_ref=None),
                             dict(id='test:yield-given-rain', version='v1', kind='conditional',
                                 variable_refs=['test:yield'], conditioning_refs=['test:rain'],
                                 definition='Synthetic', sampling_rule_ref=None)]
    for variable, distribution in zip(data['variables'], data['distributions']):
        variable['distribution_ref'] = distribution['id']
    data['dependence'][0].update(kind='conditional', definition_ref='test:rain-given-yield')
    with pytest.raises(PackError, match='conflicting_dependence|dependency_cycle'):
        archive(data)
