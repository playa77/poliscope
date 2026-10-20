"""WP-027 production-service conformance, independently specified finite oracle."""
from copy import deepcopy
from dataclasses import replace, FrozenInstanceError
import json
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError
from poliscope_engine.contracts.domains import DomainModule, PairedDomainContract
from poliscope_engine.contracts.mechanisms import Domain, MechanismDefinition
from poliscope_engine.contracts.revisions import RevisionInputs
from poliscope_engine.contracts.world import PartitionValueDTO
from poliscope_engine.domains import DomainRegistry, ConformanceError, templates
from poliscope_engine.domains.conformance import run_case, stage_transition
from poliscope_engine.mechanisms import MechanismError
from poliscope_engine.world import WorldRegistry, StateOwner, PopulationDeclaration
from poliscope_engine.world.membership import WorldGraph
from domain_fixture import case, catalog, registry, fixture

BRANCHES = ['synthetic:economy', 'synthetic:provisioning']


def run(c=None, cat=None, host=None, branches=BRANCHES):
    return run_case(c or case(), catalog=cat or catalog(), mechanisms=host or registry(), branch_ids=branches)


def world(data=None):
    data=data or case().inputs
    return WorldRegistry('civ',entities=data.entities,scopes=data.scopes,values=data.values,
        owners=[StateOwner(**o.model_dump()) for o in data.owners],
        populations=[PopulationDeclaration(**p.model_dump()) for p in data.populations])


def changed(edit):
    data=case().inputs.model_dump(mode='json')
    edit(data)
    return replace(case(),inputs=RevisionInputs.model_validate(data))


def edited_catalog(edit):
    mods=[m.model_dump(mode='json') for m in catalog().modules]
    edit(mods)
    return DomainRegistry([DomainModule.model_validate(m) for m in mods])


def validate(cat, branches=BRANCHES):
    return cat.validate(world=world(),mechanisms=registry(),branch_ids=branches)


@pytest.mark.parametrize('domain', get_args(Domain))
def test_every_domain_uses_the_same_real_conformance_path(domain):
    # Reclassify the consumer only; no separate engine/account implementation.
    defs=fixture()['definitions']
    defs[0]['domain']=domain
    r=registry(definitions=defs)
    cat=catalog(r.definitions)
    result=run(host=r,cat=cat,branches=['synthetic:'+m.domain for m in cat.modules])
    assert result.outcome=='insufficient'
    assert {c.claim_id:c.actual for c in result.accounts.claims}=={'a':'60','b':'40'}
    assert sum(int(c.actual) for c in result.accounts.claims)==100


def test_finite_stock_labor_actual_output_provenance_and_trace_oracle():
    result=run()
    assert result==run()
    # 100 input -> 70 product + 20 residual + 10 loss, 10 of 12 labor used.
    assert {a.account_id:a.closing for a in result.accounts.accounts}=={
        'stock':'0','product':'70','residual':'20','labor':'2'}
    assert case().inputs.design.execution.batch.accounts[0].opening=='100'


@pytest.mark.parametrize('field,value,code', [
    ('runtime','domain_engine','literal_error'),
    ('persistence','private_database','literal_error'),
    ('database_path','domain.sqlite','extra_forbidden'),
    ('python_module','untrusted.plugin','extra_forbidden'),
])
def test_domain_engines_databases_and_imports_fail_closed(field,value,code):
    raw=catalog().modules[0].model_dump(mode='json')
    raw[field]=value
    with pytest.raises(ValidationError,match=code):DomainModule.model_validate(raw)


