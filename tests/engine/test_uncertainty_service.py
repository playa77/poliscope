"""Real revision/SQLite integration; literal resource and sensitivity oracles."""
from copy import deepcopy
from fractions import Fraction
import json
import pytest
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from poliscope_engine.contracts.revisions import CreateRequest, RevisionInputs
from poliscope_engine.uncertainty_service import analyze, sensitivity, capacity
from poliscope_engine.uncertainty import UncertaintyError
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.workspace import dispatch
from test_revisions import inputs, mechanism_registry, count
from test_uncertainty import model, parameter, expression


def replace_record(service, context, raw):
    from poliscope_engine.contracts.revisions import PreviewRequest, ApplyRequest
    request=PreviewRequest.model_validate(dict(revision_contract=1,context=context,
        changes=[dict(kind='replace_inputs',inputs=raw)],decision=dict(alternatives=[],selected_id=None,rationale_ref=None)))
    candidate=service.preview(request)
    return service.apply(ApplyRequest(revision_contract=1,operation_id='replace',preview=request,candidate_digest=candidate.candidate_digest))


@pytest.fixture
def system(tmp_path):
    with Store(tmp_path) as store:
        from poliscope_engine.mechanisms import MechanismRegistry
        from poliscope_engine.numeric import Registry, Unit, parse
        base=mechanism_registry()
        registry=MechanismRegistry(model=base.model,units=Registry((*base.units.units,Unit('people',(('people',1),),'stock',parse('1')))),
            times=base.times,source_ids=base.source_ids,assumption_ids=base.assumption_ids,fixture_ids=base.fixture_ids,
            implementations=base.implementations,reviews=base.reviews,definitions=base.definitions,graphs=base.graphs)
        service=Revisions(store,registry=registry)
        raw=inputs().model_dump()
        raw['entities'].append(dict(id='population',entity_kind='population_cohort',label='Hypothetical solved population',provenance=raw['entities'][0]['provenance']))
        raw['populations']=[dict(entity_id='population',role='solved_capacity_bound')]
        # Quantity available = 20 kg; resource is fixed, solved entity has no fixed quantity.
        raw['values'][0]['value']['value']='20'
        created=service.create(CreateRequest.model_validate(dict(revision_contract=1,data_store_id=service.data_store_id,
            civilization_id='civ',branch_id='main',name='Hypothetical exact model',operation_id='create',inputs=raw)))
        yield service,created.context


def analysis_request(context):
    return dict(context=context.model_dump(),model=model(parameters=[parameter(low='2',high='5')]).model_dump())


def capacity_request(context,**updates):
    return dict(context=context.model_dump(),method='linear-resource-capacity-v1',solved_entity_id='population',solved_unit_id='people',
        scope_id='local',time_basis_id=None,lower='0',upper='100',quantum='1',iteration_limit=10,
        assumptions=[dict(id='synthetic:assumption',version='v1',rationale='Hypothetical 3 kg per person plus 2 kg fixed use; no social objective')],
        constraints=[dict(id='material',available_value_id='amount',fixed_demand='2',demand_per_unit='3',
            resource_unit_id='kg',solved_unit_id='people',interpretation='Hypothetical resource model',source_refs=[],assumption_refs=['synthetic:assumption'])]) | updates


def test_actual_analysis_pins_revision_types_time_provenance_and_digest(system):
    service,context=system
    before=count(service)
    report=dispatch(service,'uncertainty',analysis_request(context),'unused')
    row=report.observations[0]
    assert (row.low,row.high,row.unit_id,row.scope_id)==('2','5','kg','local')
    assert report.input_digest==digest(service.read(context).inputs)
    assert report.report_digest==digest(report.model_dump(exclude={'report_digest'}))
    assert report.assumptions==['synthetic:assumption']
    assert count(service)==before


