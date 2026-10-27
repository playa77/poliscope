"""Production scaled Preview/Apply/pages/context/archive evidence; no native claim."""
import argparse
from datetime import datetime, timezone
import platform
import subprocess
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.coupled_scale_fixture import fixture, verify, VERSION
from scripts.benchmark_scale import measure, machine, resource
from poliscope_engine.contracts.revisions import CreateRequest, PreviewRequest, ApplyRequest
from poliscope_engine.contracts.world import WorldInspectParams
from poliscope_engine.revisions import Revisions
from poliscope_engine.storage import Store
from poliscope_engine.workspace import page as workspace_page
from poliscope_engine.evaluation.identity import digest
from poliscope_engine import grounding, matrix, atlas
from poliscope_engine.archives import export_archive, validate_archive


def stream(model):
    payload=model.model_dump_json().encode()
    return (payload[i:i+131072] for i in range(0,len(payload),131072)),hashlib.sha256(payload).hexdigest()


def collect(root, *, samples=30, names=('classroom-v1','exploratory-v1')):
    manifest=json.loads((ROOT/'docs/roadmap/execution/benchmarks.json').read_text())
    receipt=dict(package='WP-051',fixture=VERSION,machine=machine(),samples=samples,
        scope='Linux cloud production service calls; excludes Electron and native owner-run validation',workloads={},issues=[],
        observed_at=datetime.now(timezone.utc).isoformat(),
        candidate=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        tracked_diff_sha256=hashlib.sha256(subprocess.check_output(['git','diff','HEAD'],cwd=ROOT)).hexdigest(),
        python=platform.python_version(),node=subprocess.check_output(['node','--version'],text=True).strip(),
        electron=json.loads((ROOT/'package.json').read_text())['devDependencies']['electron'],
        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [
            *sorted((ROOT/'engine/poliscope_engine').rglob('*.py')), ROOT/'scripts/coupled_scale_fixture.py',
            ROOT/'scripts/scale_fixtures.py',ROOT/'scripts/benchmark_coupled_scale.py',ROOT/'tests/engine/headless_fixture.py',
            ROOT/'contracts/mechanism-fixtures.json',ROOT/'docs/roadmap/execution/benchmarks.json']})
    for name in names:
        print('Production workload '+name,flush=True)
        host,inputs,expected=fixture(manifest['fixtures'][name])
        with Store(root/name) as store:
            service=Revisions(store,registry=host)
            create=CreateRequest(revision_contract=1,data_store_id=service.data_store_id,civilization_id='scale:civ',
                branch_id='main',name='Synthetic coupled scale',operation_id='create',inputs=inputs)
            parts,checksum=stream(create)
            state=service.create_chunks(parts,expected_sha256=checksum)
            verify(service.evidence(state.context).evaluation,expected)
            changed_value=inputs.values[0].model_copy(update={'value':inputs.values[0].value.model_copy(update={'value':'101'})})
            _,_,changed_expected=fixture(manifest['fixtures'][name],seed=101)
            request=PreviewRequest(revision_contract=1,context=state.context,
                changes=[dict(kind='set_values',writer_id='fixture',partition='conditions',values=[changed_value])],
                decision=dict(alternatives=[],selected_id=None,rationale_ref=None))
            cold,warm=[],[]
            identity=None
            for _ in range(samples):
                service.clear_caches()
                start=time.perf_counter_ns();candidate=service.preview(request);cold.append((time.perf_counter_ns()-start)/1e6)
                start=time.perf_counter_ns();cached=service.preview(request);warm.append((time.perf_counter_ns()-start)/1e6)
                assert candidate==cached and candidate.differences
                if identity is None: identity=candidate.candidate_digest
                assert candidate.candidate_digest==identity
            print('Measured previews '+name,flush=True)
            accepted=service.apply(ApplyRequest(revision_contract=1,operation_id='apply',preview=request,candidate_digest=identity))
            verify(service.evidence(accepted.context).evaluation,changed_expected)
            old=service.evidence(state.context)
            service.clear_caches()
            with store.transaction():store.clear_caches()
            assert service.evidence(state.context)==old
            query=WorldInspectParams(world_schema=1,context=accepted.context,collection='relationships',cursor=None,limit=100)
            pages,page=measure(lambda:service.inspect(query),samples)
            total,cursor=0,None
            while True:
                part=service.inspect(query.model_copy(update={'cursor':cursor}));total+=len(part.page.items)
                assert len(part.model_dump_json().encode())<1048576
                cursor=part.page.next_cursor
                if cursor is None:break
            assert total==len(inputs.relationships)
            print('Verified complete world pages '+name,flush=True)
            scope=inputs.scopes[0].id
            public_t,public_page=measure(lambda:workspace_page(service,dict(context=accepted.context,scope_id=scope,collection='relationships',cursor=None)),samples)
            context_t,context=measure(lambda:grounding.assemble(service,dict(context=accepted.context,
                selection=dict(scope_id=scope,task='Explain synthetic limits',collections=['facts','accounts','traces'],tools=True))),samples)
            atlas_t,catalog=measure(lambda:atlas.page(service,dict(context=accepted.context,scope_id=scope)),samples)
            matrix_t,sparse=measure(lambda:matrix.page(service,dict(context=accepted.context,scope_id=scope,axis='domain')),samples)
            assert len(context.model_dump_json().encode())<1048576 and len(sparse.model_dump_json().encode())<1048576
            print('Measured public queries '+name,flush=True)
            start=time.perf_counter_ns();archive=root/(name+'.zip');exported=export_archive(service,archive);validate_archive(archive)
            archive_t=(time.perf_counter_ns()-start)/1e6
            from scripts.benchmark_scale import summarize
            result=dict(counts=manifest['fixtures'][name],input_bytes=len(create.model_dump_json().encode()),
                cold_preview=summarize(cold),warm_preview=summarize(warm),world_page=pages,workspace_page=public_t,workspace_page_bytes=len(public_page.model_dump_json().encode()),
                context=context_t,matrix=matrix_t,atlas=atlas_t,atlas_catalog_scope='bundled catalog over scaled immutable revision',matrix_relationships=sparse.relationship_total,
                candidate_digest=identity,physical_digest=old.evaluation.identities.output_digest,
                world_page_bytes=len(page.model_dump_json().encode()),context_bytes=len(context.model_dump_json().encode()),
                matrix_bytes=len(sparse.model_dump_json().encode()),archive=dict(samples=1,elapsed_ms=archive_t,
                    revisions=exported.revisions,bytes=archive.stat().st_size),cache_clear_preserves_evidence=True)
            receipt['workloads'][name]=result
            for key,budget in [('cold_preview',1000 if name=='classroom-v1' else 5000),('warm_preview',1000 if name=='classroom-v1' else 5000),('world_page',300),('workspace_page',300),('context',300),('matrix',300),('atlas',300)]:
                if result[key]['p95_ms']>budget:receipt['issues'].append(dict(id='PERF-'+name+'-'+key,observed_ms=result[key]['p95_ms'],budget_ms=budget))
    receipt['status']='release-blocked' if receipt['issues'] else 'available-service-budgets-passed'
    receipt['python_peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024 if resource is not None else None
    if receipt['python_peak_rss_bytes'] is not None and receipt['python_peak_rss_bytes']>2147483648:
        receipt['issues'].append(dict(id='PERF-MEMORY-001',observed_python_bytes=receipt['python_peak_rss_bytes'],combined_budget_bytes=2147483648))
        receipt['status']='release-blocked'
    receipt['memory_scope']='Single Python diagnostic process high-water RSS; native combined main/renderer/engine testing is owner-run.'
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--samples',type=int,default=30)
    args=parser.parse_args()
    if not 30<=args.samples<=1000:parser.error('at least 30 samples required')
    with tempfile.TemporaryDirectory(prefix='poliscope-coupled-') as directory:receipt=collect(Path(directory),samples=args.samples)
    args.output.write_text(json.dumps(receipt,indent=2)+'\n');return 1 if receipt['issues'] else 0

if __name__=='__main__':raise SystemExit(main())
