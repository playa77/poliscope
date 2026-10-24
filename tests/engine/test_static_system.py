"""Whole-system finite constraints: literal expectations and hostile contexts."""
from copy import deepcopy
from fractions import Fraction
import pytest
from poliscope_engine.accounts import AccountError
from poliscope_engine.domains.static_system import evaluate_system, DOMAINS
from static_system_fixture import fixture, setup, set_work


def run(data=None):
    request, context = setup(data)
    return evaluate_system(request, **context)


def test_actual_twelve_domain_path_preserves_independent_shortages_and_overlap():
    data = fixture(); before = deepcopy(data)
    result = run(data)
    assert set(result['evaluations']) == set(DOMAINS)
    assert result['status'] == 'resolved'
    local = result['local_readiness']
    assert local['knowledge_culture'] == {'course': 'ready'}
    assert local['health'] == {'clinic': 'blocked'}
    assert local['governance'] == {'a': 'ready'}
    assert local['law_conflict'] == {'case:a': 'ready', 'case:b': 'blocked'}
    assert result['integrated_readiness']['knowledge_culture'] == {'course': 'blocked'}
    ev = result['evaluations']
    # Twelve hours: 3 administration + 3 second case + 4 care + 2 training.
    work = ev['economy']['allocation']
    assert {c['claim_id']: c['allocated'] for c in work['actuals']} == {
        'admin':'3', 'case:b':'3', 'care':'4', 'learning':'2', 'patient':'0',
        'job':'0', 'teach':'2', 'nurse':'1', 'materials':'2', 'medicine':'2'}
    assert sum(Fraction(c['allocated']) for c in work['actuals']
               if c['claim_id'] in ('admin','case:b','care','learning','patient','job')) == 12
    assert ev['social_organization']['population']['value'] == '10'
    assert [v['population']['value'] for v in ev['social_organization']['arrangements']] == ['10','10']
    assert ev['health']['results'][0]['unmet_claim_ids'] == ['patient','nurse','bed']
    assert ev['infrastructure']['results'][1]['unmet'] == '1'
    assert ev['communication']['results'][1]['unmet'] == '2'
    assert ev['meaning_identity']['results'][1]['unmet'] == '1'
    assert ev['security_risk']['results'][1]['unmet'] == '1'
    assert result['missing_effects'] and result['coverage_status'] == 'partial'
    assert data == before and result == run(data)


def test_requirement_order_does_not_choose_a_winner_or_turn_unknown_into_zero():
    data = fixture()
    data['request']['communication']['demands'][0]['disclosure'] = 'unknown'
    first = run(data)
    data['request']['requirements'].reverse()
    second = run(data)
    assert first['integrated_readiness'] == second['integrated_readiness']
    assert first['integrated_readiness']['knowledge_culture']['course'] == 'unresolved'
    assert first['local_readiness']['knowledge_culture']['course'] == 'ready'


@pytest.mark.parametrize('mutation,code', [
    ('book','static_system_competing_book'), ('period','static_system_period_mismatch'),
    ('scope','static_system_scope_mismatch'), ('identity','static_system_shared_identity'),
    ('unused','static_system_unused_reference'), ('result','static_system_unknown_result'),
])
def test_forged_or_incompatible_counterpart_contexts_fail(mutation, code):
    data = fixture(); req = data['request']
    if mutation == 'book': req['health']['work']['batch']['accounts'][0]['opening'] = '999'
    elif mutation == 'period': req['communication']['period_id'] = 'day:1'
    elif mutation == 'scope': req['health']['scope_id'] = 'region'
    elif mutation == 'identity': req['requirements'][0]['shared_references'][0]['entity_kind'] = 'institution'
    elif mutation == 'unused': req['requirements'][0]['shared_references'][0] = dict(entity_id='food',entity_kind='resource')
    else: req['requirements'][0]['source_result_id'] = 'forged'
    with pytest.raises(AccountError, match=code): run(data)


def test_unknown_shared_work_is_not_an_exception_or_a_complete_candidate():
    data = fixture(); work = data['request']['economy']; work['procedure'] = None
    set_work(data, work)
    result = run(data)
    assert result['status'] == 'unresolved'
    assert result['local_readiness']['provisioning'] == {'chain': 'unresolved'}
    assert set(result['local_readiness']['economy'].values()) == {'unresolved'}


def ample(data):
    work = data['request']['economy']
    for a in work['batch']['accounts']: a['opening'] = '100'
    set_work(data, work)
    for domain in ('health','knowledge_culture'):
        for a in data['request'][domain]['facility_allocation']['batch']['accounts']: a['opening'] = '100'
    for domain in ('infrastructure','communication','environment','meaning_identity','security_risk'):
        for a in data['request'][domain]['batch']['accounts']: a['opening'] = '100'
    return data


