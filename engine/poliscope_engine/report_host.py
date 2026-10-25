"""Main-owned save grant and bounded receipt, independent of numerical runtime."""
import argparse
from pathlib import Path
import sys
from poliscope_engine.contracts.reports import ReportRequest
from poliscope_engine.reports import export_report
from poliscope_engine.revisions import Revisions
from poliscope_engine.storage import Store


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',required=True,type=Path)
    parser.add_argument('--selected-file',required=True,type=Path)
    args=parser.parse_args()
    try:
        raw=sys.stdin.buffer.readline(16385)
        if not raw.endswith(b'\n') or len(raw)>16384 or sys.stdin.buffer.read(1):
            raise ValueError('invalid_report_frame')
        query=ReportRequest.model_validate_json(raw)
        if not args.directory.is_absolute() or not args.selected_file.is_absolute():
            raise ValueError('invalid_report_grant')
        with Store(args.directory) as store:
            reply=export_report(Revisions(store,registry=None),args.selected_file,query)
        sys.stdout.buffer.write(reply.model_dump_json().encode()+b'\n')
        return 0
    except Exception:
        return 1

if __name__=='__main__':
    raise SystemExit(main())
