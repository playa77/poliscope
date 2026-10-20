"""Bounded immutable release reader and host-controlled model review bridge.

Successful validation establishes integrity, never empirical validity. Imported
JSON cannot grant approval, install callbacks or select a player's policies.
"""
import json
from functools import lru_cache
from pathlib import Path, PurePosixPath
from poliscope_engine.contracts.content import ContentRelease, ModelReview
from poliscope_engine.packs import PackArchive, digest, _unique_json
from poliscope_engine.corpus import canonical
from poliscope_engine.mechanisms import Review, declaration_digest
from poliscope_engine.numeric import parse

MAX_RELEASE_BYTES = 32 * 1024 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024


class ContentError(ValueError):
    pass


def decode(payload):
    if len(payload) > MAX_FILE_BYTES:
        raise ContentError('artifact_size')
    return json.loads(payload.decode('utf-8'), object_pairs_hook=_unique_json)


def unique(rows, key=lambda row: row.id):
    result = {}
    for row in rows:
        identity = key(row)
        if identity in result:
            raise ContentError('duplicate_identity')
        result[identity] = row
    return result


def require(refs, available):
    if len(refs) != len(set(refs)) or not set(refs) <= set(available):
        raise ContentError('invalid_reference')


def safe_path(path):
    if (not path or path == '.' or path.startswith('/') or '..' in path.split('/')
            or str(PurePosixPath(path)) != path or '\\' in path):
        raise ContentError('unsafe_path')
    return path


def review_digest(record):
    return digest(canonical(record.model_dump(mode='json')))


def authorize_review(record: ModelReview, *, registry, artifacts, trusted_approvals=(), evidence_payloads=None):
    """A host allowlist binds the entire record, not an untrusted 'approved' label.

    Fixture files preserve independently derived expectations. The host must run
    and review them before adding the record digest to its code-owned approvals.
    This function verifies closure, not the truth of a prose scientific claim.
    Runtime activation still checks context, unit types, ownership and graph shape.
    """
    if record.disposition != 'approved' or review_digest(record) not in trusted_approvals:
        raise ContentError('host_review_required')
    if (record.model is None or (record.model.id, record.model.version) != registry.model
            or not record.mechanism_ref or not record.mechanism_version):
        raise ContentError('review_model')
    definition = registry.definition(record.mechanism_ref, record.mechanism_version)
    from poliscope_engine.contracts.mechanisms import MechanismDefinition
    if record.mechanism_artifact is None or safe_path(record.mechanism_artifact) not in artifacts:
        raise ContentError('missing_mechanism_artifact')
    archived = MechanismDefinition.model_validate_json(json.dumps(decode(artifacts[record.mechanism_artifact])))
    if declaration_digest(archived) != record.declaration_digest:
        raise ContentError('mechanism_artifact_digest')
    if (definition.modeling not in ('numerical', 'procedural')
            or definition.evidence not in ('supported', 'hypothetical')
            or record.basis == 'unresolved'
            or (record.basis == 'hypothetical' and definition.evidence != 'hypothetical')
            or (record.basis == 'empirical' and definition.evidence != 'supported')
            or record.declaration_digest != declaration_digest(definition)):
        raise ContentError('unsupported_activation')
    for field in ('operational_definition', 'formula_or_procedure', 'denominator_time_scope', 'uncertainty', 'invariants', 'validity_limits', 'unsupported_extrapolation', 'review_notes'):
        if not getattr(record, field).strip():
            raise ContentError('empty_review')
    evidence_payloads = evidence_payloads or {}
    if set(record.evidence_digests) != set(record.evidence_refs) or any(ref not in evidence_payloads or digest(evidence_payloads[ref]) != expected for ref, expected in record.evidence_digests.items()):
        raise ContentError('review_evidence_digest')
    require(record.evidence_refs, registry.source_ids)
    if not record.evidence_refs or not set(definition.source_refs) <= set(record.evidence_refs):
        raise ContentError('review_evidence')
    fixtures = unique(record.fixtures, lambda f: (f.identity.id, f.identity.version, f.purpose))
    declared = {(f.fixture.id, f.fixture.version, f.purpose) for f in definition.fixtures}
    if not declared or set(fixtures) != declared:
        raise ContentError('review_fixtures')
    for fixture in fixtures.values():
        if (fixture.identity.id, fixture.identity.version) not in registry.fixture_ids:
            raise ContentError('unregistered_fixture')
        safe_path(fixture.artifact)
        if fixture.artifact not in artifacts:
            raise ContentError('missing_fixture')
        if digest(artifacts[fixture.artifact]) != fixture.digest:
            raise ContentError('fixture_digest')
        # Expected cases are data with identity, derivation and concrete I/O,
        # rather than a fixture ID asserted to be evidence.
        value = decode(artifacts[fixture.artifact])
        if (set(value) != {'id', 'version', 'derivation', 'cases'}
                or (value['id'], value['version']) != (fixture.identity.id, fixture.identity.version)
                or not isinstance(value['derivation'], str) or not value['derivation'].strip()
                or not isinstance(value['cases'], list) or not value['cases']):
            raise ContentError('invalid_fixture')
        for case in value['cases']:
            if not isinstance(case, dict) or set(case) != {'inputs', 'expected'} or not isinstance(case['inputs'], dict):
                raise ContentError('invalid_fixture')
    graph_digests = set()
    for phase in ('static', 'transition'):
        procedure = getattr(definition.support, phase)
        if procedure is None:
            continue
        if procedure.kind == 'declarative_graph':
            from poliscope_engine.mechanisms.expressions import graph_digest
            graph_digests.add(graph_digest(registry._graph(procedure)))
        elif (procedure.implementation.id, procedure.implementation.version, phase) not in {i.key for i in registry.implementations}:
            raise ContentError('unregistered_implementation')
    # Distinct static/transition graphs need separately reviewed declarations.
    if len(graph_digests) > 1 or record.graph_digest != next(iter(graph_digests), None):
        raise ContentError('review_graph')
    return Review(record.declaration_digest, record.model.id, record.model.version,
                  record.id, 'fixture-review:' + review_digest(record), record.graph_digest)


