"""Synthetic independent expectations; measurement evidence is not model validation."""
import json
from copy import deepcopy
from decimal import localcontext
import pytest
from poliscope_engine.contracts.measurements import (
    IndicatorDefinition, PlayerGoal, TraceQuery, EvidenceReference, AcceptedEvidence)
from poliscope_engine.contracts.evaluation import EvaluationResult
from poliscope_engine.evaluation import EvaluationCache
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.measurements import observe, MeasurementError
from poliscope_engine.explanation import (
    trace_page, retain, read_retained, unavailable, public_projection, EvidenceError, TEMPLATES)
from test_evaluation import run, design, condition_design, MODEL
from test_dependencies import plain, request, binding
from test_solvers import host, quantity, loop, plan
from test_mechanism_registry import world
from poliscope_engine.world.membership import WorldGraph

I = ['input', 'a', 'synthetic:in']
O = ['output', 'a', 'synthetic:out']


def indicator(**updates):
    return IndicatorDefinition.model_validate(dict(id='mass', version='v1', name='Synthetic mass',
        procedure='identity', inputs=[dict(node=O, scope_id='local')], unit_id='kg', scope_id='local',
        aggregation='same_scope', time_basis_id=None, denominator_scope_id=None, coverage='known',
        interpretation='Neutral synthetic measure; no direction of improvement is assumed.',
        source_refs=['synthetic:source'], assumption_refs=[], diagnostics=[]) | updates)


def goal(**updates):
    return PlayerGoal.model_validate(dict(id='target', kind='comparison', question='Is the target reached?',
        indicator_id='mass', operation='ge', threshold=quantity('5')) | updates)


def diagnostic(category='physical_shortage', **updates):
    return dict(id='named:rule', version='v1', name='Named synthetic shortfall', operation='lt',
        threshold=quantity('7'), category=category, interpretation='Below a specifically chosen threshold.',
        source_refs=['synthetic:source'], assumption_refs=[]) | updates


def test_neutral_measurement_and_independent_identity():
    physics = run()
    report = observe(physics, [indicator()])
    measured, = report.measurements
    assert measured.value.value == '6'
    assert measured.status == 'known' and measured.diagnostic == 'neutral'
    assert report.goals == [] and report.findings == [] and report.sufficient is None
    assert report.physical_output_digest == physics.identities.output_digest
    assert report.report_digest == digest(report.model_dump(mode='json', exclude={'report_digest'}))


@pytest.mark.parametrize('procedure,expected', [('sum', '8'), ('mean', '4'), ('minimum', '2'), ('maximum', '6'), ('difference', '-4')])
def test_named_procedures_with_independently_known_expectations(procedure, expected):
    d = indicator(procedure=procedure, inputs=[dict(node=I, scope_id='local'), dict(node=O, scope_id='local')])
    report = observe(run(), [d])
    assert report.measurements[0].value.value == expected


def test_comparison_goals_are_isolated_from_physics_accounts_and_measurements():
    result = run()
    original = result.model_dump_json()
    one = observe(result, [indicator()], [goal()])
    two = observe(result, [indicator()], [goal(threshold=quantity('9'))])
    assert one.goals[0].matched is True and two.goals[0].matched is False
    assert one.measurements == two.measurements and one.traces == two.traces
    assert one.physical_output_digest == two.physical_output_digest
    assert one.report_digest != two.report_digest
    assert result.model_dump_json() == original
    assert one.findings[0].category == 'player_target_observation'


def test_narrative_goals_default_empty_and_do_not_evaluate_questions():
    report = observe(run(), goals=[goal(kind='narrative', indicator_id=None, operation=None, threshold=None)])
    assert report.goals[0].status == 'narrative' and report.goals[0].matched is None
    assert report.measurements == [] and report.findings == []


@pytest.mark.parametrize('category', ['physical_shortage', 'selected_policy_breach', 'institutional_gap', 'uncertainty'])
def test_all_named_diagnostic_categories_and_authored_templates(category):
    report = observe(run(), [indicator(diagnostics=[diagnostic(category)])])
    assert report.measurements[0].diagnostic == 'flagged'
    finding, = report.findings
    assert finding.category == category and finding.rule_ref == 'named:rule'
    assert finding.template_id in TEMPLATES
    assert finding.values[0].value == '6' and finding.values[1].value == '7'
    assert finding.source_refs == ['synthetic:source']


