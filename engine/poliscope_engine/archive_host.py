"""Main-granted file operations. No renderer paths, archive bytes or SQL in IPC."""
import argparse
import json
from pathlib import Path
import sys
from poliscope_engine.archives import (export_archive,import_archive,list_archives,read_item,display_item)
from poliscope_engine.contracts.archives import ArchiveRequest,ArchiveReply
from poliscope_engine.storage import Store


def request(directory, query, selected_file=None):
    with Store(directory) as store:
        if query.action=='export':
            from poliscope_engine.revisions import Revisions
            # Export reads immutable data without needing the original executable model.
            service=Revisions(store,registry=None)
            result=export_archive(service,selected_file,query.options,archive_id=query.archive_id)
            return ArchiveReply(status='complete',summaries=[result])
        if query.action=='import':
            result=import_archive(store,selected_file)
            return ArchiveReply(status='complete',summaries=[result])
        if query.action=='list':
            return ArchiveReply(status='complete',summaries=list_archives(store))
        item,next_offset=read_item(store,query.archive_id,query.offset)
        heading,rows,next_detail=display_item(item,query.detail_offset)
        return ArchiveReply(status='complete',summaries=[],heading=heading,rows=rows,
            next_offset=next_offset,next_detail_offset=next_detail)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',required=True,type=Path)
    parser.add_argument('--selected-file',type=Path)
    args=parser.parse_args()
    try:
        raw=sys.stdin.buffer.readline(16385)
        if not raw.endswith(b'\n') or len(raw)>16384 or sys.stdin.buffer.read(1):raise ValueError()
        query=ArchiveRequest.model_validate_json(raw)
        if not args.directory.is_absolute() or (query.action in ('import','export')) != (args.selected_file is not None):raise ValueError()
        reply=request(args.directory,query,args.selected_file)
        raw=reply.model_dump_json().encode()+b'\n'
        if len(raw)>1048576:raise ValueError()
        sys.stdout.buffer.write(raw)
        return 0
    except Exception:
        return 1

if __name__=='__main__':raise SystemExit(main())