class Release:
    def __init__(self, manifest: bytes, artifacts: dict[str, bytes], *, registry=None, trusted_approvals=()):
        self._manifest = canonical(ContentRelease.model_validate_json(json.dumps(decode(manifest))).model_dump(mode='json'))
        metadata = self.metadata
        expected = unique(metadata.artifacts, lambda row: row.path)
        if set(expected) != set(artifacts):
            raise ContentError('artifact_inventory')
        if len(manifest) + sum(map(len, artifacts.values())) > MAX_RELEASE_BYTES:
            raise ContentError('release_size')
        for path, payload in artifacts.items():
            safe_path(path)
            if len(payload) > MAX_FILE_BYTES or digest(payload) != expected[path].digest:
                raise ContentError('artifact_digest')
        # bytes and a private copy prevent caller mutations after validation.
        self._artifacts = {key: bytes(value) for key, value in artifacts.items()}
        self.digest = digest(self._manifest)
        catalogs = unique(metadata.catalogs, lambda row: row.artifact)
        archives = [PackArchive(artifacts[row.artifact], expected_digest=row.pack_digest) for row in catalogs.values()]
        unique([a.pack.manifest for a in archives])
        definitions = unique([d for a in archives for d in a.pack.definitions])
        sources = unique([s for a in archives for s in a.pack.sources], lambda row: row.reference.id)
        # Authored content has an explicit copyright/license archive too.
        if any(not a.pack.licenses or not a.pack.sources for a in archives):
            raise ContentError('attribution_required')
        if any(not d.source_refs for d in definitions.values()):
            raise ContentError('attribution_required')
        for archive in archives:
            if archive.pack.manifest.dependencies:
                raise ContentError('release_dependencies_not_supported')
        evidence_payloads = {s.reference.id: next(f.text.encode() for f in a.pack.files if f.path == s.excerpt_file)
                             for a in archives for s in a.pack.sources}
        reviews = unique(metadata.reviews)
        for review in reviews.values():
            require(review.candidate_refs, definitions)
            require(review.evidence_refs, sources)
            if set(review.evidence_digests) != set(review.evidence_refs) or any(sources[ref].reference.excerpt_digest != expected for ref, expected in review.evidence_digests.items()):
                raise ContentError('review_evidence_digest')
            if not review.candidate_refs:
                raise ContentError('review_candidate_required')
            for field in ('operational_definition', 'formula_or_procedure', 'denominator_time_scope',
                          'uncertainty', 'invariants', 'validity_limits', 'unsupported_extrapolation', 'review_notes'):
                if not getattr(review, field).strip():
                    raise ContentError('empty_review')
            for fixture in review.fixtures:
                if safe_path(fixture.artifact) not in artifacts or digest(artifacts[fixture.artifact]) != fixture.digest:
                    raise ContentError('fixture_digest')
            if review.disposition == 'approved' and (not review.fixtures or not review.evidence_refs):
                raise ContentError('review_closure')
        require(metadata.activated_review_refs, reviews)
        for ref in metadata.activated_review_refs:
            if registry is None:
                raise ContentError('host_review_required')
            review = reviews[ref]
            declaration = definitions.get(review.mechanism_ref)
            trusted = registry.definition(review.mechanism_ref, review.mechanism_version)
            if declaration is None or declaration.kind != 'mechanism' or any(getattr(declaration, field) != getattr(trusted, field) for field in ('id', 'version', 'source_refs', 'assumption_refs', 'origin', 'modeling', 'evidence')):
                raise ContentError('activation_declaration')
            authorize_review(reviews[ref], registry=registry, artifacts=artifacts, trusted_approvals=trusted_approvals, evidence_payloads=evidence_payloads)
        activated = {reviews[ref].mechanism_ref for ref in metadata.activated_review_refs}
        # No executable declaration may evade the activation manifest.
        if {d.id for d in definitions.values() if d.modeling in ('numerical', 'procedural')} != activated:
            raise ContentError('activation_inventory')
        for definition in definitions.values():
            if definition.parameter or definition.measurement:
                if registry is None:
                    raise ContentError('unit_registry_required')
                quantity = definition.parameter.value if definition.parameter else None
                unit_id = quantity.unit_id if quantity and quantity.kind == 'quantity' else (definition.measurement.unit_id if definition.measurement else None)
                if unit_id is not None:
                    unit = registry.units.unit(unit_id)
                time_id = quantity.time_basis_id if quantity and quantity.kind == 'quantity' else (definition.measurement.time_basis_id if definition.measurement else None)
                if time_id is not None and time_id not in {t.id for t in registry.times}:
                    raise ContentError('unknown_time_basis')
                if unit_id is not None and (unit.kind in ('flow', 'capacity') and time_id is None or unit.kind not in ('flow', 'capacity', 'indicator') and time_id is not None):
                    raise ContentError('invalid_time_basis')
                if quantity and quantity.kind == 'quantity':
                    parse(quantity.value)
        templates = unique(metadata.templates, lambda row: row.question.id)
        template_domains = []
        for template in templates.values():
            require([template.domain_ref], definitions)
            template_domains.append(template.domain_ref)
            if definitions[template.domain_ref].kind != 'domain' or template.question.kind != 'question':
                raise ContentError('template_domain')
            rows = [template.question, *template.options]
            for row in rows:
                if row.id not in definitions or row != definitions[row.id] or row.modeling != 'qualitative':
                    raise ContentError('template_definition')
            option_refs = [o.id for o in template.options]
            require(option_refs, definitions)
            if set(option_refs) != {d.id for d in definitions.values() if d.kind == 'option' and d.parent_ref == template.question.id}:
                raise ContentError('template_alternatives')
            if any(o.kind != 'option' or o.parent_ref != template.question.id for o in template.options):
                raise ContentError('template_options')
            if any(len(values) != len(template.options) for values in (template.labels, template.mechanisms, template.benefits, template.costs)):
                raise ContentError('template_cards')
        domains = {d.id for d in definitions.values() if d.kind == 'domain'}
        require(template_domains, domains)
        if set(template_domains) != domains:
            raise ContentError('template_coverage')
        unique(metadata.inquiries)
        for inquiry in metadata.inquiries:
            require(inquiry.domain_refs, domains)
        if {ref for row in metadata.inquiries for ref in row.domain_refs} != domains:
            raise ContentError('inquiry_coverage')
        coverage = unique(metadata.coverage, lambda row: row.branch_ref)
        branches = {d.id for d in definitions.values() if d.kind == 'branch' and d.parent_ref is not None
                    and (definitions[d.parent_ref].kind == 'domain' or definitions[d.parent_ref].parent_ref in domains)}
        if set(coverage) != branches:
            raise ContentError('branch_coverage')
        for row in coverage.values():
            if not row.reason.strip():
                raise ContentError('coverage_reason')
        setups = unique(metadata.setups)
        if 'blank' not in setups or setups['blank'].kind != 'neutral':
            raise ContentError('neutral_setup_required')
        for setup in setups.values():
            require(setup.selected_option_refs, definitions)
            require(setup.source_refs, sources)
            if any(definitions[ref].kind != 'option' or definitions[ref].historical_status in ('provenance', 'superseded') for ref in setup.selected_option_refs):
                raise ContentError('invalid_setup_option')
            parents = [definitions[ref].parent_ref for ref in setup.selected_option_refs]
            if len(parents) != len(set(parents)):
                raise ContentError('conflicting_setup_choices')
            if setup.kind != 'historical' and setup.selected_option_refs:
                raise ContentError('implicit_policy')
            if setup.kind == 'historical' and not setup.source_refs:
                raise ContentError('setup_attribution')
            if setup.kind == 'neutral' and (setup.population is not None or setup.land_area is not None):
                raise ContentError('neutral_conditions')
            for field in ('population', 'land_area'):
                value = getattr(setup, field)
                if value is not None and (parse(value) < 0 or field == 'population' and parse(value) != parse(value).to_integral_value()):
                    raise ContentError('invalid_setup_quantity')

    @property
    def metadata(self):
        return ContentRelease.model_validate_json(self._manifest)

    def artifact(self, path):
        return self._artifacts[path]

    def setup(self, identity, *, explicitly_selected=False):
        setup = next((s for s in self.metadata.setups if s.id == identity), None)
        if setup is None:
            raise ContentError('unknown_setup')
        if setup.kind != 'neutral' and not explicitly_selected:
            raise ContentError('explicit_selection_required')
        return setup