NEW_PAIRS = [r['id'] for r in fixture()['request']['requirements'] if r['id'].startswith('pair:')]


@pytest.mark.parametrize('pair_id', NEW_PAIRS)
@pytest.mark.parametrize('access,expected', [('denied','blocked'),('unknown','unresolved')])
def test_each_remaining_counterpart_uses_actual_source_semantics(pair_id,access,expected):
    data = ample(fixture()); req = data['request']
    link = next(r for r in req['requirements'] if r['id'] == pair_id)
    source, target = link['source'], link['target']
    for domain in DOMAINS:
        if domain not in (source,target): req[domain] = None
    req['requirements'] = [link]
    before = run(data)
    assert before['integrated_readiness'][target][link['target_result_id']] == 'ready'
    if source == 'health': req[source]['services'][0]['eligibility'] = access
    elif source == 'communication': req[source]['demands'][0]['receive_access'] = access
    else: req[source]['demands'][0]['access'] = access
    after = run(data)
    assert after['local_readiness'][source][link['source_result_id']] == expected
    assert after['local_readiness'][target][link['target_result_id']] == 'ready'
    assert after['integrated_readiness'][target][link['target_result_id']] == expected
    # Report-level requirements never erase independent input commitments or
    # promote local capacity to delivered service or a newly granted right.
    assert before['evaluations'][target] == after['evaluations'][target]


def test_all_modules_actual_common_conformance_and_retained_account_snapshot():
    from poliscope_engine.domains.static_host import conformance_catalog
    from poliscope_engine.domains.conformance import run_case, ConformanceCase
    from static_system_fixture import trusted
    request, ctx, registry, inputs = trusted()
    catalog = conformance_catalog()
    assert len(catalog.pairs) == 44
    assert all(p.status == 'ready_for_conformance' for p in catalog.pairs)
    from poliscope_engine.domains.static_host import run_bound_case
    result = run_bound_case(ConformanceCase(inputs, 'incomplete', ()), request=request,
        units=ctx['units'], mechanisms=ctx['mechanisms'], reviews=registry.reviews)
    outputs = [o for o in result.observations if o.node[0] == 'output' and o.node[1] in DOMAINS]
    assert len(outputs) == 12
    import json
    by_domain = {o.node[1]: json.loads(o.value.value) for o in outputs}
    assert by_domain['knowledge_culture']['integrated_readiness'] == {'course':'blocked'}
    assert {a.account_id:a.closing for a in result.accounts.accounts}['time:a'] == '0'


@pytest.mark.parametrize('domain', DOMAINS)
def test_entry_choice_originates_in_each_actual_domain_without_default_or_mutation(domain):
    import importlib
    from poliscope_engine.contracts.provisioning import ProvisioningRequest, ProcedureEdit
    from static_system_fixture import setup
    data = fixture(); before = deepcopy(data); request, ctx = setup(data)
    module = importlib.import_module('poliscope_engine.domains.'+domain+'.exploration')
    node = getattr(request,domain)
    args = dict(graph=ctx['graph'],units=ctx['units'])
    if domain in ('governance','law_conflict','knowledge_culture','health'):
        args['mechanisms'] = ctx['mechanisms']
    if domain == 'provisioning':
        node = ProvisioningRequest.model_validate(run(data)['evaluations']['provisioning']['request'])
        card = module.interview(node,ctx['units'],'use','local')
        edit = ProcedureEdit(baseline_digest=card.baseline_digest,scope_id='local',phase_id='use',
            option_id=card.alternatives[1].definition.id,claim_order=card.claim_ids)
        preview = module.preview(node,ctx['units'],edit)
        req = data['request']['provisioning']['chain']
        req['phases'][0]['procedure'] = preview.report.evaluation.request.phases[0].procedure
    elif domain == 'economy':
        from poliscope_engine.contracts.economy import EconomyEdit
        card = module.interview(node,ctx['units'],'local')
        edit = EconomyEdit(baseline_digest=card.baseline_digest,scope_id='local',
            option_id=card.alternatives[1].definition.id,claim_order=card.claim_ids)
        preview = module.preview(node,ctx['units'],edit)
        set_work(data,preview.report.evaluation.request.model_dump(mode='json'))
    else:
        names = dict(governance='GovernanceEdit',law_conflict='AdjudicationEdit',
            social_organization='CareEdit',knowledge_culture='EducationEdit',health='HealthEdit',
            infrastructure='InfrastructureEdit',communication='CommunicationEdit',environment='EnvironmentEdit',
            meaning_identity='ParticipationEdit',security_risk='ContinuityEdit')
        contracts = importlib.import_module('poliscope_engine.contracts.'+domain)
        card = module.interview(node,scope_id='local',**args)
        edit = getattr(contracts,names[domain])(baseline_digest=card.baseline_digest,
            scope_id='local',option_id=card.alternatives[1].definition.id)
        preview = module.preview(node,edit=edit,**args)
        updated = preview.report.evaluation.request.model_dump(mode='json')
        data['request'][domain] = updated
        if 'work' in updated: set_work(data,updated['work'])
        if 'administration' in updated: set_work(data,updated['administration'])
    assert card.selected_option_id is None and len(card.alternatives) == 2
    assert preview.candidate_digest != card.baseline_digest
    assert request.model_dump(mode='json') == setup(before)[0].model_dump(mode='json')
    candidate = run(data)
    assert candidate['baseline_digest'] != run(before)['baseline_digest']
    assert candidate['evidence_status'] == 'hypothetical'