@pytest.mark.parametrize('operation,value,expected', [('lt', '6', False), ('le', '6', True), ('eq', '6', True),
    ('ne', '6', False), ('ge', '6', True), ('gt', '6', False), ('gt', '5', True)])
def test_exact_named_threshold_boundary_no_global_margin(operation, value, expected):
    report = observe(run(), [indicator(diagnostics=[diagnostic(operation=operation, threshold=quantity(value))])])
    assert (report.measurements[0].diagnostic == 'flagged') is expected


@pytest.mark.parametrize('status', ['known', 'partial', 'missing_input', 'unmodeled', 'conflict', 'solver_failure', 'not_applicable'])
def test_seven_definition_coverage_states_are_preserved(status):
    report = observe(run(), [indicator(coverage=status, diagnostics=[diagnostic()])], [goal()])
    row = report.measurements[0]
    assert row.status == status
    if status == 'known':
        assert row.diagnostic == 'flagged'
        assert report.goals[0].matched is True
    else:
        assert row.diagnostic == 'unavailable'
        assert report.goals[0].matched is None
        assert report.sufficient is None
    if status == 'partial':
        assert row.value.value == '6'


def test_unknown_and_zero_and_independent_known_measurements():
    d = plain(('synthetic:in',))
    dep = request(('a', 'b'), d, fixed_inputs=[
        dict(consumer=dict(instance_id='a', port_id='synthetic:in'), value=dict(kind='unknown', reason='Missing')),
        dict(consumer=dict(instance_id='b', port_id='synthetic:in'), value=quantity('0'))])
    report = observe(run(design(dep), host(d, lambda p, i: i['synthetic:in'])),
        [indicator(), indicator(id='zero', inputs=[dict(node=['output', 'b', 'synthetic:out'], scope_id='local')])])
    unknown, zero = report.measurements
    assert unknown.status == 'missing_input' and unknown.value.kind == 'unknown'
    assert zero.status == 'known' and zero.value.value == '0'
    assert zero.diagnostic == 'neutral' and report.sufficient is None and report.coverage == 'missing_input'


@pytest.mark.parametrize('updates,error', [
    (dict(unit_id='rate'), 'measurement_type_mismatch'),
    (dict(scope_id='absent'), 'unknown_measurement_type'),
    (dict(inputs=[dict(node=O, scope_id='other')]), 'measurement_scope_mismatch'),
    (dict(inputs=[dict(node=['output', 'absent', 'p'], scope_id='local')]), 'unknown_measurement_node'),
    (dict(procedure='difference'), 'invalid_procedure_arity'),
    (dict(procedure='sum', inputs=[dict(node=O, scope_id='local')]*2), 'duplicate_measurement_input'),
    (dict(source_refs=['not:registered']), 'unresolved_provenance'),
    (dict(assumption_refs=['not:registered']), 'unresolved_provenance'),
    (dict(diagnostics=[diagnostic(threshold=quantity('7') | dict(unit_id='rate'))]), 'comparison_type_mismatch'),
])
def test_structural_errors_are_not_successful_observations(updates, error):
    # rate needs a time basis to reach the incompatible input-unit assertion.
    if updates.get('unit_id') == 'rate':
        updates = dict(updates, time_basis_id='day')
    with pytest.raises(MeasurementError, match=error):
        observe(run(), [indicator(**updates)])


def test_duplicate_definitions_rules_goals_and_invalid_goal_shapes():
    result = run()
    for definitions, goals in [([indicator(), indicator()], []),
        ([indicator(diagnostics=[diagnostic(), diagnostic()])], []), ([indicator()], [goal(), goal()])]:
        with pytest.raises(MeasurementError, match='duplicate_identity'):
            observe(result, definitions, goals)
    for g in [goal(indicator_id='absent'), goal(kind='narrative'), goal(operation=None), goal(threshold=None)]:
        with pytest.raises(MeasurementError):
            observe(result, [indicator()], [g])


def test_goal_type_checked_even_for_unavailable_observation():
    with pytest.raises(MeasurementError, match='comparison_type_mismatch'):
        observe(run(), [indicator(coverage='unmodeled')], [goal(threshold=quantity('1') | dict(unit_id='rate'))])


