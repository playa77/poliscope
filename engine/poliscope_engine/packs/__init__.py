"""Bounded archive inspection and explicit, nonactivating compatibility checks."""
from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations
import json
import re
from pathlib import PurePosixPath

from poliscope_engine.contracts.packs import Pack, PackIdentities

MAX_PACK_BYTES = 8 * 1024 * 1024


class PackError(ValueError):
    pass


def digest(data: bytes) -> str:
    return 'sha256:' + sha256(data).hexdigest()


def _index(rows, key=lambda row: row.id):
    result = {}
    for row in rows:
        identity = key(row)
        if identity in result:
            raise PackError('duplicate_identity')
        result[identity] = row
    return result


def _require(refs, available):
    if not set(refs) <= set(available):
        raise PackError('missing_reference')


def _acyclic(edges):
    done, active = set(), set()
    for root in edges:
        stack = [(root, False)]
        while stack:
            node, leaving = stack.pop()
            if leaving:
                active.remove(node)
                done.add(node)
            elif node in active:
                raise PackError('dependency_cycle')
            elif node not in done:
                active.add(node)
                stack.append((node, True))
                stack.extend((child, False) for child in edges.get(node, ()))


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PackError('duplicate_json_key')
        result[key] = value
    return result


@dataclass(frozen=True)
class Compatibility:
    executable: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True, init=False)
