"""Literal local allocation/time expectations; no empirical economic assertions."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.economy import EconomyRequest, EconomyEdit, EconomyCoverage
from poliscope_engine.domains.economy.exploration import interview, preview, report, baseline
from poliscope_engine.domains.economy.coverage import validate_coverage
from poliscope_engine.numeric import Registry
from test_economy import request, work_request, units, run, account, claim, activity, holder

ROOT = Path(__file__).resolve().parents[2]


def dto(data=None):
    return EconomyRequest.model_validate(data if data is not None else request())


def edit(plan, procedure='priority', order=None, scope='east'):
    card = interview(plan, units(), scope)
    return EconomyEdit(baseline_digest=card.baseline_digest, scope_id=scope,
        option_id=next(o.definition.id for o in card.alternatives if o.procedure == procedure),
        claim_order=card.claim_ids if order is None else order)


@pytest.mark.parametrize('scope', ['east', 'west'])
def test_authored_scoped_interview_has_no_default_or_implicit_rights(scope):
    data = request()
    for a in data['batch']['accounts']:
        a['scope_id'] = scope
    plan = dto(data)
    card = interview(plan, units(), scope)
    assert card.selected_option_id is None and card.scope_id == scope
    assert card.claim_ids == ['a', 'b']
    assert {o.procedure for o in card.alternatives} == {'priority', 'all_or_nothing'}
    for option in card.alternatives:
        assert option.definition.origin == 'authored'
        assert option.definition.evidence == 'hypothetical'
        assert option.definition.source_decision_id is None
        assert 'supplied order' in option.definition.original_text
    assert plan.batch.accounts[2].opening == '10'


def test_procedures_and_order_change_real_distribution_without_remote_supply():
    plan = dto()
    original = plan.model_dump_json()
    first = preview(plan, units(), edit(plan)).report
    whole = preview(plan, units(), edit(plan, 'all_or_nothing')).report
    reverse = preview(plan, units(), edit(plan, order=['b', 'a'])).report
    assert [(i.actual, i.unmet) for i in first.indicators] == [('10', '2'), ('0', '8')]
    assert [(i.actual, i.unmet) for i in whole.indicators] == [('0', '12'), ('8', '0')]
    assert [(i.actual, i.unmet) for i in reverse.indicators] == [('2', '10'), ('8', '0')]
    assert {i.scope_id for i in first.indicators} == {'east'}
    assert [a.closing for a in first.evaluation.allocation.accounts.accounts if a.account_id == 'west:food'] == ['100']
    assert plan.model_dump_json() == original
    assert first.baseline_digest != whole.baseline_digest != reverse.baseline_digest


def test_rights_and_denied_access_are_distinct_from_physical_supply():
    data = request()
    data['batch']['accounts'][2]['opening'] = '0'
    data['activities'][1]['eligibility'] = 'denied'
    result = report(dto(data), units())
    a, b = result.indicators
    assert a.available_before == b.available_before == '10'
    assert a.actual == b.actual == '0'
    assert a.eligibility == 'allowed' and b.eligibility == 'denied'
    assert a.budgets[0].holder_id == 'cohort:a'
    assert a.budgets[0].role == 'entitlement'
    assert a.budgets[0].available_before == a.budgets[0].available_after == '0'


@pytest.mark.parametrize('field', ['procedure', 'eligibility', 'terms_known'])
def test_unresolved_reports_keep_known_inputs_but_no_actual_zero_or_candidate(field):
    data = request()
    if field == 'procedure':
        data['procedure'], data['claim_order'] = None, []
    else:
        data['activities'][1][field] = 'unknown' if field == 'eligibility' else False
    result = report(dto(data), units())
    assert result.status == 'unresolved' and result.evaluation.batch is None
    assert all(i.actual is None and i.unmet is None and i.actual_before == '0'
               and i.available_before == '10' for i in result.indicators)
    assert all(b.available_after is None for i in result.indicators for b in i.budgets)
    assert result.evaluation.allocation.missing


def test_preview_can_answer_unknown_precedence_without_granting_access():
    data = request()
    data['procedure'], data['claim_order'] = None, []
    data['activities'][0]['eligibility'] = 'unknown'
    plan = dto(data)
    result = preview(plan, units(), edit(plan))
    assert result.report.status == 'unresolved' and result.report.evaluation.batch is None
    assert result.report.evaluation.allocation.missing == ['access']
    assert plan.procedure is None


def test_five_work_categories_share_time_without_wages_or_fake_service_output():
    data = work_request()
    # One local procedure; the other cohort is inspected in a separate request.
    data['batch']['claims'].pop()
    data['activities'].pop()
    data['claim_order'].pop()
    plan = dto(data)
    first = preview(plan, units(), edit(plan)).report
    whole = preview(plan, units(), edit(plan, 'all_or_nothing')).report
    assert [i.kind for i in first.indicators] == ['paid_work', 'unpaid_work', 'care', 'training', 'participation']
    assert [i.actual for i in first.indicators] == ['3', '3', '3', '1', '0']
    assert [i.actual for i in whole.indicators] == ['3', '3', '3', '0', '0']
    for i in first.indicators:
        assert i.unit_id == 'hours' and i.period_id == 'day:0'
        assert i.budgets[0].account_id == 'time:a' and i.budgets[0].role == 'time'
        assert i.budgets[0].available_before == '10' and i.budgets[0].available_after == '0'
    assert all(p.kind == 'use' for p in first.evaluation.batch.postings)


def test_multi_scope_report_keeps_each_cohort_local_and_rejects_local_reordering():
    plan = dto(work_request())
    result = report(plan, units())
    west = result.indicators[-1]
    assert (west.scope_id, west.claimant_id, west.actual, west.unmet) == ('west', 'cohort:b', '4', '2')
    assert west.budgets[0].holder_id == 'cohort:b'
    with pytest.raises(AccountError, match='incompatible_economy_scope'):
        interview(plan, units(), 'east')


@pytest.mark.parametrize('scope', ['west', 'missing'])
def test_foreign_scope_rejected(scope):
    with pytest.raises(AccountError, match='incompatible_economy_scope'):
        interview(dto(), units(), scope)


@pytest.mark.parametrize('order', [[], ['a'], ['a', 'a'], ['a', 'foreign']])
def test_malformed_orders_cannot_become_implicit_precedence(order):
    plan = dto()
    with pytest.raises((AccountError, ValidationError)):
        preview(plan, units(), edit(plan, order=order))


def test_foreign_option_rejected():
    plan = dto()
    change = edit(plan).model_copy(update={'option_id': 'society:DEC-016'})
    with pytest.raises(AccountError, match='unknown_economy_option'):
        preview(plan, units(), change)


@pytest.mark.parametrize('change', ['quantity', 'terms', 'provenance', 'order', 'holder', 'period'])
def test_complete_baseline_rejects_changed_inputs(change):
    plan = dto()
    old = edit(plan)
    if change == 'quantity': plan.batch.accounts[0] = plan.batch.accounts[0].model_copy(update={'opening': '9'})
    elif change == 'terms': plan.activities[0] = plan.activities[0].model_copy(update={'access_limit': '9'})
    elif change == 'provenance': plan.source_refs.append('authored:changed')
    elif change == 'order': plan.claim_order.reverse()
    elif change == 'holder': plan.holders[0] = plan.holders[0].model_copy(update={'holder_id': 'cohort:other'})
    else: plan = plan.model_copy(update={'period_id': 'day:1'})
    with pytest.raises(AccountError, match='stale_economy_preview'):
        preview(plan, units(), old)


@pytest.mark.parametrize('identity', ['VERSION', 'EVALUATOR_ID', 'RUNTIME_ID'])
def test_semantic_runtime_versions_are_bound(monkeypatch, identity):
    import poliscope_engine.domains.economy.exploration as module
    plan = dto()
    old = edit(plan)
    monkeypatch.setattr(module, identity, 'changed-version')
    with pytest.raises(AccountError, match='stale_economy_preview'):
        preview(plan, units(), old)


def test_unit_registry_is_bound():
    plan = dto()
    old = edit(plan)
    registry = units()
    changed = Registry(tuple(replace(u, scale=Decimal(2)) if u.id == 'kg' else u for u in registry.units))
    with pytest.raises(AccountError, match='stale_economy_preview'):
        preview(plan, changed, old)


def test_nested_mutated_contracts_revalidated_and_results_detached():
    plan = dto()
    change = edit(plan)
    change.claim_order.append('a')
    with pytest.raises(AccountError, match='invalid_claim_order'):
        preview(plan, units(), change)
    plan.activities[0] = plan.activities[0].model_copy(update={'eligibility': 'invalid'})
    with pytest.raises(ValidationError): report(plan, units())
    plan = dto()
    result = preview(plan, units(), edit(plan))
    result.report.evaluation.request.activities[0].source_refs.append('authored:changed')
    result.edit.claim_order.reverse()
    result.report.indicators[0].source_refs.clear()
    assert plan == dto()
    assert report(plan, units()).indicators[0].source_refs


def test_prior_actuals_and_holds_remain_separate_from_new_allocation():
    data = request()
    data['batch']['reservations'] = [dict(id='hold:a', account_id='east:food', claim_id='a', amount='2')]
    first = run(data)
    data['batch'] = first.batch.model_dump()
    plan = dto(data)
    result = report(plan, units())
    assert [(i.actual_before, i.actual, i.unmet) for i in result.indicators] == [('10', '0', '2'), ('0', '0', '8')]
    assert result.evaluation.batch.reservations == first.batch.reservations
    for i in result.indicators:
        assert i.posting_ids == [p.id for p in first.batch.postings if p.claim_id == i.claim_id]
    assert result.evaluation.batch.postings == first.batch.postings


def coverage():
    return json.loads((ROOT / 'content/economy/coverage-v1.json').read_text())


def source():
    return json.loads((ROOT / 'docs/roadmap/execution/society/inventory.json').read_text())


def test_complete_inventory_preserves_source_alternatives_and_unsupported_effects():
    result = validate_coverage(coverage(), source())
    assert len(result.entries) == 41
    assert len([r for r in result.entries if r.static_available]) == 6
    assert all(not r.transition_available for r in result.entries)
    decisions = [r for r in result.entries if r.classification == 'provenance']
    assert len(decisions) == 25 and all(not r.static_available for r in decisions)
    assert all(r.evidence_status == 'unreviewed' for r in decisions)
    for suffix in ['1/1','1/2','1/3','2/3','3/1','3/2','3/3','4/1','4/2','4/3']:
        row = next(r for r in result.entries if r.source_id == 'society:domain/02/' + suffix)
        assert not row.static_available and row.status == 'unsupported'


@pytest.mark.parametrize('change', ['revision', 'digest', 'missing', 'duplicate', 'foreign',
    'title', 'document', 'option', 'classification', 'availability', 'model', 'scope',
    'evidence', 'status', 'activation', 'transition', 'source_activation'])
def test_coverage_rejects_each_source_or_availability_drift(change):
    data = coverage()
    row = data['entries'][0]
    if change == 'revision': data['source_revision'] = 'wrong'
    elif change == 'digest': data['source_archive_digest'] = 'sha256:' + '0' * 64
    elif change == 'missing': data['entries'].pop()
    elif change == 'duplicate': data['entries'].append(deepcopy(row))
    elif change == 'foreign': row['source_id'] = 'society:domain/01/1'
    elif change == 'title': row['title'] = 'wrong'
    elif change == 'document': row['documents'].append('foreign.md')
    elif change == 'option': data['entries'][16]['option_refs'].append('foreign')
    elif change == 'classification': row['classification'] = 'provenance'
    elif change == 'availability': row['static_available'] = False
    elif change == 'model': row['implementation_refs'] = ['invented:model']
    elif change == 'scope': row['supported_scope_kinds'] = ['global_external']
    elif change == 'evidence': row['evidence_status'] = 'unreviewed'
    elif change == 'status': row['status'] = 'qualitative'
    elif change == 'activation': data['activation'] = 'activated'
    elif change == 'transition': row['transition_available'] = True
    else: data['entries'][16]['static_available'] = True
    with pytest.raises((AccountError, ValidationError)):
        validate_coverage(data, source())
