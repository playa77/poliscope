"""Build once from pinned Git objects, or verify retained reproducible artifacts."""
import argparse
from pathlib import Path
from poliscope_engine.content import load_release, decode
from poliscope_engine.content.build import build
from poliscope_engine.corpus import import_repository, canonical
from poliscope_engine.packs import PackArchive, digest

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--society', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'content' / 'release-v1')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.society:
        imported = import_repository(args.society)
        reference, report = imported.archive, imported.report
    elif args.check:
        release = load_release(args.output)
        reference = PackArchive(release.artifact('society.pack.json'))
        report = decode(release.artifact('society.inventory.json'))
    else:
        parser.error('initial builds require --society at the pinned revision')
    # Compare source artifact and inventory against WP-025's reviewed checkpoint.
    inventory = decode((ROOT / 'docs/roadmap/execution/society/inventory.json').read_bytes())
    if report != inventory or reference.digest != inventory['archive_digest']:
        raise SystemExit('Pinned source inventory/digest drift')
    outputs = build(reference, report, (ROOT / 'LICENSE').read_bytes(),
                    (ROOT / 'docs/roadmap/execution/society/review.md').read_bytes())
    inventory = dict(version=1, status='immutable-release-v1', files={f'release-v1/{p}': digest(b) for p, b in sorted(outputs.items())})
    if args.output == ROOT / 'content/release-v1' and args.check:
        actual = {p.relative_to(ROOT / 'content').as_posix() for p in (ROOT / 'content').rglob('*') if p.is_file()}
        research_files = {'health/README.md', 'health/coverage-v1.json', 'knowledge-culture/README.md', 'knowledge-culture/coverage-v1.json', 'social-organization/README.md', 'social-organization/coverage-v1.json', 'law-conflict/README.md', 'law-conflict/coverage-v1.json', 'provisioning/README.md', 'provisioning/coverage-v1.json', 'economy/README.md', 'economy/coverage-v1.json', 'governance/README.md', 'governance/coverage-v1.json'}
        from poliscope_engine.domains.provisioning.coverage import validate_coverage
        validate_coverage(decode((ROOT / 'content/provisioning/coverage-v1.json').read_bytes()), report)
        from poliscope_engine.domains.economy.coverage import validate_coverage as validate_economy
        validate_economy(decode((ROOT / 'content/economy/coverage-v1.json').read_bytes()), report)
        from poliscope_engine.domains.law_conflict.coverage import validate_coverage as validate_law
        validate_law(decode((ROOT / 'content/law-conflict/coverage-v1.json').read_bytes()), report)
        from poliscope_engine.domains.governance.coverage import validate_coverage as validate_governance
        validate_governance(decode((ROOT / 'content/governance/coverage-v1.json').read_bytes()), report)
        from poliscope_engine.domains.social_organization.coverage import validate_coverage as validate_care
        validate_care(decode((ROOT / 'content/social-organization/coverage-v1.json').read_bytes()), report)
        from poliscope_engine.domains.knowledge_culture.coverage import validate_coverage as validate_education
        validate_education(decode((ROOT / 'content/knowledge-culture/coverage-v1.json').read_bytes()), report)
        from poliscope_engine.domains.health.coverage import validate_coverage as validate_health
        validate_health(decode((ROOT / 'content/health/coverage-v1.json').read_bytes()), report)
        if actual != {*inventory['files'], 'README.md', 'inventory.json', *research_files} or decode((ROOT / 'content/inventory.json').read_bytes()) != inventory:
            raise SystemExit('Content inventory drift or unregistered artifacts')
    if args.check:
        for path, expected in outputs.items():
            if (args.output / path).read_bytes() != expected:
                raise SystemExit('Content drift: ' + path)
    else:
        args.output.mkdir(parents=True, exist_ok=False)
        for path, value in outputs.items():
            (args.output / path).write_bytes(value)
        if args.output == ROOT / 'content/release-v1':
            (ROOT / 'content/inventory.json').write_bytes(canonical(inventory))
    print('content: immutable release validated; source models remain blocked')


if __name__ == '__main__':
    main()