def test_actual_database_reopen_views_share_context_quantities_and_provenance(tmp_path):
    from poliscope_engine.storage import Store
    from poliscope_engine.revisions import Revisions
    from poliscope_engine.contracts.revisions import CreateRequest
    from poliscope_engine import overview, matrix, atlas
    from static_system_fixture import trusted
    _,ctx,registry,inputs = trusted()
    with Store(tmp_path) as store:
        writer = Revisions(store,registry=registry)
        context = writer.create(CreateRequest(revision_contract=1,data_store_id=writer.data_store_id,
            civilization_id='civ',branch_id='main',operation_id='whole-system:create',
            name='Synthetic all-domain education',inputs=inputs)).context
        retained = writer.evidence(context).model_dump_json()
    with Store(tmp_path) as store:
        reader = Revisions(store,registry=None)
        assert reader.evidence(context).model_dump_json() == retained
        selected = dict(context=context,scope_id='local')
        account_rows=[]; cursor=None
        while True:
            result = overview.page(reader, selected | dict(collection='accounts',item_id=None,
                cursor=cursor,all_scopes=True))
            assert result.query.context == context
            account_rows.extend(result.items)
            if result.next_cursor is None: break
            cursor=result.next_cursor
        actual={row.id:row.result.closing for row in account_rows}
        assert actual['time:a']=='0' and actual['time:b']=='0' and actual['supplies']=='0'
        assert actual['school:slots']=='0' and actual['channel']=='1' and actual['depot']=='0'
        rows=[];cursor=None
        while True:
            result=matrix.page(reader,selected | dict(axis='domain',detail_cursor=cursor))
            assert result.query.context == context
            rows.extend(result.relationships)
            if result.detail_next_cursor is None: break
            cursor=result.detail_next_cursor
        numeric=[r for r in rows if r.magnitude is not None]
        assert numeric and all(r.provenance=='retained_execution' for r in numeric)
        assert sum(Fraction(r.magnitude.value) for r in numeric if r.row.id=='node:account/time:a')==12
        assert all(r.magnitude.unit_id=='hours' for r in numeric if r.row.id=='node:account/time:a')
        # The atlas reads the same retained revision while leaving unmapped
        # source alternatives explicitly unanswered and unactivated.
        result=atlas.page(reader,selected)
        assert result.query.context==context and result.items
        assert all(e.selected_id is None for e in result.items)
        assert reader.evidence(context).model_dump_json()==retained


@pytest.mark.parametrize('scenario', [
    'E2E-003.b all-domain finite production access and independent shortages',
    'E2E-004.b all-domain canonical overlap and unresolved authority conflicts',
])
def test_offline_gate(scenario):
    data=fixture()
    if scenario.startswith('E2E-003.b'):
        result=run(data)
        from poliscope_engine.accounts import AccountBook
        from poliscope_engine.contracts.accounts import AccountBatch
        _,ctx=setup(data)
        accounts=AccountBook(AccountBatch.model_validate(result['candidate_batch']),ctx['units']).evaluate()
        assert {a.account_id:a.closing for a in accounts.accounts}['supplies']=='0'
        assert {c.claim_id:c.unmet for c in accounts.claims}['patient']=='2'
        assert result['local_readiness']['health']['clinic']=='blocked'
    else:
        from test_policies import binding
        data['request']['knowledge_culture']['bindings'].append(binding('b',scope_id='region',
            authority_id='regional-authority').model_dump(mode='json'))
        first=run(data)
        data['request']['knowledge_culture']['bindings'].reverse()
        second=run(data)
        assert first['evaluations']['knowledge_culture']['results'][0]['findings']==['institutional_conflict']
        assert first['integrated_readiness']==second['integrated_readiness']
        assert first['candidate_batch'] is None
        assert first['evaluations']['social_organization']['population']['value']=='10'


