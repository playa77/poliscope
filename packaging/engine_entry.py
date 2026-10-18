import sys

if '--history-read' in sys.argv[1:]:
    from poliscope_engine.history import main
    sys.argv.remove('--history-read')
else:
    from poliscope_engine.__main__ import main

if __name__ == '__main__':
    raise SystemExit(main())
