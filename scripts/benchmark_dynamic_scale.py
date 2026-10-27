"""Execute every requested synthetic day; preserve explicit quota/failure evidence."""
import argparse
import hashlib
from fractions import Fraction
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.scale_dynamic_fixture import fixture, oracle, VERSION
from scripts.benchmark_scale import machine
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from poliscope_engine.contracts.revisions import CreateRequest, PreviewRequest, ApplyRequest
from poliscope_engine.contracts.boundaries import CreateExperiment
from poliscope_engine.simulation import TransitionReducer
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.work_limits import WorkLimits, WorkStopped, limited


def run(root, *, name='classroom-v1', days=3, seconds=30, counts=None):
    manifest=json.loads((ROOT/'docs/roadmap/execution/benchmarks.json').read_text())
    counts=counts or manifest['fixtures'][name]
    host,catalog,inputs,plan,expected=fixture(counts)
    with Store(root) as store:
        revisions=Revisions(store,registry=host)
        opened=revisions.create(CreateRequest(revision_contract=1,data_store_id=revisions.data_store_id,
            civilization_id='scale:civ',branch_id='main',name='Synthetic dynamic scale',operation_id='create',inputs=inputs))
        revised=inputs.model_dump(mode='json')
        for binding in revised['design']['policies']:binding['value']['value']='90'
        approval=PreviewRequest(revision_contract=1,context=opened.context,
            changes=[dict(kind='replace_inputs',inputs=revised)],
            decision=dict(alternatives=[],selected_id=None,rationale_ref=None))
        candidate=revisions.preview(approval)
        approved=revisions.apply(ApplyRequest(revision_contract=1,operation_id='approve-policies',
            preview=approval,candidate_digest=candidate.candidate_digest))
        adoptions=[]
        for j in range(2):
            old=inputs.design.policies[j];replacement=revisions.read(approved.context).inputs.design.policies[j]
            delta=dict(binding_id=old.id,scope_id=old.scope_id,expected_digest=digest(old),replacement=replacement)
            for day in ([7,8] if j==0 else [7]):
                adoptions.append(dict(id=f'scale:adoption:{day}:{j}',effective_day=day,order=j,
                    origin='player_approved',base_revision=opened.context,source_revision=approved.context,
                    deltas=[delta],preconditions=[],transition='binding_only',source_refs=[]))
        reducer=TransitionReducer(revisions,catalog=catalog)
        scope=inputs.scopes[0].id
        off=dict(kind='label',value='off');on=dict(kind='label',value='on')
        events=[]
        for day,value,old in [(100,on,off),(110,off,on)]:
            events.append(dict(id=f'scale:event:{day}',effective_day=day,order=0,origin='player_authored',
                changes=[dict(condition_id='scale:disruption',scope_id=scope,expected_digest=digest(old),value=value)],source_refs=[]))
        request=CreateExperiment.model_validate(dict(boundary_contract=1,
            context=dict(data_store_id=revisions.data_store_id,civilization_id='scale:civ',experiment_id='scale:run'),
            operation_id='open',plan=dict(contract_version=1,calendar={},opening_revision=opened.context,opening_day=0,
                schedules=[dict(instance_id=i.id,interval_days=1,first_day=1) for i in plan.instances],events=events,adoptions=adoptions),
            conditions=[dict(condition_id='scale:disruption',scope_id=scope,value=off)],transition_plan=plan))
        current=reducer.store.create(request)
        raw=[];status='complete';start=time.perf_counter_ns()
        try:
            with limited(WorkLimits(seconds=seconds)):
                for day in range(1,days+1):
                    tick=time.perf_counter_ns()
                    current=reducer.advance_boundary(current,day,operation_id=f'day:{day}')
                    saved=reducer.store.read(current.context)
                    actual={v.id:Fraction(v.value.value) for v in saved.state.inputs.values if v.id.startswith('run:') and v.value.kind=='quantity'}
                    if day==7:assert [a.status for a in saved.record.changes.adoptions]==['applied','applied']
                    if day==8:assert [a.status for a in saved.record.changes.adoptions]==['conflict']
                    if day in [100,110]:assert [e.status for e in saved.record.changes.events]==['applied']
                    expected_amounts,accounts=oracle(day)
                    chain_outputs={o.node[1]:o.value.value for o in saved.evidence.evaluation.observations
                        if o.node[0]=='output' and o.node[-1]=='scale:out' and o.node[1].startswith('scale:chain:')}
                    for index in range(counts['decision_instances']-4):
                        expected_output=(expected_amounts[0] if index % counts['scopes']==0 else 0)+index//counts['scopes']+1
                        assert chain_outputs[f'scale:chain:{index:05}']==str(expected_output)
                    assert [actual['run:processed-'+chr(97+i)] for i in range(12)]==expected_amounts
                    assert actual['run:balance:material']==accounts['material']
                    assert actual['run:balance:labor']==accounts['labor']
                    assert actual['run:balance:product']==Fraction(accounts['product'],10)
                    assert actual['run:balance:residual']==Fraction(accounts['residual'],10)
                    raw.append((time.perf_counter_ns()-tick)/1e6)
                    print('Confirmed day',day,flush=True)
                    # Do not spend minutes re-establishing a known throughput
                    # failure. Correctness still checks every executed boundary.
                    # Compact calendar fixtures have their own conformance route.
                    if (days==365 and day==3 and counts==manifest['fixtures'].get(name)
                            and (time.perf_counter_ns()-start)/1e6/3*365 >
                            manifest['budgets']['small_365_day_run_ms']):
                        status='annual_throughput_gate_failed'
                        break
        except WorkStopped as error:
            status=str(error)
        elapsed=(time.perf_counter_ns()-start)/1e6
        receipt=dict(package='WP-051',fixture=VERSION,name=name,counts=counts,machine=machine(),requested_days=days,
            confirmed_days=current.day,raw_boundary_ms=raw,elapsed_ms=elapsed,status=status,
            boundary_digest=current.boundary_digest,all_confirmed_values_match_integer_oracle=True,
            performance_claim='full-year measurement' if days==365 and current.day==365 else 'short diagnostic; no annual budget claim',
            projected_year_ms=(elapsed/current.day*365 if current.day else None),
            release_issue='PERF-DYNAMIC-001' if name in manifest['fixtures'] and
                (days!=365 or status!='complete' or elapsed>30000) else None,
            native_validation='owner-run; no native claim')
        receipt['candidate']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        receipt['python']=sys.version
        receipt['input_digest']=digest(inputs)
        receipt['transition_plan_digest']=digest(plan)
        paths=[*sorted((ROOT/'engine/poliscope_engine').rglob('*.py')),
            ROOT/'scripts/benchmark_dynamic_scale.py',ROOT/'scripts/scale_dynamic_fixture.py',
            ROOT/'scripts/coupled_scale_fixture.py',ROOT/'scripts/scale_fixtures.py',
            ROOT/'tests/engine/transition_fixture.py',ROOT/'tests/engine/headless_fixture.py',
            ROOT/'docs/roadmap/execution/benchmarks.json',ROOT/'pyproject.toml',ROOT/'uv.lock']
        receipt['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--seconds',type=int,default=30);parser.add_argument('--days',type=int,default=3)
    args=parser.parse_args()
    if not 1<=args.days<=365 or not 1<=args.seconds<=3600:
        parser.error('days must be 1..365 and seconds 1..3600')
    with tempfile.TemporaryDirectory(prefix='poliscope-dynamic-') as directory:r=run(Path(directory),days=args.days,seconds=args.seconds)
    args.output.write_text(json.dumps(r,indent=2)+'\n');return 1 if r['release_issue'] else 0

if __name__=='__main__':raise SystemExit(main())
