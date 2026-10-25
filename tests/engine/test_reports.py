"""Independent literal CSV and escaping checks over actual retained services."""
import csv
import io
import json
from pathlib import Path
import pytest
from poliscope_engine import reports
from poliscope_engine.reports import export_report, block, csv_line, COLUMNS
from poliscope_engine.contracts.reports import ReportRequest
from poliscope_engine.contracts.archives import ArchiveOptions
from poliscope_engine.archives import export_archive, import_archive, ArchiveError
from poliscope_engine.revisions import Revisions
from poliscope_engine.storage import Store
from poliscope_engine.evaluation.identity import serialized
from test_workbench import blank, commit, edit, note
from headless_fixture import registry, inputs, create
from test_experiments import setup, advance


def request(format='csv',**kwargs):
    return ReportRequest(format=format,**kwargs)


def decode(path):
    with path.open(newline='') as stream:
        rows=list(csv.DictReader(stream))
    numeric={'report_schema','world_schema','sequence','day','tick','value'}
    return [{k:(v[1:] if v and k not in numeric else v) for k,v in row.items()} for row in rows]


def test_exact_python_measurements_and_unavailable_values(tmp_path):
    with Store(tmp_path/'store') as store:
        service=Revisions(store,registry=registry())
        context=create(service,inputs()).context
        before=store._connection.total_changes
        saved=service.evidence(context)
        path=tmp_path/'measurements.csv'
        receipt=export_report(service,path,request())
        rows=decode(path)
        observations={o.indicator_id:o for o in saved.report.measurements}
        actual={r['indicator_id']:r for r in rows if r['record_type']=='measurement'}
        assert actual.keys()==observations.keys()
        for identity, observation in observations.items():
            row=actual[identity]
            assert row['coverage']==observation.status
            assert row['scope_id']==observation.scope_id
            assert row['calendar_id']==observation.effective_time.calendar_id
            assert row['tick']==str(observation.effective_time.tick)
            if observation.value.kind=='quantity':
                assert row['value']==observation.value.value
                assert row['unit_id']==observation.value.unit_id
            else:
                assert row['value']==''
            assert row['world_schema']=='1'
            assert row['model_id']==service.read(context).inputs.versions.model_id
            assert json.loads(row['trace_refs'])==observation.trace_refs
        # Literal expectation from the synthetic allocation, independently derived:
        # 100 shared units minus B's reservation of 40 => A receives 60 under priority.
        assert {o.value.value for o in observations.values() if o.value.kind=='quantity'} >= {'60'}
        assert receipt.bytes_written==path.stat().st_size
        assert receipt.rows==len(rows)
        assert store._connection.total_changes==before
        assert service.branch(context).context==context


@pytest.mark.parametrize('text',['=HYPERLINK("https://sink.test")','+SUM(1,2)','-2+3','@SUM(1,2)',
    '\t=evil','\r\n=evil',"'original",'commas, "quotes"\r\nline','<img src="https://sink.test">','```\n</code>\n```','λ🙂'])
def test_csv_reversible_text_and_markdown_fences(text):
    row=next(csv.DictReader(io.StringIO(','.join(COLUMNS)+'\r\n'+csv_line(dict(reason=text,value='-12.500')))))
    assert row['reason'].startswith("'")
    assert row['reason'][1:]==text
    assert row['value']=='-12.500'
    markdown=block(text)
    lines=markdown.split('\n')
    fence=lines[0][:-4]
    assert len(fence)>=3
    assert fence not in text
    assert markdown==f'{fence}text\n{text}\n{fence}\n\n'


def test_history_privacy_notes_subtypes_and_keys(tmp_path):
    from poliscope_engine.workspace import registry as workspace_registry
    with Store(tmp_path/'store') as store:
        service=Revisions(store,registry=workspace_registry())
        context=blank(service)
        _,first=commit(service,edit(context,note('OLD_REPORT_CANARY',kind='expectation')),'old')
        ref=service.read(first.state.context).inputs.notes[0]
        _,second=commit(service,edit(first.state.context,note('NEW_REPORT_CANARY',ref.id,'observation')),'new')
        (tmp_path/'store'/'keys.json').write_text('KEY_CANARY_NEVER_READ')
        for format in ('markdown','csv'):
            path=tmp_path/f'default.{format}'
            export_report(service,path,request(format))
            text=path.read_text()
            for secret in ('OLD_REPORT_CANARY','NEW_REPORT_CANARY','KEY_CANARY_NEVER_READ',ref.id):
                assert secret not in text
        path=tmp_path/'selected.md'
        export_report(service,path,request('markdown',options=ArchiveOptions(include_private_notes=True)))
        text=path.read_text()
        assert 'OLD_REPORT_CANARY' in text and 'NEW_REPORT_CANARY' in text
        assert '"note_kind":"expectation"' in text and '"note_kind":"observation"' in text
        assert 'KEY_CANARY_NEVER_READ' not in text
        assert 'player hypothesis' in text and 'not calculated findings' in text
        assert 'no AI explanation' in text