def test_exact_arithmetic_independent_of_ambient_decimal_context():
    with localcontext() as ctx:
        ctx.prec = 2
        report = observe(run(), [indicator(procedure='mean', inputs=[dict(node=I, scope_id='local'), dict(node=O, scope_id='local')])])
    assert report.measurements[0].value.value == '4'


def test_trace_dag_every_node_traversable_and_pageable_with_provenance():
    report = observe(run(), [indicator()])
    indexed = {t.id: t for t in report.traces}
    assert {tuple(m.node) for t in report.traces for m in t.members} == {tuple(o.node) for o in run().observations}
    def walk(key, path=()):
        assert key not in path
        for child in indexed[key].dependency_refs:
            walk(child, (*path, key))
    for trace in report.traces:
        walk(trace.id)
        for mechanism in trace.mechanisms:
            assert mechanism.mechanism_id == 'synthetic:supply'
            assert mechanism.mechanism_version == 'v1'
    root = report.measurements[0].trace_refs[0]
    query = TraceQuery(report_digest=report.report_digest, root_id=root, cursor=None, limit=1)
    pages = []
    while True:
        page = trace_page(report, query)
        pages.extend(page.items)
        assert len(page.items) == 1
        if page.next_cursor is None:
            break
        query = query.model_copy(update={'cursor': page.next_cursor})
    assert {t.id for t in pages} == set(indexed)
    assert any('synthetic:source' in m.source_refs for t in pages for m in t.members)


def test_feedback_condenses_to_dag_and_retains_all_internal_edges():
    d, dep = loop()
    r = host(d, lambda p, i: quantity(str(parse(i['synthetic:in'].value) / 2 + 1)))
    from poliscope_engine.numeric import parse
    des = design(dep).model_dump()
    des['execution']['solvers'] = [plan('linear')]
    report = observe(run(type(design()).model_validate(des), r), [indicator()])
    component, = [t for t in report.traces if t.kind == 'solved_component']
    assert {tuple(m.node) for m in component.members} == {tuple(I), tuple(O)}
    assert len(component.internal_edges) == 2 and component.dependency_refs == []
    assert report.measurements[0].value.value == '2'


@pytest.mark.parametrize('change', ['report', 'root', 'offset'])
def test_trace_cursors_bind_root_and_report_and_reject_invalid_offsets(change):
    report = observe(run(), [indicator()])
    query = TraceQuery(report_digest=report.report_digest, root_id=None, cursor=None, limit=1)
    page = trace_page(report, query)
    if change == 'report':
        query = query.model_copy(update={'report_digest': 'sha256:' + '0'*64})
    elif change == 'root':
        query = query.model_copy(update={'root_id': report.traces[-1].id})
    else:
        page = page.model_copy(update={'next_cursor': page.next_cursor.rsplit(':', 1)[0] + ':999'})
    with pytest.raises(EvidenceError):
        trace_page(report, query.model_copy(update={'cursor': page.next_cursor}))


def reference(**updates):
    return EvidenceReference(**(dict(id='synthetic:source', kind='source', visibility='public',
        availability='available', description='Synthetic versioned source; fixture only.',
        source=dict(id='synthetic:source', repository_id='synthetic:repository', document_id='synthetic:document',
            revision_id='v1', location='Synthetic fixture', excerpt_digest='sha256:' + '0'*64,
            license_id='synthetic:license', historical_status='current', supersedes_refs=[])) | updates))


def test_retained_evidence_survives_cache_eviction_and_data_only_read(monkeypatch):
    cache = EvaluationCache(capacity=1)
    r = host(plain(('synthetic:in',)), lambda p, i: i['synthetic:in'])
    result = cache.evaluate(WorldGraph(world()), design(), (), MODEL, registry=r)
    saved = retain(result, observe(result, [indicator()]), [reference()])
    blob = saved.model_dump_json()
    changed = design().model_dump()
    changed['effective_time']['tick'] = 1
    cache.evaluate(WorldGraph(world()), type(design()).model_validate(changed), (), MODEL, registry=r)
    cache._entries.clear()
    monkeypatch.setattr('poliscope_engine.measurements.observe', lambda *a, **k: pytest.fail('historical recomputation'))
    recovered = read_retained(blob)
    assert recovered == saved
    assert recovered.report.measurements[0].value.value == '2'
    assert recovered.evaluation.input_json == result.input_json