def load_release(root: Path, **kwargs):
    """Read only bounded regular files; reject links, undeclared and special files."""
    if root.is_symlink():
        raise ContentError('unsafe_release_root')
    artifacts = {}
    total = 0
    for path in root.rglob('*'):
        if path.is_symlink() or not path.is_file() and not path.is_dir():
            raise ContentError('unsafe_artifact')
        if path.is_file():
            total += path.stat().st_size
            if path.stat().st_size > MAX_FILE_BYTES or total > MAX_RELEASE_BYTES:
                raise ContentError('release_size')
            artifacts[path.relative_to(root).as_posix()] = path.read_bytes()
    if 'release.json' not in artifacts:
        raise ContentError('missing_manifest')
    return Release(artifacts.pop('release.json'), artifacts, **kwargs)


def reviewed_registry(registry, records, *, artifacts, trusted_approvals=(), evidence_payloads=None):
    """Attach only host-approved release reviews; preserve all trusted registries."""
    from poliscope_engine.mechanisms import MechanismRegistry
    reviews = tuple(authorize_review(r, registry=registry, artifacts=artifacts,
                    trusted_approvals=trusted_approvals, evidence_payloads=evidence_payloads) for r in records)
    return MechanismRegistry(model=registry.model, units=registry.units, times=registry.times,
        source_ids=registry.source_ids, assumption_ids=registry.assumption_ids,
        fixture_ids=registry.fixture_ids, implementations=registry.implementations,
        definitions=registry.definitions, graphs=registry.graphs, reviews=(*registry.reviews, *reviews))


@lru_cache(maxsize=1)
def bundled_release():
    import sys
    root = (Path(sys._MEIPASS) / 'poliscope_content' if getattr(sys, 'frozen', False)
            else Path(__file__).resolve().parents[3] / 'content' / 'release-v1')
    return load_release(root)
