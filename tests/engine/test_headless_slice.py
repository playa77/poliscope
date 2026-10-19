"""WP-019 independent SV slice. Public services only; no renderer/provider."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import platform
import time

import pytest
from poliscope_engine.contracts.revisions import RevisionInputs, ApplyRequest, HistoryQuery
from poliscope_engine.contracts.world import WorldInspectParams
from poliscope_engine.contracts.measurements import TraceQuery
from poliscope_engine.explanation import trace_page
from poliscope_engine.revisions import Revisions, RevisionError
from poliscope_engine.storage import Store, StorageError
from poliscope_engine.world import WorldRegistry, StateOwner
from poliscope_engine.world.membership import WorldGraph
from poliscope_engine.numeric import NumericError
from headless_fixture import inputs, registry, create, preview, apply, move, physical, EXPECTED, quantity


def changed(data, edit):
    raw = data.model_dump(mode='json')
    edit(raw)
    return RevisionInputs.model_validate(raw)


def query(service, context, collection):
    return service.inspect(WorldInspectParams(world_schema=1, context=context, collection=collection, cursor=None, limit=100))


def union(data):
    world = WorldRegistry('civ', entities=data.entities, scopes=data.scopes, values=data.values,
        owners=[StateOwner(**o.model_dump()) for o in data.owners])
    return WorldGraph(world, data.relationships).aggregate(['east', 'watershed', 'region'],
        property_id='water-stock', partition='conditions').value


def assert_oracle(evidence):
    assert physical(evidence) == EXPECTED
    assert json.loads(evidence.evaluation.model_json)['evaluator'] == 'pure-static-v2'
    # Independent exact conservation in integer hundredths, including both losses.
    p = physical(evidence)
    assert int(Decimal(p['accounts']['product'][0]) * 100) + int(Decimal(p['accounts']['residual'][0]) * 100) + 1000 == 10000
    assert sum(Decimal(v[0]) for v in p['claims'].values()) == 100


def goal_data(data):
    return changed(data, lambda d: d['goals'].append(dict(id='optional', kind='comparison',
        question='Does east receive at least 70 kg?', indicator_id='east-output', operation='ge', threshold=quantity(70))))


def test_complete_headless_workflow_and_retained_futures(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry())
        root = create(service)
        original = service.read(root.context).inputs
        assert original.goals == [] and original.design.policies == []
        assert_oracle(service.evidence(root.context))
        assert {s.id for s in query(service, root.context, 'scopes').page.items} == {'east', 'west', 'watershed', 'region'}
        assert query(service, root.context, 'values').page.items[0].value.value == '100'
        assert union(original) == '100'
        goal = goal_data(original)
        qualitative = changed(goal, lambda d: d['design']['execution']['dependencies']['instances'].append(
            dict(id='qualitative', mechanism_id='synthetic:qualitative', mechanism_version='v1', entity_id='water', scope_id='west')))
        alternatives = [dict(id='quantitative', changes=preview(root.context, goal).model_dump(mode='json')['changes']),
                        dict(id='qualitative', changes=preview(root.context, qualitative).model_dump(mode='json')['changes'])]
        request = preview(root.context, goal, alternatives)
        request = request.model_copy(update={'decision': request.decision.model_copy(update={'selected_id': 'quantitative'})})
        # Cancel means discard: repeatable preview cannot advance head or history.
        history_before = service.history(HistoryQuery(context=root.context, cursor=None, limit=100))
        candidate = service.preview(request)
        assert service.preview(request) == candidate
        assert service.history(HistoryQuery(context=root.context, cursor=None, limit=100)) == history_before
        assert service.branch(root.context).context == root.context
        committed_request = apply(service, request)
        accepted = service.apply(committed_request)
        assert_oracle(service.evidence(accepted.context))
        assert service.evidence(accepted.context).evaluation == service.evidence(root.context).evaluation
        report = service.evidence(accepted.context).report
        assert report.goals[0].matched is False
        revised_goal = changed(goal, lambda d: d['goals'][0].update(threshold=quantity(50)))
        observed_goal = service.preview(preview(accepted.context, revised_goal)).report
        assert observed_goal.goals[0].matched is True
        assert observed_goal.physical_output_digest == report.physical_output_digest
        assert observed_goal.measurements == report.measurements
        assert report.measurements[0].value.value == '60'
        # Follow the complete paged trace, proving edges resolve to retained nodes.
        traces, cursor = [], None
        while True:
            page = trace_page(report, TraceQuery(report_digest=report.report_digest, root_id=None, cursor=cursor, limit=2))
            traces.extend(page.items)
            cursor = page.next_cursor
            if cursor is None:
                break
        ids = {t.id for t in traces}
        assert ids and all(set(t.dependency_refs) <= ids for t in traces)
        assert any(any(n.node[0] == 'actual_consumption' for n in t.members) for t in traces)
        assert service.read(root.context).inputs.goals == []
        fork = move(service, accepted, 'fork', new_branch_id='comparison', name='Synthetic alternative')
        denied = changed(goal, lambda d: d['design']['execution']['allocations'][0]['choices'][0].update(access='denied'))
        forked = service.apply(apply(service, preview(fork.context, denied), 'deny-access'))
        result = physical(service.evidence(forked.context))
        assert result['outputs'] == {'a': '0', 'b': '80'}
        assert {k: v[0] for k, v in result['accounts'].items()} == {'stock': '20', 'labor': '4', 'product': '56', 'residual': '16'}
        # Compare retained inputs/outputs without introducing a ranking service.
        assert service.read(forked.context).inputs != service.read(accepted.context).inputs
        assert physical(service.evidence(accepted.context))['outputs']['a'] == '60'
        undo = move(service, accepted, 'undo')
        assert undo.context.revision_id == root.context.revision_id
        replacement = service.apply(apply(service, preview(undo.context, denied), 'alternate-future'))
        assert service.read(accepted.context).inputs == goal
        assert service.read(accepted.context).decision == request.decision
        assert [a.id for a in service.read(accepted.context).decision.alternatives] == ['quantitative', 'qualitative']
        assert service.status('apply', committed_request) == accepted
        assert service.apply(committed_request) == accepted  # replay after head advancement
        history = service.history(HistoryQuery(context=replacement.context, cursor=None, limit=100))
        assert len(history.items) == 4
        retained = {o.context.revision_id: service.evidence(o.context) for o in (root, accepted, forked, replacement)}
        with store.transaction():
            store.clear_caches()
    with Store(tmp_path) as store:
        service = Revisions(store, registry=None)
        opened = service.open(data_store_id=service.data_store_id, civilization_id='civ', branch_id='main')
        assert opened.context == replacement.context
        for outcome in (root, accepted, forked, replacement):
            assert service.evidence(outcome.context) == retained[outcome.context.revision_id]
            assert service.read(outcome.context).inputs is not None
        assert service.status('apply', committed_request) == accepted
        assert service.apply(committed_request) == accepted


def test_stale_tampered_conflicting_and_lost_reply(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry())
        root = create(service)
        first = apply(service, preview(root.context, goal_data(inputs())))
        stale = first.model_copy(update={'operation_id': 'stale'})
        result = service.apply(first)  # simulate losing the reply by reopening below
        with pytest.raises(RevisionError, match='stale'):
            service.apply(stale)
        tampered = apply(service, preview(result.context, inputs()), 'tampered')
        tampered = tampered.model_copy(update={'candidate_digest': 'sha256:' + '0' * 64})
        with pytest.raises(RevisionError):
            service.apply(tampered)
        conflict = first.model_dump(mode='json')
        conflict['preview']['changes'][0]['inputs']['goals'] = []
        with pytest.raises(StorageError, match='different request'):
            service.apply(ApplyRequest.model_validate(conflict))
        conflict['preview']['context']['civilization_id'] = 'unauthorized'
        with pytest.raises(RevisionError, match='unknown_civilization'):
            service.status('apply', ApplyRequest.model_validate(conflict))
        cross_store = first.model_dump(mode='json')
        cross_store['preview']['context']['data_store_id'] = 'other-store'
        with pytest.raises(RevisionError, match='wrong_data_store'):
            service.status('apply', ApplyRequest.model_validate(cross_store))
        assert service.branch(result.context).context == result.context
        assert len(service.history(HistoryQuery(context=result.context, cursor=None, limit=100)).items) == 2
    with Store(tmp_path) as store:
        recovered = Revisions(store, registry=None)
        assert recovered.status('apply', first) == result
        assert recovered.apply(first) == result


@pytest.mark.parametrize('case', ['missing', 'qualitative', 'access-unknown', 'labor', 'quantum-remainder', 'precision', 'precision-boundary'])
def test_visible_gaps_and_precision_rejection(tmp_path, case):
    data = inputs().model_dump(mode='json')
    execution = data['design']['execution']
    if case == 'missing':
        execution['dependencies']['fixed_inputs'][0]['value'] = dict(kind='unknown', reason='Synthetic unmeasured demand')
    elif case == 'qualitative':
        execution['dependencies']['instances'].append(dict(id='qualitative', mechanism_id='synthetic:qualitative',
            mechanism_version='v1', entity_id='water', scope_id='west'))
    elif case == 'access-unknown':
        execution['allocations'][0]['choices'][0]['access'] = 'unknown'
    elif case in ('labor', 'quantum-remainder'):
        execution['batch']['accounts'][3]['opening'] = '5' if case == 'labor' else '5.01'
    else:
        execution['batch']['postings'][0]['amount'] = ('0.001' if case == 'precision' else '10000000000000000000000000001')
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry())
        if case in ('precision', 'precision-boundary'):
            with pytest.raises(NumericError):
                create(service, RevisionInputs.model_validate(data))
            # Rejection is atomic: a valid create reuses the exact operation key.
            assert_oracle(service.evidence(create(service).context))
            return
        root = create(service, RevisionInputs.model_validate(data))
        result = service.evidence(root.context).evaluation
        if case in ('labor', 'quantum-remainder'):
            p = physical(service.evidence(root.context))
            assert sum(Decimal(c[0]) for c in p['claims'].values()) == (Decimal('50') if case == 'labor' else Decimal('50.1'))
            assert p['accounts']['labor'][0] == '0'
            assert p['accounts']['stock'][0] == ('50' if case == 'labor' else '49.9')
            if case == 'quantum-remainder':
                assert p['accounts']['product'][0] == '35.07'
                assert p['accounts']['residual'][0] == '10.02'
        else:
            assert result.outcome in ('incomplete', 'unresolved')
            if case == 'qualitative':
                assert any(o.status == 'unmodeled' and o.value is None for o in result.observations)
            else:
                assert result.accounts is None


def test_overlap_and_policy_conflicts_are_order_invariant(tmp_path):
    data = inputs().model_dump(mode='json')
    data['design']['policies'] = [dict(contract_version=1, id=i, mechanism=dict(id='synthetic:access-policy', version='v1'),
        scope_id=s, authority_id=a, entity_ids=['water'], parameter_id='synthetic:limit', value=quantity(v),
        conflict_kind='allocation', account_refs=['stock'], choice_refs=[]) for i, s, a, v in
        [('east-limit', 'east', 'east-authority', 40), ('region-limit', 'region', 'region-authority', 60)]]
    observed = []
    for order in (False, True):
        variant = deepcopy(data)
        if order:
            for field in ('entities', 'scopes', 'relationships', 'values'):
                variant[field].reverse()
            variant['design']['policies'].reverse()
        with Store(tmp_path / str(order)) as store:
            service = Revisions(store, registry=registry())
            root = create(service, RevisionInputs.model_validate(variant))
            result = service.evidence(root.context).evaluation
            assert union(service.read(root.context).inputs) == '100'
            assert result.policies.results[0].status == 'conflict'
            assert result.policies.results[0].value is None
            observed.append(result)
    assert observed[0] == observed[1]


def test_repeatable_digests_and_preliminary_measurements(tmp_path):
    """Current-run diagnostics only, no reference-desktop performance acceptance."""
    results, durations = [], []
    for run in range(30):
        with Store(tmp_path / str(run)) as store:
            service = Revisions(store, registry=registry())
            start = time.perf_counter_ns()
            root = create(service)
            timings = {'create_ns': time.perf_counter_ns() - start}
            request = preview(root.context, goal_data(inputs()))
            start = time.perf_counter_ns()
            candidate = service.preview(request)
            timings['preview_ns'] = time.perf_counter_ns() - start
            start = time.perf_counter_ns()
            accepted = service.apply(ApplyRequest(revision_contract=1, preview=request,
                candidate_digest=candidate.candidate_digest, operation_id='apply'))
            timings['apply_ns'] = time.perf_counter_ns() - start
            assert_oracle(service.evidence(accepted.context))
            results.append(service.evidence(accepted.context).evaluation.identities.model_dump())
            durations.append(timings)
    assert results[0] == results[1] == results[2]
    artifact = os.environ.get('POLISCOPE_HEADLESS_EVIDENCE')
    if artifact:
        payload = dict(kind='preliminary-cloud-diagnostics', runs=30, platform=platform.platform(),
            python=platform.python_version(), timings=durations, result_identities=results[0],
            fixture_sha256=hashlib.sha256(Path('tests/engine/headless_fixture.py').read_bytes()).hexdigest())
        Path(artifact).write_text(json.dumps(payload, indent=2) + '\n')


@pytest.mark.parametrize('edit', ['scope', 'physical-budget', 'dated-source', 'stock-budget'])
def test_period_allowance_does_not_erase_other_requirement_guards(tmp_path, edit):
    data = inputs().model_dump(mode='json')
    labor = data['design']['execution']['batch']['accounts'][3]
    if edit == 'scope':
        labor['scope_id'] = 'west'
    elif edit == 'physical-budget':
        labor['invariant'] = 'physical'
    elif edit == 'dated-source':
        # A dated resource's declared period still cannot be changed by funding.
        from poliscope_engine.allocations import allocate
        from poliscope_engine.contracts.allocations import AllocationRequest
        from poliscope_engine.accounts import AccountError
        batch = data['design']['execution']['batch']
        batch['accounts'][0]['period_id'] = 'other-day'
        plan = data['design']['execution']['allocations'][0]
        with pytest.raises(AccountError, match='incompatible_requirement'):
            allocate(AllocationRequest.model_validate(dict(contract_version=1, batch=batch,
                procedure=plan['procedure'], claim_order=plan['claim_order'], choices=plan['choices'],
                mechanism_ref=plan['mechanism_ref'], source_refs=[])), registry().units)
        return
    else:
        labor.update(kind='stock', unit_id='kg', period_id='day:0')
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry())
        root = create(service, RevisionInputs.model_validate(data))
        result = service.evidence(root.context).evaluation
        assert result.accounts is None
        assert any(o.reason == 'incompatible_requirement' for o in result.observations)