@pytest.mark.parametrize('tamper', ['request','world','snapshot','versions'])
def test_bound_conformance_rejects_stale_context_and_forged_snapshot(tamper):
    from poliscope_engine.domains.static_host import run_bound_case
    from poliscope_engine.domains.conformance import ConformanceCase
    from poliscope_engine.domains import ConformanceError
    from poliscope_engine.contracts.revisions import RevisionInputs
    from static_system_fixture import trusted
    request,ctx,registry,inputs=trusted()
    raw=inputs.model_dump(mode='json')
    if tamper=='request':
        request=request.model_copy(update={'source_refs':['changed:provenance']})
    elif tamper=='world': raw['entities'][0]['label']='Changed world'
    elif tamper=='snapshot': raw['design']['execution']['batch']['accounts'][0]['opening']='999'
    else: raw['versions']['catalog_id']='foreign:catalog'
    case=ConformanceCase(RevisionInputs.model_validate(raw),'incomplete',())
    with pytest.raises(ConformanceError):
        run_bound_case(case,request=request,units=ctx['units'],mechanisms=ctx['mechanisms'],reviews=registry.reviews)


def test_host_rejects_forged_upstream_evidence_and_requires_explicit_reviews():
    from poliscope_engine.domains.static_host import host_registry, incoming, context_digest
    from poliscope_engine.contracts.world import LabelValue
    from static_system_fixture import trusted
    request,ctx,registry,inputs=trusted()
    domain=next(d for d in DOMAINS if incoming(d))
    callback=next(i.callback for i in registry.implementations if i.id=='authored:system/'+domain+'/implementation')
    values={'system:context':LabelValue(kind='label',value=context_digest(request,**ctx))}
    values.update({'system:from/'+d:LabelValue(kind='label',value='forged') for d in incoming(domain)})
    with pytest.raises(AccountError,match='stale_static_system_evidence'):
        callback('system:evidence',values)
    no_reviews=host_registry(request,**ctx,reviews=[])
    from poliscope_engine.mechanisms import MechanismError
    with pytest.raises(MechanismError,match='review_required'):
        no_reviews.activate('authored:system/'+domain,'v1',phase='static',world=ctx['graph'].registry,
            entity_id='local-authority',scope_id='local')


def test_exact_balance_oracle_prior_commitment_and_posting_identity_provenance():
    data=fixture(); work=data['request']['economy']
    work['batch']['postings'].append(dict(id='prior-care',kind='use',source_id='time:a',
        destination_id=None,amount='1',reservation_id=None,claim_id='care',
        mechanism_ref='synthetic:prior-care',source_refs=['synthetic:whole-system']))
    work['batch']['reservations'].append(dict(id='learning-hold',account_id='time:a',claim_id='learning',amount='2'))
    set_work(data,work)
    result=run(data);batch=result['candidate_batch']
    assert result['evaluations']['social_organization']['results'][0]['actual_before']=='1'
    assert result['evaluations']['social_organization']['results'][0]['actual']=='3'
    assert sum(p['original_id']=='prior-care' for p in result['posting_origins'])==1
    assert batch['reservations']==[dict(id='learning-hold',account_id='time:a',claim_id='learning',amount='2')]
    assert len({p['id'] for p in batch['postings']})==len(batch['postings'])
    original_ids={p['id']:p['original_id'] for p in result['posting_origins']}
    assert set(original_ids)=={p['id'] for p in batch['postings']}
    balances={a['id']:Fraction(a['opening']) for a in batch['accounts']}
    for posting in batch['postings']:
        if posting['source_id']: balances[posting['source_id']]-=Fraction(posting['amount'])
        if posting['destination_id']: balances[posting['destination_id']]+=Fraction(posting['amount'])
    from poliscope_engine.accounts import AccountBook
    from poliscope_engine.contracts.accounts import AccountBatch
    _,ctx=setup(data)
    assert balances=={a.account_id:Fraction(a.closing) for a in AccountBook(AccountBatch.model_validate(batch),ctx['units']).evaluate().accounts}
    assert result==run(data)


def test_disjoint_account_names_cannot_hide_a_second_budget_for_the_same_people():
    data=fixture();req=data['request']
    for d in DOMAINS:
        if d not in ('economy','social_organization'):req[d]=None
    req['requirements']=[dict(id='care-work',source='economy',target='social_organization',
        source_result_id='materials',target_result_id='care',obligation_ref='synthetic:care-work',
        shared_references=[dict(entity_id='shared:cohort',entity_kind='population_cohort')],source_refs=['synthetic:whole-system'])]
    work=req['social_organization']['work']
    for account in work['batch']['accounts']:
        account['id']='copy/'+account['id']
        data['world']['entities'].append(dict(id=account['id'],entity_kind='account',label=account['id'],
            provenance=data['world']['entities'][0]['provenance']))
    for claim in work['batch']['claims']:claim['account_id']='copy/'+claim['account_id']
    for holder in work['holders']:holder['account_id']='copy/'+holder['account_id']
    with pytest.raises(AccountError,match='static_system_duplicate_time'):run(data)
