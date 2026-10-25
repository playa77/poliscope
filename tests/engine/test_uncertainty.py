"""Independent exact examples; hypothetical parameters convey no scientific validity."""
from copy import deepcopy
from decimal import localcontext
from fractions import Fraction
import pytest
from poliscope_engine.contracts.uncertainty import UncertaintyModel
from poliscope_engine.uncertainty import propagate, UncertaintyError


def parameter(identity='x', form='bounded_range', **updates):
    return dict(id=identity,version='v1',value_id='amount' if identity == 'x' else identity,
        form=form,point=None,low='0' if form == 'bounded_range' else None,high='1' if form == 'bounded_range' else None,
        interpretation='Hypothetical parameter',source_refs=[],assumption_refs=['synthetic:assumption']) | updates


def expression(terms=None, **updates):
    return dict(id='out',version='v1',constant='0',terms=[dict(variable_id=k,coefficient=v) for k,v in (terms or [('x','1')])],
        threshold='0.5',operation='lt',interpretation='Hypothetical observation') | updates


def model(parameters=None, expressions=None, **updates):
    return UncertaintyModel.model_validate(dict(id='synthetic:model',version='v1',method='affine-box-v1',dependence='declared_box',
        parameters=parameters or [parameter()],expressions=expressions or [expression()],factors=[],
        assumption_refs=['synthetic:assumption'],assumptions=[dict(id='synthetic:assumption',version='v1',rationale='Explicit hypothetical box/factorization; not an empirical model')],state_limit=1000) | updates)


def probability(n,d):
    return dict(numerator=str(n),denominator=str(d))


def factor(identity, variables, outcomes, parents=(), given=None):
    return dict(id=identity,version='v1',variables=variables,parents=list(parents),
        rows=[dict(given=given or {},outcomes=[dict(values=v,probability=probability(n,d)) for v,n,d in outcomes])],
        interpretation='Explicit hypothetical joint law',assumption_refs=['synthetic:assumption'])


def test_same_variable_cancels_before_interval_propagation():
    # x + (1-x) = 1 for every real x, not [0,2].
    row = propagate(model(expressions=[expression([('x','1'),('x','-1')],constant='1',threshold='1',operation='eq')]))[0]
    assert (row['low'],row['high'],row['diagnostic'],row['probability']) == ('1','1','always',None)


@pytest.mark.parametrize('operation,threshold,expected', [('lt','0','never'),('le','0','overlap'),('eq','0','overlap'),('ne','2','always'),('gt','1','never'),('ge','1','overlap'),('le','1','always')])
def test_exact_threshold_boundaries(operation,threshold,expected):
    row=propagate(model(expressions=[expression(operation=operation,threshold=threshold)]))[0]
    assert row['diagnostic']==expected


def test_signed_affine_box_matches_all_independently_enumerated_corners():
    m=model(parameters=[parameter('x',low='2',high='5'),parameter('y',low='3',high='7')],
        expressions=[expression([('x','-2'),('y','3')],constant='1')])
    # extrema among 1-2*2+3*3, 1-2*2+3*7, 1-2*5+3*3, 1-2*5+3*7
    row=propagate(m)[0]
    assert (row['low'],row['high']) == ('0','18')
    assert row['probability'] is None  # ranges are not uniform probabilities


def common_cause():
    # Both supplies fail together with probability 1/4. Shortage when any fails.
    return model(parameters=[parameter('x','distribution'),parameter('y','distribution')],
        expressions=[expression([('x','1'),('y','1')],threshold='2')],
        method='finite-factorization-v1',dependence='declared_factorization',
        factors=[factor('joint',['x','y'],[({'x':'0','y':'0'},1,4),({'x':'1','y':'1'},3,4)])])


def test_joint_common_cause_shortage_is_one_quarter_not_independent_seven_sixteenths():
    row=propagate(common_cause())[0]
    assert row['probability'].model_dump()==probability(1,4)
    assert row['low']=='0' and row['high']=='2'
    independent=common_cause().model_dump()
    independent['factors']=[factor('x',['x'],[({'x':'0'},1,4),({'x':'1'},3,4)]),factor('y',['y'],[({'y':'0'},1,4),({'y':'1'},3,4)])]
    assert propagate(UncertaintyModel.model_validate(independent))[0]['probability'].model_dump()==probability(7,16)


def test_conditional_common_cause_matches_joint_and_does_not_resample_parent():
    m=common_cause().model_dump()
    m['factors']=[factor('parent',['x'],[({'x':'0'},1,4),({'x':'1'},3,4)]),
        factor('child',['y'],[({'y':'0'},1,1)],['x'],{'x':'0'})]
    m['factors'][1]['rows'].append(dict(given={'x':'1'},outcomes=[dict(values={'y':'1'},probability=probability(1,1))]))
    assert propagate(UncertaintyModel.model_validate(m))==propagate(common_cause())