@pytest.mark.parametrize('edit,code', [
    (lambda ms: ms[0]['interfaces'][0]['value_type'].update(unit_id='hours'),'interface_type_mismatch'),
    (lambda ms: ms[0]['interfaces'][0]['references'][0].update(entity_kind='resource'),'shared_reference_kind'),
    (lambda ms: ms[0]['interfaces'].pop(),'incomplete_interface_catalog'),
    (lambda ms: ms[0]['coverage'][0].update(branch_id='absent'),'unknown_branch'),
    (lambda ms: ms[0]['coverage'][0].update(transition_available=True),'unsupported_execution_claim'),
    (lambda ms: ms[0]['coverage'][0].update(evidence_status='supported'),'unsupported_evidence_claim'),
    (lambda ms: ms[0]['coverage'][0].update(source_refs=['invented:evidence']),'unresolved_provenance'),
    (lambda ms: ms[0]['coverage'][0].update(scope_kinds=['household']),'coverage_scope_mismatch'),
    (lambda ms: ms[0]['authorities'].append(dict(entity_id='water',property_id='water-stock',partition='conditions',owner=ms[0]['domain'])),'state_authority_mismatch'),
])
def test_catalog_rejects_false_types_coverage_authority_and_evidence(edit,code):
    with pytest.raises(ConformanceError,match=code):validate(edited_catalog(edit))


def test_exhaustive_coverage_and_unknown_is_not_zero():
    with pytest.raises(ConformanceError,match='incomplete_branch_coverage'):
        validate(catalog(),BRANCHES+['hidden:branch'])
    c=changed(lambda d: d['design']['execution']['dependencies']['fixed_inputs'].pop())
    # A missing requested amount must not satisfy the finite numerical oracle.
    with pytest.raises(ConformanceError,match='unexpected_'):
        run(c)


def test_double_writer_and_foreign_owner_fail_before_evaluation():
    mods=[m.model_dump(mode='json') for m in catalog().modules]
    for m in mods:
        m['authorities']=[dict(entity_id='water',property_id='water-stock',partition='conditions',owner=m['domain'])]
    with pytest.raises(ValueError,match='duplicate_identity'):
        DomainRegistry([DomainModule.model_validate(m) for m in mods])
    mods[0]['authorities'][0]['owner']=mods[1]['domain']
    with pytest.raises(ValidationError,match='foreign_state_owner'):DomainModule.model_validate(mods[0])


@pytest.mark.parametrize('change', ['duplicate_account','duplicate_claim','overspend','wrong_unit','wrong_scope','missing_source','missing_review'])
def test_invalid_module_and_global_budget_mutations_fail(change):
    if change=='missing_source':
        with pytest.raises(ConformanceError,match='unresolved_provenance'):run(host=registry(source_ids=[]))
        return
    if change=='missing_review':
        with pytest.raises(MechanismError,match='review_required'):run(host=registry(reviews=[]))
        return
    def edit(d):
        e=d['design']['execution']
        if change=='duplicate_account':e['batch']['accounts'].append(deepcopy(e['batch']['accounts'][0]))
        if change=='duplicate_claim':e['batch']['claims'].append(deepcopy(e['batch']['claims'][0]))
        if change=='overspend':e['batch']['postings'].append(dict(id='double-spend',kind='loss',source_id='stock',destination_id=None,amount='101',reservation_id=None,claim_id=None,mechanism_ref='synthetic:spend',source_refs=[]))
        if change=='wrong_unit':e['dependencies']['fixed_inputs'][0]['value']['unit_id']='hours'
        if change=='wrong_scope':d['scopes'][0]['scope_kind']='household'
    # Contract, context or global account rejection must happen on the real route.
    with pytest.raises(ValueError):run(changed(edit))


def test_disconnected_actual_allocation_cannot_fabricate_requested_output():
    def fabricated(port,inputs):
        return inputs['synthetic:need']
    with pytest.raises(ConformanceError,match='unexpected_'):
        run(host=registry(callback=fabricated))


def test_repeatability_guard_detects_stateful_trusted_callback():
    n=0
    def impure(port,inputs):
        nonlocal n
        n+=1
        q=inputs['synthetic:need' if port=='synthetic:requested' else 'synthetic:allocated']
        return q.model_copy(update={'value':str(n)}) if port=='synthetic:supported' else q
    with pytest.raises(ConformanceError,match='impure_evaluation'):run(host=registry(callback=impure))


