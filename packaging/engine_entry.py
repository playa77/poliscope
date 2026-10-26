import sys

if '--spending' in sys.argv[1:]:
    from poliscope_engine.spending_host import main
    sys.argv.remove('--spending')
elif '--recovery' in sys.argv[1:]:
    from poliscope_engine.recovery_host import main
    sys.argv.remove('--recovery')
elif '--report' in sys.argv[1:]:
    from poliscope_engine.report_host import main
    sys.argv.remove('--report')
elif '--archive' in sys.argv[1:]:
    from poliscope_engine.archive_host import main
    sys.argv.remove('--archive')
elif '--workspace' in sys.argv[1:]:
    from poliscope_engine.workspace import main
    sys.argv.remove('--workspace')
elif '--history-read' in sys.argv[1:]:
    from poliscope_engine.history import main
    sys.argv.remove('--history-read')
else:
    from poliscope_engine.__main__ import main

if __name__ == '__main__':
    raise SystemExit(main())
