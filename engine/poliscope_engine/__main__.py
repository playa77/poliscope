"""Bootstrap process, intentionally not the production WP-005 wire protocol."""
import argparse
import sys
from typing import Literal

from pydantic import BaseModel, ConfigDict
from poliscope_engine import __version__


class BootstrapIdentity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["bootstrap-ready"] = "bootstrap-ready"
    version: Literal["0.1.0"] = __version__


def main() -> int:
    parser = argparse.ArgumentParser(description="Poliscope bootstrap runtime")
    parser.parse_args()
    print(BootstrapIdentity().model_dump_json(), flush=True)
    # No RPC exists yet. EOF is the development lifecycle shutdown signal.
    for line in sys.stdin:
        print("bootstrap runtime does not accept requests", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
