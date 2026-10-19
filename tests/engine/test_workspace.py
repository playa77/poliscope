"""Production workspace boundary: unanswered creation, retained reads and grants."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
from poliscope_engine.workspace import starting_inputs, dispatch, registry, catalogue, page, select
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from poliscope_engine.contracts.revisions import BranchRequest, PreviewRequest, ApplyRequest

OPTIONS = dict(name='Unanswered society', setup='blank', scope_name='Home', population=None, land_area=None)


def test_unknown_is_not_zero_and_ordinary_creation_has_no_civic_choices(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry())
        state = dispatch(service, 'create', OPTIONS, 'one')
        record = service.read(state.context)
        assert not record.inputs.goals and not record.inputs.design.policies
        assert not record.inputs.design.execution.dependencies.instances
        assert all(v.value.kind == 'unknown' for v in record.inputs.values)
        evidence = service.evidence(state.context)
        assert not evidence.evaluation.observations
        result = page(service, dict(context=state.context.model_dump(), scope_id='home', collection='values', cursor=None))
        assert len(result.result.page.items) == 2
        assert result.result.context == state.context
        assert dispatch(service, 'create', OPTIONS, 'one') == state
    with Store(tmp_path) as store:
        service = Revisions(store, registry=None)
        assert select(service, dict(civilization_id=state.context.civilization_id, branch_id='main', revision_id=None)) == state
        assert catalogue(service).branches[0].context == state.context
        assert len(catalogue(service).domains) == 12


@pytest.mark.parametrize('field,value', [('population', '-1'), ('population', '1.5'), ('population', 'NaN'),
    ('population', '1e300'), ('land_area', '-0.1'), ('land_area', 'Infinity'), ('land_area', 'text')])
def test_invalid_starting_conditions_do_not_create_world(tmp_path, field, value):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry())
        with pytest.raises(ValueError):
            dispatch(service, 'create', OPTIONS | {field: value}, 'one')
        assert catalogue(service).branches == []


def test_explicit_reference_remains_editable_and_does_not_inject_design():
    data = starting_inputs(OPTIONS | dict(setup='reference:small-settlement', population='120', land_area='2.50'), 'civilization')
    assert [v.value.value for v in data.values] == ['120', '2.50']
    assert data.goals == [] and data.design.policies == []
    # Selecting a reference never silently overrides unanswered or edited fields.
    assert all(v.value.kind == 'unknown' for v in starting_inputs(OPTIONS | dict(setup='reference:small-settlement'), 'civilization').values)


def test_scope_revision_and_branch_binding_with_retained_futures(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry())
        state = dispatch(service, 'create', OPTIONS | dict(population='10'), 'one')
        base = service.read(state.context).inputs.model_dump(mode='json')
        base['scopes'].append(dict(base['scopes'][0], id='other', label='Other'))
        population = next(v for v in base['values'] if v['id'] == 'population:value')
        base['values'].append(dict(population, id='other:population', scope_id='other', property_id='other:people', value=dict(population['value'], value='20')))
        base['owners'].append(dict(entity_id='population', property_id='other:people', partition='conditions', writer_id='player'))
        preview = PreviewRequest.model_validate(dict(revision_contract=1, context=state.context.model_dump(),
            changes=[dict(kind='replace_inputs', inputs=base)], decision=dict(alternatives=[], selected_id=None, rationale_ref=None)))
        candidate = service.preview(preview)
        result = service.apply(ApplyRequest(revision_contract=1, operation_id='edit', preview=preview, candidate_digest=candidate.candidate_digest))
        for scope, expected in [('home', '10'), ('other', '20')]:
            output = page(service, dict(context=result.context.model_dump(), scope_id=scope, collection='values', cursor=None))
            quantities = [v.value.value for v in output.result.page.items if v.value.kind == 'quantity']
            assert quantities == [expected]
        with pytest.raises(ValueError):
            page(service, dict(context=result.context.model_dump(), scope_id='foreign', collection='values', cursor=None))
        fork = service.change_branch(BranchRequest(revision_contract=1, operation_id='fork', context=result.context,
            expected_sequence=result.branch_sequence, action='fork', new_branch_id='alternative', name='Other future'))
        assert len(catalogue(service).branches) == 2
        old = select(service, dict(civilization_id=state.context.civilization_id, branch_id='alternative', revision_id=state.context.revision_id))
        assert old.context.branch_id == 'alternative'
        assert old.context.revision_id == state.context.revision_id
        assert old.branch.context.revision_id == fork.context.revision_id
        with pytest.raises(ValueError):
            select(service, dict(civilization_id='foreign', branch_id='main', revision_id=None))


def test_one_shot_process_reopens_production_store_and_bounds_errors(tmp_path):
    command = [sys.executable, '-I', '-m', 'poliscope_engine.workspace', '--directory', str(tmp_path)]
    created = subprocess.run(command + ['--operation', 'create', '--identity', 'one'], input=json.dumps(OPTIONS)+'\n', capture_output=True, text=True)
    assert created.returncode == 0, created.stderr
    context = json.loads(created.stdout)['context']
    opened = subprocess.run(command + ['--operation', 'catalogue'], input='{}\n', capture_output=True, text=True)
    assert json.loads(opened.stdout)['branches'][0]['context'] == context
    for payload in ['{}\nextra', 'x'*16385, json.dumps(OPTIONS | {'path': '/private/path'})+'\n']:
        bad = subprocess.run(command + ['--operation', 'create'], input=payload, capture_output=True, text=True)
        assert bad.returncode == 1 and bad.stdout == '' and '/private' not in bad.stderr
