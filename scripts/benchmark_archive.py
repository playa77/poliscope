"""Measure archive projection over an existing isolated synthetic history store."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from poliscope_engine.archives import export_archive, validate_archive
from poliscope_engine.revisions import Revisions
from poliscope_engine.storage import Store
from scripts.benchmark_scale import machine, resource


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not (args.store / 'poliscope.sqlite3').is_file():
        parser.error('existing isolated synthetic store required')
    metadata = dict(version=1, package='WP-051', workload='semantic-history-archive-v1',
        candidate=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        tracked_diff_sha256=hashlib.sha256(subprocess.check_output(['git', 'diff', 'HEAD'], cwd=ROOT)).hexdigest(),
        command=sys.argv, machine=machine(), python=platform.python_version(),
        source_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in [
            'scripts/benchmark_archive.py', 'engine/poliscope_engine/archives.py']},
        samples=1, memory_scope='single Python process high-water RSS; excludes Electron',
        native_validation='owner-run')
    with Store(args.store) as store:
        service = Revisions(store, registry=None)
        start = time.perf_counter_ns()
        summary = export_archive(service, args.archive)
        export_ms = (time.perf_counter_ns() - start) / 1e6
        start = time.perf_counter_ns()
        _, items = validate_archive(args.archive)
        validate_ms = (time.perf_counter_ns() - start) / 1e6
        metadata.update(status='validated', revisions=summary.revisions, branches=summary.branches,
            entries=len(items), bytes=args.archive.stat().st_size, export_ms=export_ms, validate_ms=validate_ms)
    metadata['peak_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 if resource is not None else None
    args.output.write_text(json.dumps(metadata, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