class PackArchive:
    """Detached validated snapshot. No paths are opened and no text is executed."""
    _json: str
    digest: str

    def __init__(self, payload: bytes, *, expected_digest: str | None = None):
        if not isinstance(payload, bytes) or len(payload) > MAX_PACK_BYTES:
            raise PackError('pack_size')
        try:
            # Decode strictly and reject duplicate keys before Pydantic parsing.
            data = json.loads(payload.decode('utf-8'), object_pairs_hook=_unique_json)
            pack = Pack.model_validate_json(json.dumps(data))
        except (ValueError, RecursionError) as error:
            raise PackError('invalid_pack') from error
        self._validate(pack)
        canonical = json.dumps(pack.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        if expected_digest is not None and digest(canonical.encode()) != expected_digest:
            raise PackError("pack_digest")
        object.__setattr__(self, '_json', canonical)
        object.__setattr__(self, 'digest', digest(canonical.encode()))

    @property
    def pack(self):
        return Pack.model_validate_json(self._json)

    @staticmethod
    def _validate(pack):
        files = _index(pack.files, lambda row: row.path)
        if set(files) != set(pack.manifest.files):
            raise PackError('file_inventory')
        for path, file in files.items():
            if path == '.' or str(PurePosixPath(path)) != path or '..' in path.split('/') or path.startswith('/'):
                raise PackError('unsafe_path')
            if digest(file.text.encode()) != pack.manifest.files[path]:
                raise PackError('file_digest')
        licenses = _index(pack.licenses)
        for license in licenses.values():
            if license.file not in files or pack.manifest.files[license.file] != license.digest:
                raise PackError('license_digest')
        sources = _index(pack.sources, lambda row: row.reference.id)
        assumptions = _index(pack.assumptions, lambda row: row.reference.id)
        definitions = _index(pack.definitions)
        variables = _index(pack.variables)
        distributions = _index(pack.distributions)
        dependence = _index(pack.dependence)
        _index(pack.manifest.dependencies)
        if any(row.id == pack.manifest.id for row in pack.manifest.dependencies):
            raise PackError('dependency_cycle')
        all_ids = [*sources, *assumptions, *definitions, *variables, *distributions, *dependence]
        if len(set(all_ids)) != len(all_ids) or pack.manifest.id in all_ids:
            raise PackError('duplicate_identity')
        namespace = pack.manifest.id.split(':')[0] + ':'
        if any(not key.startswith(namespace) or re.fullmatch(r'[a-z][a-z0-9_.-]*:[a-zA-Z0-9_./-]+', key) is None for key in all_ids):
            raise PackError('foreign_namespace')
        for source in sources.values():
            ref = source.reference
            if ref.revision_id != source.commit:
                raise PackError('source_revision')
            if ref.license_id not in licenses or source.license_digest != licenses[ref.license_id].digest:
                raise PackError('source_license')
            if source.excerpt_file not in files or pack.manifest.files[source.excerpt_file] != ref.excerpt_digest:
                raise PackError('source_digest')
            _require(ref.supersedes_refs, sources)
        _acyclic({key: row.reference.supersedes_refs for key, row in sources.items()})
        for assumption in assumptions.values():
            ref = assumption.reference
            _require(ref.source_refs, sources)
            _require([ref.definition_id], definitions)
            if definitions[ref.definition_id].version != ref.definition_version:
                raise PackError('assumption_version')
            if ref.uncertainty_definition_ref is not None:
                _require([ref.uncertainty_definition_ref], variables)
                variable = variables[ref.uncertainty_definition_ref]
                if variable.form != ref.uncertainty_form or variable.scope_id != ref.scope_id:
                    raise PackError('assumption_uncertainty')
            elif ref.uncertainty_form == 'distribution':
                raise PackError('missing_distribution')
        for definition in definitions.values():
            if (definition.kind == 'parameter') != (definition.parameter is not None):
                raise PackError('parameter_declaration')
            if (definition.kind == 'measurement') != (definition.measurement is not None):
                raise PackError('measurement_declaration')
            _require(definition.source_refs, sources)
            _require(definition.assumption_refs, assumptions)
            _require(definition.supersedes_refs, definitions)
            _require(definition.mechanism_refs, definitions)
            _require(definition.variable_refs, variables)
            if any(definitions[key].kind != 'mechanism' for key in definition.mechanism_refs):
                raise PackError('invalid_mechanism_reference')
            if definition.parent_ref is not None:
                _require([definition.parent_ref], definitions)
            if definition.kind == 'option' and (definition.parent_ref is None or definitions[definition.parent_ref].kind != 'question'):
                raise PackError('option_parent')
            if definition.kind == 'question' and not any(row.kind == 'option' and row.parent_ref == definition.id for row in definitions.values()):
                raise PackError('missing_alternatives')
        _acyclic({key: row.supersedes_refs for key, row in definitions.items()})
        _acyclic({key: [row.parent_ref] if row.parent_ref else [] for key, row in definitions.items()})
        for variable in variables.values():
            _require(variable.source_refs, sources)
            if variable.distribution_ref is not None and variable.form != 'distribution':
                raise PackError('unexpected_distribution')
            if variable.distribution_ref is not None:
                _require([variable.distribution_ref], distributions)
                if variable.id not in distributions[variable.distribution_ref].variable_refs:
                    raise PackError('distribution_membership')
            elif variable.form == 'distribution':
                raise PackError('missing_distribution')
        for distribution in distributions.values():
            refs = distribution.variable_refs + distribution.conditioning_refs
            _require(refs, variables)
            if len(set(refs)) != len(refs):
                raise PackError('duplicate_distribution_variable')
            if distribution.kind == 'marginal' and len(distribution.variable_refs) != 1:
                raise PackError('distribution_arity')
            if (distribution.kind == 'conditional') != bool(distribution.conditioning_refs):
                raise PackError('distribution_conditioning')
            if distribution.sampling_rule_ref is not None:
                _require([distribution.sampling_rule_ref], definitions)
                if definitions[distribution.sampling_rule_ref].kind != 'mechanism':
                    raise PackError('invalid_mechanism_reference')
        pairs = {}
        for relation in dependence.values():
            _require(relation.variable_refs, variables)
            if len(set(relation.variable_refs)) != len(relation.variable_refs):
                raise PackError('duplicate_dependence_variable')
            if relation.kind in ('joint', 'conditional'):
                _require([relation.definition_ref], distributions)
                model = distributions[relation.definition_ref]
                if model.kind != relation.kind or set(relation.variable_refs) != set(model.variable_refs + model.conditioning_refs):
                    raise PackError('dependence_definition')
            elif relation.kind == 'common_cause':
                _require([relation.definition_ref], variables)
                if relation.definition_ref in relation.variable_refs:
                    raise PackError('self_cause')
            elif relation.definition_ref is not None:
                raise PackError('unexpected_dependence_definition')
            for pair in combinations(sorted(relation.variable_refs), 2):
                if pair in pairs:
                    raise PackError('ambiguous_dependence')
                pairs[pair] = (relation.kind, relation.definition_ref)
        # Every pair is declared, including explicit unresolved relationships.
        if set(pairs) != set(combinations(sorted(variables), 2)):
            raise PackError('undeclared_dependence')
        conditional_edges = {}
        for distribution in distributions.values():
            if distribution.kind in ('joint', 'conditional'):
                members = distribution.variable_refs + distribution.conditioning_refs
                for pair in combinations(sorted(members), 2):
                    # Conditioning variables may have their own declared relation.
                    if all(key in distribution.conditioning_refs for key in pair):
                        continue
                    if pairs[pair] != (distribution.kind, distribution.id):
                        raise PackError('conflicting_dependence')
            for target in distribution.variable_refs:
                conditional_edges.setdefault(target, []).extend(distribution.conditioning_refs)
        for relation in dependence.values():
            if relation.kind == 'common_cause':
                for target in relation.variable_refs:
                    conditional_edges.setdefault(target, []).append(relation.definition_ref)
        _acyclic(conditional_edges)

    def compatibility(self, *, identities: PackIdentities, engine_version: str,
                      mechanisms: frozenset[tuple[str, str]], dependencies=()):
        """Report availability; never activate imports, code, or numerical rules."""
        resolved = _index(dependencies, lambda archive: archive.pack.manifest.id)
        root_id = self.pack.manifest.id
        if root_id in resolved and resolved[root_id].digest != self.digest:
            raise PackError('duplicate_identity')
        resolved[root_id] = self
        reasons, edges, pending, visited = [], {}, [root_id], set()
        bundle_ids = set()
        while pending:
            identity = pending.pop()
            if identity in visited:
                continue
            visited.add(identity)
            pack = resolved[identity].pack
            identifiers = {pack.manifest.id}
            identifiers.update(row.reference.id for row in pack.sources)
            identifiers.update(row.reference.id for row in pack.assumptions)
            for rows in (pack.definitions, pack.variables, pack.distributions, pack.dependence):
                identifiers.update(row.id for row in rows)
            if bundle_ids & identifiers:
                raise PackError('duplicate_bundle_identity')
            bundle_ids.update(identifiers)
            if pack.manifest.identities != identities:
                reasons.append('identity_mismatch:' + identity)
            if engine_version not in pack.manifest.engine_versions:
                reasons.append('engine_version:' + identity)
            edges[identity] = []
            for dependency in pack.manifest.dependencies:
                archive = resolved.get(dependency.id)
                if archive is None or archive.pack.manifest.version != dependency.version or archive.digest != dependency.digest:
                    reasons.append('dependency_unavailable:' + dependency.id)
                else:
                    edges[identity].append(dependency.id)
                    pending.append(dependency.id)
            for distribution in pack.distributions:
                sampler = next((row for row in pack.definitions if row.id == distribution.sampling_rule_ref), None)
                if (sampler is None or sampler.modeling not in ('numerical', 'procedural')
                        or sampler.evidence != 'supported' or (sampler.id, sampler.version) not in mechanisms):
                    reasons.append('sampling_unavailable:' + distribution.id)
            for relation in pack.dependence:
                if relation.kind == 'unresolved':
                    reasons.append('dependence_unresolved:' + relation.id)
            for definition in pack.definitions:
                if definition.kind == 'mechanism' and definition.modeling in ('numerical', 'procedural', 'partial'):
                    if (definition.id, definition.version) not in mechanisms:
                        reasons.append('mechanism_unavailable:' + definition.id)
                    if definition.evidence != 'supported':
                        reasons.append('mechanism_evidence:' + definition.id)
        _acyclic(edges)
        return Compatibility(not reasons, tuple(sorted(set(reasons))))