def test_probability_repeated_reference_and_nonconvex_support_threshold():
    m=common_cause().model_dump()
    m['expressions']=[expression([('x','1'),('x','-1')],constant='1',threshold='1',operation='eq'),
        expression([('x','1')],id='hole',threshold='0.5',operation='eq')]
    rows=propagate(UncertaintyModel.model_validate(m))
    assert [r['probability'].model_dump() for r in rows]==[probability(1,1),probability(0,1)]
    assert rows[1]['diagnostic']=='never'  # not interval-overlap over the support hole


@pytest.mark.parametrize('change,reason', [({'method':'unsupported'},'unsupported_propagation_method'),({'dependence':'unresolved'},'explicit_admissible_box_required')])
def test_unsupported_returns_no_numbers(change,reason):
    row=propagate(model(**change))[0]
    assert row['status']=='unmodeled' and row['reason']==reason and row['low'] is None and row['probability'] is None


def test_exact_state_limit_returns_coverage_not_truncated_probability():
    m=common_cause().model_copy(update={'state_limit':1})
    assert propagate(m)[0]['reason']=='exact_state_limit_exceeded'


@pytest.mark.parametrize('mutate,error', [
    (lambda m:m['parameters'][0].update(point='0.5'),'range_requires_ordered_bounds'),
    (lambda m:m['parameters'][0].update(high='-1'),'range_requires_ordered_bounds'),
    (lambda m:m['expressions'][0]['terms'][0].update(variable_id='missing'),'unknown_variable'),
    (lambda m:m.update(assumptions=[]),'at least 1')])
def test_invalid_range_and_reference_inputs_fail(mutate,error):
    m=model().model_dump();mutate(m)
    with pytest.raises((ValueError,UncertaintyError),match=error):propagate(UncertaintyModel.model_validate(m))


@pytest.mark.parametrize('mutation,error', [
    (lambda m:m['factors'][0]['rows'][0]['outcomes'][0].update(probability=probability(-1,4)),'invalid_probability'),
    (lambda m:m['factors'][0]['rows'][0]['outcomes'][0].update(probability=probability(1,2)),'probabilities_must_sum_to_one'),
    (lambda m:m['factors'][0]['rows'][0]['outcomes'][0].update(values={'x':'0'}),'joint_variable_mismatch'),
    (lambda m:m['factors'].append(deepcopy(m['factors'][0])),'duplicate_identity')])
def test_malformed_joint_models_fail(mutation,error):
    m=common_cause().model_dump();mutation(m)
    with pytest.raises(UncertaintyError,match=error):propagate(UncertaintyModel.model_validate(m))


def test_no_global_decimal_context_or_presentation_order_dependency():
    m=common_cause()
    expected=propagate(m)
    with localcontext() as c:
        c.prec=2
        assert propagate(m)==expected
    raw=m.model_dump();raw['parameters'].reverse();raw['factors'][0]['rows'][0]['outcomes'].reverse()
    assert propagate(UncertaintyModel.model_validate(raw))==expected


def test_conditional_missing_and_unreachable_rows_fail_and_cycles_are_qualified():
    m=common_cause().model_dump()
    m['factors']=[factor('parent',['x'],[({'x':'0'},1,4),({'x':'1'},3,4)]),
        factor('child',['y'],[({'y':'0'},1,1)],['x'],{'x':'0'})]
    with pytest.raises(UncertaintyError,match='missing_conditional_row'):propagate(UncertaintyModel.model_validate(m))
    m['factors'][1]['rows'].append(dict(given={'x':'1'},outcomes=[dict(values={'y':'1'},probability=probability(1,1))]))
    m['factors'][1]['rows'].append(dict(given={'x':'2'},outcomes=[dict(values={'y':'1'},probability=probability(1,1))]))
    with pytest.raises(UncertaintyError,match='unreachable_conditional_row'):propagate(UncertaintyModel.model_validate(m))
    m['factors']=[factor('x',['x'],[({'x':'0'},1,1)],['y'],{'y':'0'}),factor('y',['y'],[({'y':'0'},1,1)],['x'],{'x':'0'})]
    assert propagate(UncertaintyModel.model_validate(m))[0]['reason']=='cyclic_or_unresolved_dependence'


def test_mixed_range_probability_is_not_implicitly_independent():
    m=common_cause().model_dump();m['parameters'].append(parameter('z'))
    assert propagate(UncertaintyModel.model_validate(m))[0]['reason']=='mixed_range_probability_not_supported'


def test_unresolved_factorization_never_multiplies_marginals():
    m=common_cause().model_copy(update={'dependence':'unresolved'})
    row=propagate(m)[0]
    assert row['status']=='unmodeled' and row['probability'] is None


def test_precision_failure_does_not_erase_independent_expression():
    m=model(parameters=[parameter(form='point',point='9999999999999999999999999999',low=None,high=None)],
        expressions=[expression([('x','9')]),expression([('x','0')],id='independent',constant='1')])
    rows=propagate(m)
    assert rows[0]['status']=='solver_failure' and rows[0]['low'] is None
    assert rows[1]['status']=='known' and rows[1]['low']=='1'