def test_csv_time_series_and_declared_distributions_without_resampling(tmp_path,monkeypatch):
    import test_experiments
    from poliscope_engine.contracts.revisions import RevisionInputs
    original=test_experiments.fixture
    def measured_fixture():
        mechanisms,catalog,initial,plan=original()
        raw=initial.model_dump(mode='json')
        raw['measurements']=[dict(id='static-output',version='v1',name='Synthetic static zero',procedure='identity',
            inputs=[dict(node=['output','a','synthetic:out'],scope_id='local')],unit_id='kg',scope_id='local',
            aggregation='same_scope',time_basis_id=None,denominator_scope_id=None,coverage='known',
            interpretation='Synthetic static zero; transition state is separate',source_refs=[],assumption_refs=[],diagnostics=[])]
        return mechanisms,catalog,RevisionInputs.model_validate(raw),plan
    monkeypatch.setattr(test_experiments,'fixture',measured_fixture)
    with Store(tmp_path/'store') as store:
        experiments,opening,_=setup(store)
        experiments.advance(advance(opening))
        path=tmp_path/'series.csv'
        export_report(experiments.reducer.revisions,path,request())
        rows=decode(path)
        series=[r for r in rows if r['record_type']=='time_series_state']
        assert {r['day'] for r in series}=={'0','1','2','3','4'}
        assert {r['sequence'] for r in series}=={'0','1','2','3','4'}
        calculated=[r for r in rows if r['record_type']=='time_series']
        assert len(calculated)==6  # one original opening plus five controlled boundaries
        assert {r['value'] for r in calculated}=={'0'}
        assert {r['day'] for r in calculated}=={'0','1','2','3','4'}
        assert next(r['value'] for r in series if r['day']=='1' and r['value_id']=='processed-a')=='8'
        assert next(r['value'] for r in series if r['day']=='1' and r['value_id']=='processed-b')=='2'


def test_explicit_distribution_export(tmp_path):
    from test_stochastic import setup_random
    with Store(tmp_path/'store') as store:
        reducer, _, _ = setup_random(store)
        path=tmp_path/'laws.csv'
        export_report(reducer.revisions,path,request())
        rows=decode(path)
        laws=[r for r in rows if r['record_type']=='distribution']
        assert laws
        assert all(r['value']=='' and r['coverage']=='declared' for r in laws)
        assert all(json.loads(r['distribution_json'])['kind']=='bernoulli' for r in laws)
        assert all(json.loads(r['distribution_json'])['numerator']==1 for r in laws)
        assert all(json.loads(r['distribution_json'])['denominator']==3 for r in laws)
        assert all(r['dependence'] in ('declared_independent','shared_realization') for r in laws)
        assert all('not a measured outcome' in r['reason'] for r in laws)


def test_imported_historical_reports_no_runtime_and_reduced_evidence(tmp_path):
    with Store(tmp_path/'source') as store:
        service=Revisions(store,registry=registry())
        create(service,inputs())
        export_archive(service,tmp_path/'history.zip')
    with Store(tmp_path/'target') as store:
        summary=import_archive(store,tmp_path/'history.zip')
        service=Revisions(store,registry=None)
        path=tmp_path/'historical.csv'
        export_report(service,path,request(archive_id=summary.id))
        assert any(r['value']=='60' for r in decode(path))
        path=tmp_path/'reduced.csv'
        export_report(service,path,request(archive_id=summary.id,options=ArchiveOptions(evidence='reduced')))
        rows=decode(path)
        unavailable=[r for r in rows if r['record_type']=='evidence_unavailable']
        assert unavailable
        assert all(r['value']=='' and r['coverage']=='unavailable' for r in unavailable)
        assert not any(r['record_type']=='measurement' for r in rows)
        assert service.catalogue()==[]


@pytest.mark.parametrize('failure',['cancel','budget','write','link'])
def test_failure_cleanup_no_partial_or_history_change(tmp_path,monkeypatch,failure):
    with Store(tmp_path/'store') as store:
        service=Revisions(store,registry=registry())
        context=create(service,inputs()).context
        before=store._connection.total_changes
        path=tmp_path/'result.csv'
        cancel=None
        if failure=='cancel':
            # Archive work calls this too: cancel only after report staging exists.
            cancel=lambda:any(tmp_path.glob('.poliscope-report-*'))
        if failure=='budget':monkeypatch.setattr(reports,'MAX_REPORT',1)
        if failure in ('write','link'):
            name='fsync' if failure=='write' else 'link'
            original=getattr(reports.os,name)
            def fail(*args,**kwargs):
                if list(tmp_path.glob('.poliscope-report-*')):
                    raise OSError('synthetic report disk error')
                return original(*args,**kwargs)
            monkeypatch.setattr(reports.os,name,fail)
        with pytest.raises((ArchiveError,OSError)):
            export_report(service,path,request(),cancelled=cancel)
        assert not path.exists()
        assert not list(tmp_path.glob('.poliscope-report-*'))
        assert store._connection.total_changes==before
        assert service.branch(context).context==context


