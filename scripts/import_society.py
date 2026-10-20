"""Offline pinned-corpus import. Never modifies a sandbox or activates models."""
import argparse
from pathlib import Path
from poliscope_engine.corpus import canonical, import_repository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repository', type=Path, help='local Git clone containing the pinned source commit')
    parser.add_argument('output', type=Path, help='new directory for candidate archive and inventory')
    args = parser.parse_args()
    result = import_repository(args.repository)
    # Refuse overwrite, including existing drafts. Compute and validate first.
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'reference-pack.json').write_bytes(canonical(result.archive.pack.model_dump(mode='json')))
    (args.output / 'inventory.json').write_bytes(canonical(result.report))
    print(f'Imported {len(result.report["decisions"])} reference decisions; no policies or models activated.')


if __name__ == '__main__':
    main()