def test_catalog_and_fixture_returns_are_detached():
    cat=catalog()
    cat.modules[0].interfaces.clear()
    assert cat.modules[0].interfaces
    with pytest.raises(FrozenInstanceError):cat._modules=()
    c=case()
    run(c)
    assert c==case()


def pair(status='ready_for_conformance',**updates):
    cat=catalog()
    # Both ports use exactly the same kg type and canonical stock reference.
    refs=[next(i.id for i in m.interfaces if i.direction==direction) for m,direction in zip(cat.modules,('input','output'))]
    return PairedDomainContract.model_validate(dict(contract_version=1,id='pair:synthetic',domains=['economy','provisioning'],
        integration_owner='economy',owner_status='designated',shared_references=[dict(entity_id='stock',entity_kind='account')],
        interface_refs=refs,fixture_refs=[dict(id='synthetic:domain-conformance',version='v1')],status=status,
        limits='Synthetic exact-type interface fixture only.')|updates)


def test_paired_contract_checks_both_domains_exact_types_and_authoritative_ids():
    cat=DomainRegistry(catalog().modules,[pair()])
    validate(cat)
    with pytest.raises(ConformanceError,match='counterpart_identity_mismatch'):
        validate(DomainRegistry(cat.modules,[pair(shared_references=[dict(entity_id='water',entity_kind='resource')])]))
    with pytest.raises(ConformanceError,match='missing_counterpart_interface'):
        validate(DomainRegistry(cat.modules,[pair(interface_refs=['missing'])]))
    with pytest.raises(ConformanceError,match='unresolved_counterpart_fixture'):
        validate(DomainRegistry(cat.modules,[pair(fixture_refs=[dict(id='unreviewed',version='v1')])]))


def test_unresolved_counterpart_owner_is_visible_and_cannot_be_ready():
    pending=pair(status='pending_counterpart',owner_status='unresolved',integration_owner=None)
    assert pending.integration_owner is None
    with pytest.raises(ValidationError,match='incomplete_counterpart_contract'):
        pair(owner_status='unresolved',integration_owner=None)


def test_all_branch_templates_and_counterpart_dependencies_match_pinned_inventory():
    t=templates()
    inventory=json.loads(Path('content/release-v1/society.inventory.json').read_text())
    assert {m.domain for m in t.modules}==set(get_args(Domain))
    expected={b['id'] for d in inventory['domains'] for b in d['branches']}
    actual={b.branch_id for m in t.modules for b in m.coverage}
    assert actual==expected and len(actual)==38
    import re
    text=Path('docs/roadmap/domain_work_packages.md').read_text()
    sections=re.split(r'### DOM-(\d+) —',text)[1:]
    expected_pairs=set()
    domains=get_args(Domain)
    for number,section in zip(sections[::2],sections[1::2]):
        line=next(l for l in section.splitlines() if '**Integration counterparts:**' in l)
        counterparts=range(1,13) if 'all other domains' in line else map(int,re.findall(r'DOM-(\d+)',line))
        for other in counterparts:
            if int(number)!=other:expected_pairs.add(frozenset((domains[int(number)-1],domains[other-1])))
    assert {frozenset(p.domains) for p in t.pairs}==expected_pairs
    assert len(t.pairs)==44
    t.validate(world=world(),mechanisms=registry(),branch_ids=expected)
    assert all(b.status=='unresolved' and not b.static_available and not b.transition_available for m in t.modules for b in m.coverage)
    assert all(p.status=='pending_counterpart' and p.integration_owner in p.domains for p in t.pairs)
    assert not any(m.authorities or m.mechanisms for m in t.modules)


