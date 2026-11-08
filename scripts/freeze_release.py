"""Freeze or verify release inputs without publishing or evaluating a model.

Product inputs and upstream evidence are separate from mutable release notes.
Git supplies the path inventory (including new unignored files); bytes come from
this checkout. No environment, saves, keys or ignored build output is inspected.

The default output path is the active receipt of the current label. A new
candidate label (--label) must be written to a separately named release
directory; prior receipts are never overwritten or relabeled in place.
"""
import argparse
import ast
import hashlib
import json
import re
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
# The active receipt lives in the current label's release directory; keep this
# path and the label on the release README in step when preparing a candidate.
DEFAULT = ROOT / 'docs/releases/0.1.0-rc.2/inventory.ci-history.json'
LABEL = re.compile(r'0\.1\.0-rc\.\d+')
PRODUCT_DIRS = ('desktop/', 'engine/', 'contracts/', 'content/', 'packaging/')
PRODUCT_FILES = ('LICENSE', 'package.json', 'package-lock.json', 'pyproject.toml', 'uv.lock',
                 '.nvmrc', '.python-version', 'forge.config.cjs', 'tsconfig.json',
                 'vite.main.config.mts', 'vite.preload.config.mts', 'vite.renderer.config.mts',
                 'scripts/build_content.py', 'scripts/generate_contracts.py',
                 'scripts/build_engine.py', 'scripts/check_bundle.mjs',
                 'scripts/distribution.py', 'scripts/desktop.mjs', 'scripts/bundle_paths.mjs')
EVIDENCE_PREFIX = 'docs/roadmap/execution/'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def included(name):
    return (name.startswith(PRODUCT_DIRS) or name in PRODUCT_FILES or
            name.startswith('.github/workflows/') or
            name.startswith(EVIDENCE_PREFIX + 'WP-055') or
            name.startswith(EVIDENCE_PREFIX + 'evidence/WP-055/') or
            name in [EVIDENCE_PREFIX + p for p in
                     ('requirements.json', 'gates.json', 'regressions.json')] or
            name in ('docs/design_doc.md', 'docs/tech_spec.md',
                     'docs/roadmap/verification_matrix.md', 'docs/provider_compatibility.md',
                     'docs/platform_scope.md'))


def inputs(root=ROOT):
    names = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others',
                                     '--exclude-standard'], cwd=root).decode().split('\0')
    result = []
    for name in sorted(set(filter(None, names))):
        if not included(name):
            continue
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Release input missing or symbolic: {name}')
        data = path.read_bytes()
        result.append(dict(path=name, bytes=len(data), sha256=digest(data)))
    if not result:
        raise ValueError('Empty release inventory')
    return result


def fingerprint(files):
    return digest(json.dumps(files, sort_keys=True, separators=(',', ':')).encode())


def constant(root, name, key):
    tree = ast.parse((root / name).read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == key for t in node.targets):
            value = node.value
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == 'dict' and not value.args:
                return {item.arg: ast.literal_eval(item.value) for item in value.keywords if item.arg}
            return ast.literal_eval(value)
    raise ValueError(f'Missing identity constant: {key}')


def identities(root, release):
    wire = json.loads((root / 'contracts/wire.schema.json').read_text())['$defs']['Versions']['properties']
    return dict(protocol=wire['protocol']['const'], wire_schema=wire['schema_version']['const'],
                sqlite_schema=constant(root, 'engine/poliscope_engine/storage/store.py', 'SCHEMA_VERSION'),
                numeric_runtime=constant(root, 'engine/poliscope_engine/numeric/__init__.py', 'RUNTIME_ID'),
                workspace_model=list(constant(root, 'engine/poliscope_engine/workspace.py', 'MODEL')),
                calendar=constant(root, 'engine/poliscope_engine/workspace.py', 'TIME')['calendar_id'],
                content_release=release['version'])


def verify_source_commit(root, commit, files):
    # A source SHA must actually contain these inputs, not merely be an ancestor.
    names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', '-z', commit], cwd=root).decode().split('\0')
    if {name for name in names if included(name)} != {item['path'] for item in files}:
        raise ValueError('Commit frozen inputs before preparing the release inventory')
    subprocess.run(['git', 'diff', '--quiet', commit, '--', *[item['path'] for item in files]],
                   cwd=root, check=True)


def freeze(root=ROOT, label='0.1.0-rc.1'):
    files = inputs(root)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    verify_source_commit(root, commit, files)
    package = json.loads((root / 'package.json').read_text())
    release = json.loads((root / 'content/release-v1/release.json').read_text())
    source = json.loads((root / 'content/release-v1/society.inventory.json').read_text())
    return dict(version=1, release_candidate=label, app_version=package['version'],
                source_commit=commit,
                status='prepared; not authorized for release publication',
                identity_scope='Exact product/build inputs, WP-055 evidence and requirement sources; release guides and this inventory are versioned by the delivery commit.',
                fingerprint=fingerprint(files), files=files,
                versions=identities(root, release),
                catalogs=release['catalogs'], source_revision=source['revision'],
                source_archive_digest=source['archive_digest'])


def verify(record, root=ROOT):
    label = record.get('release_candidate')
    if record.get('version') != 1 or not (isinstance(label, str) and LABEL.fullmatch(label)):
        raise ValueError('Unsupported release inventory')
    current = inputs(root)
    if record.get('files') != current or record.get('fingerprint') != fingerprint(current):
        raise ValueError('Frozen input drift: review affected evidence and prepare a new candidate')
    # Prevent edited summary metadata from disagreeing with the frozen bytes.
    expected = freeze(root, label)
    for key in ('app_version', 'versions', 'catalogs', 'source_revision', 'source_archive_digest'):
        if record.get(key) != expected[key]:
            raise ValueError(f'Release identity mismatch: {key}')
    commit = record.get('source_commit', '')
    verify_source_commit(root, commit, current)
    subprocess.run(['git', 'merge-base', '--is-ancestor', commit, 'HEAD'], cwd=root, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return len(current)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT,
        help='Receipt path; use the target label release directory to keep labels and paths in step')
    parser.add_argument('--label', default='0.1.0-rc.1',
        help='Release candidate label recorded in a newly prepared inventory')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        if args.check:
            count = verify(json.loads(args.output.read_text()))
            print(f'{count} frozen release inputs verified; publication remains separate')
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            # Build first: an invalid identity must not leave a partial receipt.
            encoded = json.dumps(freeze(label=args.label), indent=2) + '\n'
            # Exclusive creation preserves an existing candidate and its evidence.
            with args.output.open('x') as output:
                output.write(encoded)
            print('Release inventory prepared; no artifact published')
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Release freeze rejected: {error}\n')


if __name__ == '__main__':
    main()
