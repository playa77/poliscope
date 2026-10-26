"""One bounded, main-owned spending operation; no network or secret inputs."""
import argparse
from pathlib import Path
import sys
from poliscope_engine.contracts.spending import spend_request_adapter
from poliscope_engine.spending import Spending


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', required=True, type=Path)
    args = parser.parse_args()
    ledger = None
    try:
        raw = sys.stdin.buffer.readline(16385)
        if len(raw) > 16384 or not raw.endswith(b'\n') or sys.stdin.buffer.read(1):
            raise ValueError('invalid_spending_frame')
        query = spend_request_adapter.validate_json(raw)
        ledger = Spending(args.database)
        sys.stdout.buffer.write(ledger.request(query).model_dump_json().encode() + b'\n')
        return 0
    except Exception:
        return 1
    finally:
        if ledger:
            ledger.close()

if __name__ == '__main__':
    raise SystemExit(main())