def test_exclusive_target_and_unknown_scope(tmp_path):
    with Store(tmp_path/'store') as store:
        service=Revisions(store,registry=registry())
        create(service,inputs())
        path=tmp_path/'existing.csv';path.write_text('preserve')
        with pytest.raises(ArchiveError,match='new_absolute'):
            export_report(service,path,request())
        assert path.read_text()=='preserve'
        with pytest.raises(ArchiveError,match='unknown_report_scope'):
            export_report(service,tmp_path/'bad.csv',request(scope_id='absent'))
        assert not (tmp_path/'bad.csv').exists()


@pytest.mark.parametrize('incompatible',[False,True])
def test_parent_comparison_matches_actual_comparability(tmp_path,incompatible):
    from headless_fixture import preview, apply
    from poliscope_engine.contracts.revisions import RevisionInputs
    with Store(tmp_path/'store') as store:
        service=Revisions(store,registry=registry())
        opening=create(service,inputs())
        raw=inputs().model_dump(mode='json')
        raw['design']['execution']['allocations'][0]['claim_order']=['b','a']
        if incompatible:raw['measurements'][0]['version']='other-definition'
        changed=RevisionInputs.model_validate(raw)
        service.apply(apply(service,preview(opening.context,changed)))
        path=tmp_path/'comparison.csv'
        export_report(service,path,request())
        rows=[r for r in decode(path) if r['record_type']=='comparison']
        assert len(rows)==1
        row=rows[0]
        assert row['comparison_revision']=='revision:0'
        if incompatible:
            assert row['value']=='' and row['coverage']=='unavailable'
            assert 'Incompatible definition: version' in row['reason']
        else:
            # A's priority reversed: B now uses 80, A receives remaining 20;
            # right-minus-left is 20 - 60 = -40, not a winner ranking.
            assert row['value']=='-40' and row['unit_id']=='kg'
            assert row['coverage']=='known'


def test_missing_measurement_is_explicit_unknown_not_zero(tmp_path):
    from poliscope_engine.contracts.revisions import RevisionInputs
    raw=inputs().model_dump(mode='json')
    raw['measurements'][0]['coverage']='unmodeled'
    with Store(tmp_path/'store') as store:
        service=Revisions(store,registry=registry())
        create(service,RevisionInputs.model_validate(raw))
        path=tmp_path/'missing.csv'
        export_report(service,path,request(scope_id='east'))
        rows=[r for r in decode(path) if r['record_type']=='measurement']
        assert len(rows)==1
        assert rows[0]['coverage']=='unmodeled'
        assert rows[0]['value_kind']=='unknown' and rows[0]['value']==''
        assert rows[0]['unit_id']=='kg'
        assert 'reason' in rows[0] and rows[0]['reason']


def test_host_rejects_bad_grants_and_never_prints_sensitive_errors(tmp_path):
    import subprocess
    import sys
    with Store(tmp_path/'store') as store:
        service=Revisions(store,registry=registry())
        create(service,inputs())
    path=tmp_path/'host.csv'
    command=[sys.executable,'-I','-m','poliscope_engine.report_host','--directory',str(tmp_path/'store'),'--selected-file',str(path)]
    for payload in ('{"format":"csv","path":"SECRET_CANARY"}\n','{"format":"execute"}\n','{"format":"csv"}\nextra'):
        result=subprocess.run(command,input=payload.encode(),capture_output=True)
        assert result.returncode==1
        assert not result.stdout and not result.stderr and not path.exists()
    result=subprocess.run(command,input=b'{"format":"csv"}\n',capture_output=True)
    assert result.returncode==0
    receipt=json.loads(result.stdout)
    assert receipt['format']=='csv' and receipt['status']=='complete'
    assert len(result.stdout)<2048 and path.exists()


def test_versioned_export_fixture():
    fixture=json.loads(Path('tests/fixtures/reports/format-v1.json').read_text())
    assert fixture['report_schema']==1
    for example in fixture['examples']:
        if 'text' in example:
            assert reports.csv_text(example['text'])==example['cell']
        else:
            row=next(csv.DictReader(io.StringIO(','.join(COLUMNS)+'\r\n'+csv_line(dict(value=example['quantity'])))))
            assert row['value']==example['cell']