def test_retained_snapshots_are_detached_and_corruption_is_visible():
    result = run()
    report = observe(result, [indicator()])
    saved = retain(result, report, [reference()])
    result.observations.clear()
    report.traces.clear()
    assert saved.evaluation.observations and saved.report.traces
    data = json.loads(saved.model_dump_json())
    data['report']['measurements'][0]['value']['value'] = '99'
    with pytest.raises(EvidenceError, match='closure_identity_mismatch'):
        read_retained(json.dumps(data))


def test_retention_rejects_other_evaluation_report_and_broken_identity():
    result = run()
    other = run(r=host(plain(('synthetic:in',)), lambda p, i: quantity('8')))
    with pytest.raises(EvidenceError, match='report_evaluation_mismatch'):
        retain(other, observe(result, [indicator()]))
    with pytest.raises(MeasurementError, match='evaluation_identity_mismatch'):
        observe(result.model_copy(update={'outcome': 'insufficient'}), [indicator()])


def test_legacy_missing_evidence_is_unavailable_never_fabricated():
    saved = unavailable()
    assert read_retained(saved.model_dump_json()) == saved
    assert saved.evaluation is None and saved.report is None
    assert public_projection(saved)['state'] == 'unavailable'


def test_private_projection_omits_private_metadata_ids_hashes_and_goal_text():
    report = observe(run(), [indicator()], [goal(question='Private question do not export')])
    saved = retain(run(), report, [reference(visibility='private', description='Private excerpt do not export')])
    projected = public_projection(saved)
    text = json.dumps(projected)
    for forbidden in ['synthetic:source', 'Private excerpt', 'Private question', saved.closure_digest, report.report_digest]:
        assert forbidden not in text
    assert projected['omitted_references'] == 1
    assert projected['report']['physical_output_digest'] == report.physical_output_digest
    assert projected['projection_digest'] == digest({k: v for k, v in projected.items() if k != 'projection_digest'})
    assert 'goal_definitions' not in projected['report'] and 'goals' not in projected['report']
    assert not projected['report']['findings']


def test_missing_reference_metadata_defaults_to_private_unavailable():
    saved = retain(run(), observe(run(), [indicator()]))
    row, = saved.references
    assert row.visibility == 'private' and row.availability == 'unavailable'
    projected = public_projection(saved)
    assert projected['omitted_references'] == 1 and projected['references'] == []


def test_public_references_are_explicit_and_projection_is_separately_identified():
    saved = retain(run(), observe(run(), [indicator()]), [reference()])
    projected = public_projection(saved)
    assert projected['omitted_references'] == 0
    assert projected['references'][0]['id'] == 'synthetic:source'
    assert projected['report']['measurements'][0]['value']['value'] == '6'
    assert projected['projection_digest'] != saved.closure_digest


def test_unreferenced_or_duplicate_metadata_rejected():
    for refs in [[reference(), reference()], [reference(id='unused', source=None, availability='unavailable')]]:
        with pytest.raises(EvidenceError):
            retain(run(), observe(run(), [indicator()]), refs)


def test_operand_order_changes_semantics_and_identity_and_survives_retention():
    inputs = [dict(node=I, scope_id='local'), dict(node=O, scope_id='local')]
    first = observe(run(), [indicator(procedure='difference', inputs=inputs)])
    second = observe(run(), [indicator(procedure='difference', inputs=list(reversed(inputs)))])
    assert first.measurements[0].value.value == '-4'
    assert second.measurements[0].value.value == '4'
    assert first.report_digest != second.report_digest
    for report in (first, second):
        saved = retain(run(), report, [reference()])
        assert read_retained(saved.model_dump_json()).report == report


def finite_result(case='contention'):
    from test_solvers import contention
    req, r = contention()
    data = req.model_dump()
    for claim in data['batch']['claims']:
        claim['claimant_id'] = 'supply'
    if case == 'denied':
        for choice in data['allocations'][0]['choices']:
            choice['access'] = 'denied'
    return run(design(execution=data), r)