def transition_fixture():
    defs=fixture()['definitions']
    # Extend supply-shaped policy declaration with one owned label proposal.
    d=defs[2]
    d['owned_state']=[dict(id='synthetic:state',owner_domain='provisioning',partition='dynamic_state',value_type=dict(kind='label'))]
    d['write_state_refs']=['synthetic:state']
    d['support']['transition']=dict(kind='trusted_python',implementation=dict(id='synthetic:transition',version='v1'))
    r=registry(definitions=defs)
    mods=[m.model_dump(mode='json') for m in catalog(r.definitions).modules]
    m=next(m for m in mods if m['domain']=='provisioning')
    m['authorities']=[dict(entity_id='water',property_id='synthetic:state',partition='dynamic_state',owner='provisioning')]
    m['transitions']=[dict(mechanism=dict(id=d['id'],version=d['version']),entity_id='water',scope_id='east',property_refs=['synthetic:state'],status='proposal_only')]
    data=case().inputs
    w=WorldRegistry('civ',entities=data.entities,scopes=data.scopes,values=data.values,
        owners=[StateOwner(**o.model_dump()) for o in data.owners]+[StateOwner('water','synthetic:state','dynamic_state','provisioning')],
        populations=[PopulationDeclaration(**p.model_dump()) for p in data.populations])
    cat=DomainRegistry([DomainModule.model_validate(m) for m in mods])
    cat.validate(world=w,mechanisms=r,branch_ids=BRANCHES)
    change=PartitionValueDTO.model_validate(dict(id='synthetic:state-value',entity_id='water',scope_id='east',partition='dynamic_state',property_id='synthetic:state',value=dict(kind='label',value='pending'),effective_time=dict(tick=1,calendar_id='calendar'),provenance=dict(origin='authored',source_refs=[],assumption_refs=[])))
    return cat,r,w,change


def test_transition_hook_stages_private_candidate_and_preserves_original():
    cat,r,w,c=transition_fixture()
    result=stage_transition(catalog=cat,mechanisms=r,world=w,module_domain='provisioning',mechanism=('synthetic:access-policy','v1'),entity_id='water',scope_id='east',changes=[c])
    assert len(result.values)==len(w.values)+1
    assert not any(v.id==c.id for v in w.values)


@pytest.mark.parametrize('field,value,code', [
    ('property_id','foreign','undeclared_transition_write'),
    ('entity_id','stock','undeclared_state_write'),
    ('scope_id','west','undeclared_state_write'),
])
def test_transition_hook_cannot_write_foreign_state(field,value,code):
    cat,r,w,c=transition_fixture()
    with pytest.raises(ValueError,match=code):
        stage_transition(catalog=cat,mechanisms=r,world=w,module_domain='provisioning',mechanism=('synthetic:access-policy','v1'),entity_id='water',scope_id='east',changes=[c.model_copy(update={field:value})])


def test_unavailable_transition_does_not_invent_procedure():
    with pytest.raises(ConformanceError,match='unavailable_transition'):
        stage_transition(catalog=catalog(),mechanisms=registry(),world=world(),module_domain='economy',mechanism=('synthetic:demand','v1'),entity_id='stock',scope_id='east',changes=[])


@pytest.mark.parametrize('scope',['east','west'])
def test_same_canonical_budget_supports_two_local_scopes(scope):
    def edit(d):
        for a in d['design']['execution']['batch']['accounts']:a['scope_id']=scope
        for i in d['design']['execution']['dependencies']['instances']:i['scope_id']=scope
    result=run(changed(edit))
    assert {o.scope_id for o in result.observations if o.node[0]=='output'}=={scope}
    graph=WorldGraph(world(),case().inputs.relationships)
    assert graph.aggregate(['east','watershed','region'],property_id='water-stock',partition='conditions').value=='100'


