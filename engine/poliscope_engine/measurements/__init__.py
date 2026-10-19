"""Pure post-evaluation observations. No callbacks, I/O, ranking or world mutation."""
import json
from fractions import Fraction
from poliscope_engine.contracts.evaluation import EvaluationResult
from poliscope_engine.contracts.measurements import (
    IndicatorDefinition, PlayerGoal, MeasurementReport, MeasurementObservation,
    ObservationFinding, GoalObservation)
from poliscope_engine.contracts.world import QuantityValue, UnknownValue
from poliscope_engine.evaluation.identity import digest, serialized
from poliscope_engine.numeric import parse, exact, canonical, NumericError

COMPARISONS = dict(lt=lambda a, b: a < b, le=lambda a, b: a <= b,
                   eq=lambda a, b: a == b, ne=lambda a, b: a != b,
                   ge=lambda a, b: a >= b, gt=lambda a, b: a > b)
STATUS_ORDER = ('solver_failure', 'conflict', 'missing_input', 'unmodeled', 'partial', 'not_applicable', 'known')


class MeasurementError(ValueError):
    pass


def coverage(statuses):
    states = set(statuses)
    return next((s for s in STATUS_ORDER if s in states), 'known')


def verify_evaluation(result):
    result = EvaluationResult.model_validate_json(result.model_dump_json())
    if (digest(result.model_dump(mode='json', exclude={'identities'})) != result.identities.output_digest
            or digest(json.loads(result.input_json)) != result.identities.input_digest
            or digest(json.loads(result.model_json)) != result.identities.model_digest
            or digest(json.loads(result.realization_json)) != result.identities.realization_digest
            or digest(result.identities.model_dump(exclude={'cache_key', 'output_digest'})) != result.identities.cache_key):
        raise MeasurementError('evaluation_identity_mismatch')
    return result


def _unique(rows, key=lambda r: r.id):
    indexed = {key(r): r for r in rows}
    if len(indexed) != len(rows):
        raise MeasurementError('duplicate_identity')
    return indexed


def _metadata(value):
    return value.unit_id, value.time_basis_id, value.denominator_scope_id


def _compare(value, operation, threshold):
    parse(threshold.value)
    if _metadata(value) != _metadata(threshold):
        raise MeasurementError('comparison_type_mismatch')
    return COMPARISONS[operation](parse(value.value), parse(threshold.value))