def test_final_account_and_distribution_numbers_have_retained_traversable_traces():
    result = finite_result()
    report = observe(result)
    traced = {tuple(m.node): m for t in report.traces for m in t.members}
    for account in result.accounts.accounts:
        for field in ('closing', 'available', 'outstanding_reserved'):
            assert traced['account_result', account.account_id, field].value.value == getattr(account, field)
    for claim in result.accounts.claims:
        for field in ('actual', 'unmet'):
            assert traced['claim_result', claim.claim_id, field].value.value == getattr(claim, field)
    shortages = [f for f in report.findings if f.category == 'physical_shortage']
    assert shortages and report.sufficient is False
    for finding in shortages:
        assert finding.trace_refs
        query = TraceQuery(report_digest=report.report_digest, root_id=finding.trace_refs[0], cursor=None, limit=100)
        assert len(trace_page(report, query).items) > 1
    saved = retain(result, report)
    assert read_retained(saved.model_dump_json()) == saved


def test_food_existing_without_access_is_an_institutional_gap_not_physical_absence():
    result = finite_result('denied')
    report = observe(result)
    assert result.accounts.accounts[0].available == '100'
    assert any(f.category == 'institutional_gap' for f in report.findings)
    assert not any(f.category == 'physical_shortage' for f in report.findings)
    assert report.sufficient is False


def test_final_account_quantity_is_measurable_in_its_own_scope():
    result = finite_result()
    account = result.accounts.accounts[0]
    report = observe(result, [indicator(inputs=[dict(node=['account_result', account.account_id, 'available'], scope_id='local')])])
    assert report.measurements[0].value.value == account.available


def test_ratio_is_dimensionless_and_zero_denominator_is_visible_failure():
    from dataclasses import replace
    from poliscope_engine.numeric import Registry, Unit, parse
    from test_mechanism_registry import registry
    d = plain(('synthetic:in',))
    r = host(d, lambda p, i: quantity('4'))
    r = registry([d], implementations=r.implementations,
        units=Registry((*r.units.units, Unit('ratio', (), 'indicator', parse('1')))))
    measure = indicator(procedure='ratio', unit_id='ratio',
        inputs=[dict(node=I, scope_id='local'), dict(node=O, scope_id='local')])
    assert observe(run(r=r), [measure]).measurements[0].value.value == '0.5'
    r = registry([d], implementations=host(d, lambda p, i: quantity('0')).implementations, units=r.units)
    row = observe(run(r=r), [measure]).measurements[0]
    assert row.status == 'solver_failure' and row.reason == 'invalid_denominator' and row.value.kind == 'unknown'


def test_nonrepresentable_measurement_is_qualified_instead_of_silently_rounded():
    d = plain(('synthetic:in',))
    dep = request(('a', 'b', 'c'), d, fixed_inputs=[dict(consumer=dict(instance_id=i, port_id='synthetic:in'), value=quantity(n))
        for i, n in [('a', '0'), ('b', '0'), ('c', '1')]])
    report = observe(run(design(dep), host(d, lambda p, i: i['synthetic:in'])), [indicator(procedure='mean',
        inputs=[dict(node=['output', i, 'synthetic:out'], scope_id='local') for i in 'abc'])])
    row, = report.measurements
    assert row.status == 'solver_failure' and row.reason == 'precision_unsupported'
    assert row.value.kind == 'unknown'


def test_post_evaluation_services_are_pure_with_external_effect_tripwires(monkeypatch):
    import builtins
    import socket
    import sqlite3
    import random
    import time
    result = run()
    def forbidden(*args, **kwargs):
        pytest.fail('External effect in post-evaluation service')
    for module, name in [(builtins, 'open'), (socket, 'socket'), (sqlite3, 'connect'), (random, 'random'), (time, 'time')]:
        monkeypatch.setattr(module, name, forbidden)
    report = observe(result, [indicator()], [goal()])
    saved = retain(result, report)
    assert read_retained(saved.model_dump_json()) == saved
    public_projection(saved)


def test_all_posted_amounts_have_trace_links_into_final_account_closure():
    result = finite_result()
    report = observe(result)
    traced = {tuple(m.node): m for t in report.traces for m in t.members}
    for posting in json.loads(result.final_batch_json)['postings']:
        assert traced['posting_result', posting['id'], 'amount'].value.value == posting['amount']
    saved = retain(result, report)
    assert read_retained(saved.model_dump_json()) == saved