def test_sensitivity_calls_actual_preview_without_committing_and_retains_explicit_choices(system):
    service,context=system
    request=analysis_request(context)
    request['variants']=[dict(id='low',values=[dict(variable_id='x',value='2',selection_ref='player:low-end')]),
        dict(id='high',values=[dict(variable_id='x',value='5',selection_ref='player:high-end')])]
    before=count(service)
    report=dispatch(service,'sensitivity',request,'unused')
    # Production synthetic mechanism is multiplication by 3. Independently expect 6/15.
    amounts=[]
    for variant in report.variants:
        values=[member.value.value for trace in variant.report.traces for member in trace.members if member.node[0]=='output']
        amounts.append(set(values))
    assert amounts==[{'6'},{'15'}]
    assert report.variants[0].selected.values[0].selection_ref=='player:low-end'
    assert len({v.physical_digest for v in report.variants})==2
    assert service.branch(context).context==context and count(service)==before
    assert service.read(context).inputs.values[0].value.value=='20'


@pytest.mark.parametrize('values,error', [([], 'at least 1'),([dict(variable_id='x',value='1',selection_ref='player:choice')],'variant_outside_declared_range'),
    ([dict(variable_id='other',value='2',selection_ref='player:choice')],'explicit_complete_variant_required')])
def test_sensitivity_never_chooses_missing_or_out_of_bounds_points(system,values,error):
    service,context=system
    with pytest.raises(ValueError,match=error):sensitivity(service,analysis_request(context)|dict(variants=[dict(id='v',values=values)]))


def test_resource_capacity_independent_feasible_infeasible_oracle_and_no_writes(system):
    service,context=system
    before=count(service)
    report=capacity(service,capacity_request(context))
    # 2 + 3*n <= 20 implies greatest whole n = 6; n=7 requires 23.
    assert report.status=='bounded' and (report.feasible,report.infeasible)==('6','7')
    assert report.witnesses[0].demand_at_feasible=='20'
    assert report.witnesses[0].demand_at_infeasible=='23'
    assert report.witnesses[0].available.value=='20'
    assert count(service)==before


@pytest.mark.parametrize('updates,status,feasible,infeasible', [
    (dict(upper='5'),'upper_feasible','5',None),
    (dict(lower='7'),'infeasible',None,'7'),
    (dict(iteration_limit=1),'solver_failure','0','50'),
    (dict(quantum='0.5'),'bounded','6','6.5')])
def test_capacity_interval_quantum_and_iteration_contract(system,updates,status,feasible,infeasible):
    service,context=system
    report=capacity(service,capacity_request(context,**updates))
    assert (report.status,report.feasible,report.infeasible)==(status,feasible,infeasible)


@pytest.mark.parametrize('updates,error', [
    (dict(quantum='0'),'invalid_capacity_grid'),(dict(lower='0.1'),'invalid_capacity_grid'),
    (dict(solved_entity_id='supply'),'solved_variable_also_fixed_or_evolving'),
    (dict(scope_id='missing'),'unknown_scope'),(dict(time_basis_id='day'),'capacity_resource_type_mismatch')])
def test_invalid_capacity_context_and_grid_fail(system,updates,error):
    service,context=system
    with pytest.raises(UncertaintyError,match=error):capacity(service,capacity_request(context,**updates))


def test_capacity_negative_slope_and_duplicate_resource_are_not_monotone_models(system):
    service,context=system
    request=capacity_request(context);request['constraints'][0]['demand_per_unit']='-1'
    with pytest.raises(UncertaintyError,match='nonmonotone'):capacity(service,request)
    request=capacity_request(context);request['constraints'].append(request['constraints'][0]|dict(id='another'))
    with pytest.raises(UncertaintyError,match='duplicate_resource_budget'):capacity(service,request)


def test_constant_constraint_can_make_whole_interval_infeasible(system):
    service,context=system
    request=capacity_request(context);request['constraints'][0].update(demand_per_unit='0',fixed_demand='21')
    report=capacity(service,request)
    assert report.status=='infeasible' and report.infeasible=='0'


def test_population_cannot_be_fixed_dynamic_and_solved_at_once(tmp_path):
    from poliscope_engine.workspace import registry, starting_inputs
    with Store(tmp_path) as store:
        service=Revisions(store,registry=registry())
        initial=starting_inputs(dict(name='Fixed',setup='blank',scope_name='Home',population='10',land_area='20'),'civ')
        result=service.create(CreateRequest(revision_contract=1,data_store_id=service.data_store_id,civilization_id='civ',branch_id='main',name='Fixed',operation_id='create',inputs=initial))
        with pytest.raises(UncertaintyError,match='population_role_conflict'):capacity(service,capacity_request(result.context))


