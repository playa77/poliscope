"""Pure institutional resolution; stable ordering never chooses precedence."""
from fractions import Fraction

from poliscope_engine.contracts.policies import (
    PolicyBinding, ResolutionRule, PolicyFinding, PolicyResult, PolicyEvaluation)
from poliscope_engine.contracts.world import UnknownValue, QuantityValue
from poliscope_engine.numeric import parse, exact, canonical


class PolicyError(ValueError):
    pass


def detached(cls, value):
    return cls.model_validate_json(value.model_dump_json())


def resolve(bindings, *, graph, mechanisms, rules=(), phase='static'):
    """Resolve a complete bounded snapshot using explicitly selected host rules.

    `rules` is a trusted application input, not a list accepted from an imported
    pack. Direct jurisdiction edges authorize an institution over an entity or
    scope. Neither containment nor jurisdiction is traversed transitively.
    All inputs are validated before exposing any result. No callbacks run.
    """
    if phase not in ('static', 'transition'):
        raise PolicyError('invalid_phase')
    bindings = tuple(detached(PolicyBinding, b) for b in bindings)
    rules = tuple(detached(ResolutionRule, r) for r in rules)
    if len(bindings) > 100 or len(rules) > 100:
        raise PolicyError('policy_limit')
    for keys in ([b.id for b in bindings], [(r.identity.id, r.identity.version) for r in rules]):
        if len(keys) != len(set(keys)):
            raise PolicyError('duplicate_identity')
    world = graph.registry
    entities = {e.id: e for e in world.entities}
    scopes = {s.id: s for s in world.scopes}
    edges = graph.relationships
    jurisdiction = {(r.from_id, r.to_id) for r in edges if r.relationship_kind == 'jurisdiction'}
    members = {scope: {r.from_id for r in edges if r.to_id == scope and
                       r.aggregation.kind != 'non_aggregating'} for scope in scopes}

    def institution(identity):
        if identity not in entities or entities[identity].entity_kind != 'institution':
            raise PolicyError('invalid_authority')

    def authorized(authority, scope, entity):
        return (authority, scope) in jurisdiction or (authority, entity) in jurisdiction

    for rule in rules:
        institution(rule.authority_id)
        if rule.scope_id not in scopes or rule.entity_id not in entities:
            raise PolicyError('missing_reference')
        if not set(rule.source_refs) <= mechanisms.source_ids:
            raise PolicyError('unresolved_source')
        if not authorized(rule.authority_id, rule.scope_id, rule.entity_id):
            raise PolicyError('unauthorized_resolution_rule')
        if not set(rule.participant_ids) <= {b.id for b in bindings}:
            raise PolicyError('missing_rule_participant')

    groups, unused = {}, []
    for binding in bindings:
        institution(binding.authority_id)
        if binding.scope_id not in scopes or not set(binding.entity_ids) <= entities.keys():
            raise PolicyError('missing_reference')
        for refs, kind in ((binding.account_refs, 'account'), (binding.choice_refs, 'decision')):
            if any(ref not in entities or entities[ref].entity_kind != kind for ref in refs):
                raise PolicyError('invalid_affected_reference')
        definition = mechanisms.definition(binding.mechanism.id, binding.mechanism.version)
        if definition.policy is None:
            raise PolicyError('missing_policy_declaration')
        if scopes[binding.scope_id].scope_kind not in definition.scope_kinds:
            raise PolicyError('unsupported_scope')
        port = next((p for p in definition.inputs if p.id == binding.parameter_id), None)
        if port is None:
            raise PolicyError('undeclared_parameter')
        mechanisms._type(port.value_type, world)
        if not isinstance(binding.value, UnknownValue):
            mechanisms.validate_value(port.value_type, binding.value, world)
        targets = set(binding.entity_ids) if binding.entity_ids else members[binding.scope_id]
        if len(targets) > 100:
            raise PolicyError('target_limit')
        if not targets:
            unused.append(binding.id)
        for target in sorted(targets):
            # Uses the same reviewed activation gate as execution, without running code.
            mechanisms.activate(binding.mechanism.id, binding.mechanism.version,
                phase=phase, world=world, scope_id=binding.scope_id, entity_id=target)
            groups.setdefault((target, binding.parameter_id), []).append((binding, definition, port.value_type))

    results = []
    for (target, parameter), rows in sorted(groups.items()):
        rows.sort(key=lambda row: row[0].id)
        participants = [b.id for b, _, _ in rows]
        authorities = sorted({b.authority_id for b, _, _ in rows})
        scope_ids = sorted({b.scope_id for b, _, _ in rows})
        sources = sorted({s for _, d, _ in rows for s in d.source_refs})
        findings = []

        def finding(kind, requirement):
            findings.append(PolicyFinding(kind=kind, entity_id=target, parameter_id=parameter,
                participant_ids=participants, authority_ids=authorities, scope_ids=scope_ids,
                account_refs=sorted({a for b, _, _ in rows for a in b.account_refs}),
                choice_refs=sorted({a for b, _, _ in rows for a in b.choice_refs}),
                source_refs=sources, requirements=[requirement]))

        if any(not authorized(b.authority_id, b.scope_id, target) for b, _, _ in rows):
            finding('authority_conflict', 'Declare direct jurisdiction for every participating authority and target or scope')
        if any(t != rows[0][2] for _, _, t in rows):
            finding('parameter_conflict', 'Provide compatible parameter types or an explicit conversion mechanism')
        candidates = [r for r in rules if r.entity_id == target and r.parameter_id == parameter
                      and set(r.participant_ids) == set(participants)
                      and r.scope_id in scope_ids]
        if len(candidates) > 1:
            finding('resolution_conflict', 'Select exactly one resolution rule for this participant set')
        rule = candidates[0] if len(candidates) == 1 else None
        semantics = {d.policy.semantics for _, d, _ in rows}
        requires_rule = len(rows) > 1 or semantics != {'exclusive'}
        if requires_rule and rule is None:
            if len(authorities) > 1:
                finding('authority_conflict', 'Choose an explicit institutional resolution for the competing authorities')
            kind = 'unresolved_allocation' if any(b.conflict_kind == 'allocation' for b, _, _ in rows) else 'parameter_conflict'
            finding(kind, 'Select a registered rule identifying authority, scope and exact participants')
        if rule is not None:
            sources = sorted(set(sources) | set(rule.source_refs))
            if any(d.policy.composition_rule is not None and d.policy.composition_rule != rule.identity
                   for _, d, _ in rows):
                finding('parameter_conflict', 'Use the composition rule declared by every participating mechanism')
            valid = (rule.operation == 'select' and semantics <= {'exclusive', 'delegated'} or
                     rule.operation == 'sum' and semantics == {'composable'} or
                     rule.operation == 'bounds' and semantics <= {'floor', 'ceiling'})
            if not valid:
                finding('parameter_conflict', 'Use a rule operation compatible with the declared policy semantics')
        value = lower = upper = None
        selected = rows
        if rule is not None and rule.operation == 'select':
            selected = [row for row in rows if row[0].id == rule.selected_id]
        if not findings:
            if any(isinstance(b.value, UnknownValue) for b, _, _ in selected):
                reasons = '; '.join(sorted({b.value.reason for b, _, _ in selected if isinstance(b.value, UnknownValue)}))
                finding('missing_parameter', 'Supply the selected policy parameter; unknown is not zero: ' + reasons)
            elif rule is None or rule.operation == 'select':
                value = selected[0][0].value
            elif any(not isinstance(b.value, QuantityValue) for b, _, _ in selected):
                finding('parameter_conflict', 'Sum and bound rules require quantity parameters')
            elif rule.operation == 'sum':
                total = sum((Fraction(parse(b.value.value)) for b, _, _ in selected), Fraction())
                value = selected[0][0].value.model_copy(update={'value': canonical(exact(total))})
            else:
                floors = [b.value for b, d, _ in selected if d.policy.semantics == 'floor']
                ceilings = [b.value for b, d, _ in selected if d.policy.semantics == 'ceiling']
                lower = max(floors, key=lambda v: parse(v.value)) if floors else None
                upper = min(ceilings, key=lambda v: parse(v.value)) if ceilings else None
                if lower is not None and upper is not None and parse(lower.value) > parse(upper.value):
                    finding('incompatible_bounds', 'Choose compatible floor and ceiling policies')
        status = 'known' if not findings else ('missing_input' if all(f.kind == 'missing_parameter' for f in findings) else 'conflict')
        results.append(PolicyResult(entity_id=target, parameter_id=parameter,
            participant_ids=participants, status=status, value_type=rows[0][2],
            value=value if status == 'known' else None,
            floor=lower if status == 'known' else None, ceiling=upper if status == 'known' else None,
            rule=rule, source_refs=sources, findings=findings))
    return PolicyEvaluation(contract_version=1, results=results, not_applicable_ids=sorted(unused))