def test_explicit_assumption_value_binding_is_part_of_traversable_provenance():
    from poliscope_engine.contracts.evaluation import AssumptionValue
    from poliscope_engine.contracts.world import QuantityValue
    d = plain(('synthetic:in',))
    des = design(request(('a',), d), assumption_inputs=[dict(consumer=dict(instance_id='a', port_id='synthetic:in'), value_id='player:assumption')])
    result = run(des, host(d, lambda p, i: i['synthetic:in']),
        assumptions=[AssumptionValue(id='player:assumption', value=QuantityValue(**quantity('3')))])
    report = observe(result, [indicator()])
    assert any('player:assumption' in m.assumption_refs for t in report.traces for m in t.members)
    saved = retain(result, report)
    assert any(r.id == 'player:assumption' and r.kind == 'assumption' and r.availability == 'unavailable' for r in saved.references)
    assert read_retained(saved.model_dump_json()) == saved


def test_public_projection_cannot_leak_private_finding_identity():
    report = observe(run(), [indicator(diagnostics=[diagnostic()])])
    saved = retain(run(), report, [reference(visibility='private', description='Secret evidence')])
    projected = public_projection(saved)
    assert report.findings[0].id not in json.dumps(projected)
    assert projected['report']['findings'][0]['source_refs'] == []


def test_retained_source_revision_and_transitive_classified_references_are_complete():
    public = reference()
    source = public.source.model_copy(update={'supersedes_refs': ['private:older-source']})
    public = public.model_copy(update={'source': source})
    saved = retain(run(), observe(run(), [indicator()]), [public])
    assert len(saved.references) == 2
    assert next(r for r in saved.references if r.id == 'synthetic:source').source.revision_id == 'v1'
    assert read_retained(saved.model_dump_json()) == saved
    projected = public_projection(saved)
    assert 'private:older-source' not in json.dumps(projected)
    assert projected['references'][0]['source']['supersedes_refs'] == []
    assert projected['omitted_references'] == 1


def test_available_evidence_requires_matching_typed_descriptor():
    from pydantic import ValidationError
    for update in [dict(source=None), dict(id='different'), dict(kind='assumption')]:
        with pytest.raises(ValidationError):
            reference(**update)


def test_trace_response_is_byte_bounded_and_oversize_vertex_fails_visibly():
    from poliscope_engine.contracts.world import LabelValue
    report = observe(run(), [indicator()])
    trace = report.traces[0]
    large_members = [trace.members[0].model_copy(update={
        'node': ['output', 'synthetic:large:' + str(i), 'port'],
        'value': LabelValue(kind='label', value='x'*4096)}) for i in range(250)]
    large = trace.model_copy(update={'members': large_members})
    report = report.model_copy(update={'traces': [large]})
    report = report.model_copy(update={'report_digest': digest(report.model_dump(mode='json', exclude={'report_digest'}))})
    query = TraceQuery(report_digest=report.report_digest, root_id=None, cursor=None, limit=100)
    with pytest.raises(EvidenceError, match='trace_node_requires_chunking'):
        trace_page(report, query)


def test_coupled_funding_does_not_invent_the_cause_of_unmet_physical_claims():
    from test_solvers import contention
    from test_allocations import account
    from poliscope_engine.contracts.world import EntityDTO
    from poliscope_engine.world import WorldRegistry
    from test_mechanism_registry import PROVENANCE
    req, r = contention()
    data = req.model_dump()
    for claim in data['batch']['claims']:
        claim['claimant_id'] = 'supply'
    data['batch']['accounts'].append(account('funding', '30', scope_id='local', invariant='budget'))
    for choice in data['allocations'][0]['choices']:
        choice['requirements'] = [dict(account_id='funding', per_unit='2', kind='funding')]
    base = world()
    w = WorldGraph(WorldRegistry('civ', entities=[*base.entities,
        EntityDTO(id='funding', entity_kind='account', label='Synthetic funding', provenance=PROVENANCE)], scopes=base.scopes))
    result = run(design(execution=data), r, w)
    report = observe(result)
    assert any(f.category == 'uncertainty' and f.template_id == 'constrained_claim:v1' for f in report.findings)
    assert not any(f.category == 'physical_shortage' for f in report.findings)
    assert report.sufficient is False