def test_unresolved_sources_and_foreign_revision_are_rejected(system):
    service,context=system
    request=analysis_request(context);request['model']['parameters'][0]['source_refs']=['fake:source']
    with pytest.raises(UncertaintyError,match='unresolved_provenance'):analyze(service,request)
    request=analysis_request(context);request['context']['civilization_id']='foreign'
    with pytest.raises(ValueError):analyze(service,request)


def test_goals_cannot_enter_capacity_problem(system):
    service,context=system
    with pytest.raises(ValueError,match='Extra inputs'):capacity(service,capacity_request(context)|dict(player_target='9999'))


def test_two_resources_find_tighter_bound_with_independent_witnesses(system):
    service,context=system
    raw=service.read(context).inputs.model_dump()
    raw['values'].append(deepcopy(raw['values'][0]) | dict(id='second-resource',property_id='second-resource'))
    raw['values'][-1]['value']['value']='17'
    raw['owners'].append(raw['owners'][0] | dict(property_id='second-resource'))
    created=replace_record(service,context,raw)
    request=capacity_request(created.context)
    request['constraints'].append(request['constraints'][0]|dict(id='second',available_value_id='second-resource',fixed_demand='2',demand_per_unit='4'))
    report=capacity(service,request)
    assert (report.feasible,report.infeasible)==('3','4')
    assert [(w.demand_at_feasible,w.demand_at_infeasible) for w in report.witnesses]==[('11','14'),('14','18')]


def test_missing_resource_is_not_zero_capacity(system):
    service,context=system
    raw=service.read(context).inputs.model_dump()
    raw['values'][0]['value']=dict(kind='unknown',reason='Resource not measured')
    created=replace_record(service,context,raw)
    report=capacity(service,capacity_request(created.context))
    assert (report.status,report.feasible,report.infeasible)==('unmodeled',None,None)


def test_sensitivity_joint_support_rejects_impossible_combination(system):
    from test_uncertainty import common_cause
    service,context=system
    raw=service.read(context).inputs.model_dump()
    raw['values'].append(deepcopy(raw['values'][0])|dict(id='y',property_id='other'))
    raw['owners'].append(raw['owners'][0]|dict(property_id='other'))
    created=replace_record(service,context,raw)
    request=dict(context=created.context.model_dump(),model=common_cause().model_dump(),
        variants=[dict(id='impossible',values=[dict(variable_id='x',value='0',selection_ref='player:x'),dict(variable_id='y',value='1',selection_ref='player:y')])])
    with pytest.raises(UncertaintyError,match='variant_outside_joint_support'):sensitivity(service,request)
    request['variants'][0]['values'][1]['value']='0'
    assert len(sensitivity(service,request).variants)==1


def test_player_goal_change_cannot_change_physical_capacity(system):
    service,context=system
    before=capacity(service,capacity_request(context))
    raw=service.read(context).inputs.model_dump()
    raw['goals']=[dict(id='player:goal',kind='narrative',question='Could this settlement support a million people?',indicator_id=None,operation=None,threshold=None)]
    created=replace_record(service,context,raw)
    after=capacity(service,capacity_request(created.context))
    assert (after.feasible,after.infeasible,after.witnesses)==(before.feasible,before.infeasible,before.witnesses)


def test_population_unit_and_unknown_unit_are_rejected(system):
    service,context=system
    with pytest.raises(ValueError,match='population_unit_mismatch'):capacity(service,capacity_request(context,solved_unit_id='kg'))
    with pytest.raises(ValueError,match='unknown_unit'):capacity(service,capacity_request(context,solved_unit_id='invented'))


def test_model_assumptions_and_expression_units_cannot_be_invented(system):
    service,context=system
    request=analysis_request(context)
    request['model']['assumption_refs']=['missing:assumption']
    with pytest.raises(ValueError,match='unresolved_model_assumption'):analyze(service,request)