def observe(evaluation, definitions=(), goals=()):
    """Host-authored bounded same-scope procedures; targets never re-evaluate physics.

    Explicit input order matters for difference/ratio; no implicit spatial or
    population aggregation, unit conversion or uncertainty propagation is assumed.
    """
    from poliscope_engine.explanation import build_traces
    result = verify_evaluation(evaluation)
    definitions = sorted([IndicatorDefinition.model_validate_json(d.model_dump_json()) for d in definitions], key=lambda d: d.id)
    goals = sorted([PlayerGoal.model_validate_json(g.model_dump_json()) for g in goals], key=lambda g: g.id)
    if len(definitions) > 1000 or len(goals) > 1000:
        raise MeasurementError('observation_limit')
    _unique(definitions)
    _unique(goals)
    nodes = _unique(result.observations, lambda n: tuple(n.node))
    traces, node_trace = build_traces(result)
    # Final reconciled accounts/distributions are explicit observable nodes too.
    for trace in traces:
        for member in trace.members:
            nodes.setdefault(tuple(member.node), member)
    model = json.loads(result.model_json)
    units = {u['id']: u for u in model['units']}
    times = {t['id'] for t in model['times']}
    scopes = {s['id'] for s in json.loads(result.input_json)['world']['scopes']}
    sources, assumptions = set(model['source_ids']), set(model['assumption_ids'])
    observations, findings = [], []

    def refs(row):
        if not set(row.source_refs) <= sources or not set(row.assumption_refs) <= assumptions:
            raise MeasurementError('unresolved_provenance')
        if len(set(row.source_refs)) != len(row.source_refs) or len(set(row.assumption_refs)) != len(row.assumption_refs):
            raise MeasurementError('duplicate_reference')

    def finding(category, scope, status, template, rule=None, indicator=None, trace=(), src=(), asm=(), values=()):
        payload = dict(category=category, scope_id=scope, effective_time=result.effective_time,
            status=status, template_id=template, rule_ref=rule, indicator_id=indicator,
            trace_refs=sorted(set(trace)), source_refs=sorted(set(src)), assumption_refs=sorted(set(asm)), values=list(values))
        if len(findings) >= 10000:
            raise MeasurementError('finding_limit')
        findings.append(ObservationFinding(id=digest(payload), **payload))

    for definition in definitions:
        refs(definition)
        _unique(definition.diagnostics)
        if (definition.scope_id not in scopes or definition.unit_id not in units
                or definition.time_basis_id is not None and definition.time_basis_id not in times
                or definition.denominator_scope_id is not None and definition.denominator_scope_id not in scopes):
            raise MeasurementError('unknown_measurement_type')
        unit = units[definition.unit_id]
        if (unit['kind'] in ('flow', 'capacity') and definition.time_basis_id is None
                or unit['kind'] not in ('flow', 'capacity', 'indicator') and definition.time_basis_id is not None):
            raise MeasurementError('invalid_time_basis')
        arity = len(definition.inputs)
        if (definition.procedure == 'identity' and arity != 1
                or definition.procedure in ('difference', 'ratio') and arity != 2):
            raise MeasurementError('invalid_procedure_arity')
        if len({tuple(i.node) for i in definition.inputs}) != arity:
            raise MeasurementError('duplicate_measurement_input')
        rows = []
        for binding in definition.inputs:
            row = nodes.get(tuple(binding.node))
            if row is None:
                raise MeasurementError('unknown_measurement_node')
            if binding.scope_id != definition.scope_id or row.scope_id != binding.scope_id:
                raise MeasurementError('measurement_scope_mismatch')
            rows.append(row)
        trace = sorted({node_trace[tuple(r.node)] for r in rows})
        status = coverage([definition.coverage, *(r.status for r in rows)])
        value = UnknownValue(kind='unknown', reason=status)
        reason = status
        quantities = [r.value for r in rows if r.value is not None and r.value.kind == 'quantity']
        expected = definition.unit_id, definition.time_basis_id, definition.denominator_scope_id
        for q in quantities:
            parse(q.value)
        if definition.procedure == 'ratio':
            if len(quantities) == 2 and _metadata(quantities[0]) != _metadata(quantities[1]):
                raise MeasurementError('ratio_input_type_mismatch')
            if unit['dimension'] or unit['kind'] != 'indicator' or parse(unit['scale']) != 1 or definition.time_basis_id is not None or definition.denominator_scope_id is not None:
                raise MeasurementError('ratio_output_type_mismatch')
        elif any(_metadata(q) != expected for q in quantities):
            raise MeasurementError('measurement_type_mismatch')
        for rule in definition.diagnostics:
            refs(rule)
            parse(rule.threshold.value)
            if _metadata(rule.threshold) != expected:
                raise MeasurementError('comparison_type_mismatch')
        if status in ('known', 'partial'):
            if len(quantities) != arity:
                status, reason = 'missing_input', 'quantity_required'
            else:
                numbers = [Fraction(parse(q.value)) for q in quantities]
                try:
                    procedure = definition.procedure
                    if procedure == 'identity':
                        number = numbers[0]
                    elif procedure == 'sum':
                        number = sum(numbers, Fraction())
                    elif procedure == 'mean':
                        number = sum(numbers, Fraction()) / arity
                    elif procedure == 'minimum':
                        number = min(numbers)
                    elif procedure == 'maximum':
                        number = max(numbers)
                    elif procedure == 'difference':
                        number = numbers[0] - numbers[1]
                    else:
                        if not numbers[1]:
                            raise NumericError('invalid_denominator')
                        number = numbers[0] / numbers[1]
                    value = QuantityValue(kind='quantity', value=canonical(exact(number)), unit_id=definition.unit_id,
                        time_basis_id=definition.time_basis_id, denominator_scope_id=definition.denominator_scope_id)
                except NumericError as exc:
                    status, reason = 'solver_failure', str(exc)
        if value.kind == 'unknown':
            value = UnknownValue(kind='unknown', reason=reason)
        diagnostic = 'neutral' if status == 'known' else 'unavailable'
        if status == 'known' and definition.diagnostics:
            diagnostic = 'within_named_thresholds'
            for rule in definition.diagnostics:
                if _compare(value, rule.operation, rule.threshold):
                    diagnostic = 'flagged'
                    finding(rule.category, definition.scope_id, status, 'named_diagnostic:v1', rule.id,
                        definition.id, trace, set(definition.source_refs) | set(rule.source_refs),
                        set(definition.assumption_refs) | set(rule.assumption_refs), [value, rule.threshold])
        if status != 'known':
            finding('uncertainty', definition.scope_id, status, 'coverage_gap:v1', indicator=definition.id,
                trace=trace, src=definition.source_refs, asm=definition.assumption_refs)
        observations.append(MeasurementObservation(indicator_id=definition.id, definition_version=definition.version,
            scope_id=definition.scope_id, effective_time=result.effective_time, status=status, reason=reason, value=value,
            diagnostic=diagnostic, trace_refs=trace, source_refs=definition.source_refs, assumption_refs=definition.assumption_refs))

    measured = {o.indicator_id: o for o in observations}
    goal_rows = []
    for goal in goals:
        if goal.kind == 'narrative':
            if any(v is not None for v in (goal.indicator_id, goal.operation, goal.threshold)):
                raise MeasurementError('invalid_narrative_goal')
            goal_rows.append(GoalObservation(goal_id=goal.id, status='narrative', matched=None,
                indicator_id=None, reason='player_question_only'))
            continue
        if goal.indicator_id not in measured or goal.operation is None or goal.threshold is None:
            raise MeasurementError('invalid_comparison_goal')
        observation = measured[goal.indicator_id]
        # Validate targets even when the current value is unavailable.
        definition = next(d for d in definitions if d.id == goal.indicator_id)
        if _metadata(goal.threshold) != (definition.unit_id, definition.time_basis_id, definition.denominator_scope_id):
            raise MeasurementError('comparison_type_mismatch')
        parse(goal.threshold.value)
        matched = _compare(observation.value, goal.operation, goal.threshold) if observation.status == 'known' else None
        goal_rows.append(GoalObservation(goal_id=goal.id, status='unavailable' if matched is None else 'observed',
            matched=matched, indicator_id=goal.indicator_id, reason='post_evaluation_comparison'))
        finding('player_target_observation', observation.scope_id, observation.status, 'player_target:v1', goal.id,
            observation.indicator_id, observation.trace_refs, values=[observation.value, goal.threshold])

    # Production insufficiency is evidence even without any selected indicator.
    if result.accounts is not None:
        batch = json.loads(result.final_batch_json)
        claims = {c['id']: c for c in batch['claims']}
        accounts = {a['id']: a for a in batch['accounts']}
        available = {a.account_id: parse(a.available) for a in result.accounts.accounts}
        choices = {c['claim_id']: c for p in json.loads(result.input_json)['design']['execution']['allocations'] for c in p['choices']}
        for claim in result.accounts.claims:
            if parse(claim.unmet) > 0:
                demand = claims[claim.claim_id]
                account = accounts[demand['account_id']]
                # Access/funding limits are not evidence that physical supply
                # itself is absent. Keep the selected constraint trace visible.
                choice = choices.get(claim.claim_id)
                access_gap = choice is not None and (choice['access'] != 'allowed' or
                    parse(choice['access_limit']) < parse(demand['requested']))
                coupled = choice is not None and bool(choice['requirements'])
                physical = (account['invariant'] == 'physical' and not access_gap and not coupled
                    and available[account['id']] < parse(claim.unmet))
                category = ('physical_shortage' if physical else
                    'institutional_gap' if access_gap or account['invariant'] != 'physical' else 'uncertainty')
                template = 'unmet_claim:v1' if physical else 'constrained_claim:v1'
                finding(category, account['scope_id'], 'known', template, claim.claim_id,
                    trace=[node_trace[('claim_result', claim.claim_id, 'unmet')]], src=demand['source_refs'], values=[QuantityValue(kind='quantity', value=claim.unmet,
                    unit_id=account['unit_id'], time_basis_id=account['period_id'], denominator_scope_id=None)])
    for policy in result.policies.results:
        if policy.status != 'known':
            finding('institutional_gap', None, policy.status, 'policy_gap:v1', policy.parameter_id, src=policy.source_refs)
    status = coverage([*(o.status for o in result.observations), *(r.status for r in result.policies.results),
                       *(o.status for o in observations)])
    sufficient = None
    # There is no claim that the simulated domain set covers an entire society.
    # True is intentionally never inferred from finite successful computations.
    if result.outcome == 'insufficient' or any(f.category in ('physical_shortage', 'selected_policy_breach') for f in findings):
        sufficient = False
    payload = dict(measurement_schema=1, physical_output_digest=result.identities.output_digest,
        definitions=definitions, goal_definitions=goals, measurements=observations, goals=goal_rows,
        findings=sorted(findings, key=lambda f: f.id), traces=traces, coverage=status, sufficient=sufficient)
    return MeasurementReport.model_validate_json(serialized(dict(payload, report_digest=digest(payload))))