@pytest.mark.parametrize('reverse',[False,True])
def test_overlapping_institutions_preserve_conflict_and_finite_outcomes(reverse):
    from poliscope_engine.contracts.world import QuantityValue
    def edit(d):
        d['design']['policies']=[dict(contract_version=1,id=i,mechanism=dict(id='synthetic:access-policy',version='v1'),
            scope_id=s,authority_id=a,entity_ids=['water'],parameter_id='synthetic:limit',
            value=QuantityValue(kind='quantity',unit_id='kg',time_basis_id=None,denominator_scope_id=None,value=v).model_dump(),
            conflict_kind='allocation',account_refs=['stock'],choice_refs=[]) for i,s,a,v in
            [('east-limit','east','east-authority','40'),('region-limit','region','region-authority','60')]]
        if reverse:
            d['design']['policies'].reverse()
            d['relationships'].reverse()
    # Independent fixed demand remains finite; unresolved authority has no winner.
    c=replace(changed(edit),outcome='unresolved')
    result=run(c)
    finding=result.policies.results[0]
    assert finding.status=='conflict' and finding.value is None
    assert finding.source_refs==['synthetic:source']
    assert finding.findings[0].account_refs==['stock']


def test_real_counterpart_binding_checks_context_and_exact_units():
    r=registry()
    bound=r.bind(('synthetic:access-policy','v1'),('synthetic:demand','v1'),output_id='synthetic:available',input_id='synthetic:allocated',world=world(),scope_id='east',producer_entity_id='water',consumer_entity_id='stock')
    assert bound.unit_id=='kg'
    with pytest.raises(MechanismError,match='incompatible_port'):
        r.bind(('synthetic:access-policy','v1'),('synthetic:demand','v1'),output_id='missing',input_id='synthetic:allocated',world=world(),scope_id='east',producer_entity_id='water',consumer_entity_id='stock')


def test_missing_input_returns_explicit_unavailable_observations():
    c=changed(lambda d: d['design']['execution']['dependencies']['fixed_inputs'].clear())
    from poliscope_engine.evaluation import evaluate
    result=evaluate(WorldGraph(world(c.inputs),c.inputs.relationships),c.inputs.design,[],registry().model,registry=registry())
    missing=[o for o in result.observations if o.node[0]=='output']
    assert missing and all(o.status!='known' and (o.value is None or o.value.kind=='unknown') for o in missing)


def test_unknown_unit_in_a_consistent_module_still_requires_numeric_registry():
    from poliscope_engine.numeric import NumericError
    defs=fixture()['definitions']
    # Edit all local claim/dependency port types consistently; local structural
    # validity cannot turn a made-up unit into a registered engine unit.
    for d in defs:
        for port in [*d['inputs'],*d['outputs']]:
            if port['value_type']['kind']=='quantity':port['value_type']['unit_id']='unregistered'
    r=registry(definitions=defs)
    with pytest.raises(NumericError,match='unknown_unit'):
        catalog(r.definitions).validate(world=world(),mechanisms=r,branch_ids=BRANCHES)


def test_foreign_transition_cannot_borrow_another_modules_valid_write_hook():
    cat,r,w,c=transition_fixture()
    mods=[m.model_dump(mode='json') for m in cat.modules]
    economy=next(m for m in mods if m['domain']=='economy')
    # Even a syntactically valid fabricated module cannot claim a foreign rule.
    foreign=next(d for d in r.definitions if d.id=='synthetic:access-policy')
    economy['mechanisms'].append(dict(id=foreign.id,version=foreign.version))
    economy['transitions']=[dict(mechanism=dict(id=foreign.id,version=foreign.version),entity_id='water',scope_id='east',property_refs=['synthetic:state'],status='proposal_only')]
    forged=DomainRegistry([DomainModule.model_validate(m) for m in mods])
    with pytest.raises(ConformanceError,match='foreign_mechanism_domain'):
        stage_transition(catalog=forged,mechanisms=r,world=w,module_domain='economy',mechanism=('synthetic:access-policy','v1'),entity_id='water',scope_id='east',changes=[c])
