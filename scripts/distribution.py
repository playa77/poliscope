"""Build an offline per-user distribution from a native Forge package.

Unsigned is the default and is recorded explicitly. Signing is opt-in using
external key stores; no publication occurs. Run on the target OS, x64 only.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def target():
    if platform.machine().lower() not in ('amd64', 'x86_64') or sys.platform not in ('win32', 'linux'):
        raise ValueError('Only native Windows x64 and Linux x64 distributions are supported')
    return 'win32' if sys.platform == 'win32' else 'linux'


def check_binary(path, system):
    with path.open('rb') as stream:
        head = stream.read(64)
        if system == 'linux':
            if len(head) != 64 or head[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', head, 18)[0] != 62:
                raise ValueError('Expected Linux x64 ELF executable')
            if not os.access(path, os.X_OK):
                raise ValueError('Native executable permission missing')
        else:
            if head[:2] != b'MZ' or len(head) != 64:
                raise ValueError('Expected Windows executable')
            stream.seek(struct.unpack_from('<I', head, 60)[0])
            if stream.read(6) != b'PE\0\0d\x86':
                raise ValueError('Expected Windows x64 PE executable')


def inventory(directory):
    result = []
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ValueError('Distribution must not contain symlinks')
        if path.is_file():
            result.append(dict(path=path.relative_to(directory).as_posix(), bytes=path.stat().st_size,
                sha256=sha256(path), mode=path.stat().st_mode & 0o777))
    return result


def build(output, *, sign=False):
    system = target()
    version = json.loads((ROOT / 'package.json').read_text())['version']
    name = f'Poliscope-{version}-{system}-x64'
    source = ROOT / 'out' / f'Poliscope-{system}-x64'
    if not source.is_dir():
        raise ValueError('Run npm run package on this target first')
    output.mkdir(parents=True, exist_ok=True)
    # Do not overwrite a prior candidate or silently replace its evidence.
    suffix = '.zip' if system == 'win32' else '.tar.gz'
    archive = output / (name + suffix)
    receipt = output / (name + '.json')
    checksum = output / (name + '.sha256')
    if any(p.exists() for p in (archive, receipt, checksum, Path(str(archive) + '.asc'))):
        raise FileExistsError('Choose a fresh output directory for this candidate')
    with tempfile.TemporaryDirectory(prefix='poliscope-distribution-') as temporary:
        root = Path(temporary)
        bundle = root / name
        app = bundle / 'app'
        shutil.copytree(source, app, symlinks=True)
        inventory(app)  # Reject links before executing any bundled probe.
        extension = '.exe' if system == 'win32' else ''
        engine = app / 'resources/poliscope-engine' / ('poliscope-engine' + extension)
        check_binary(app / ('poliscope' + extension), system)
        check_binary(engine, system)
        asar = json.loads(subprocess.check_output(['node', str(ROOT / 'scripts/check_bundle.mjs'),
            str(app / 'resources/app.asar')], cwd=ROOT, timeout=30))
        dependencies = {'status': 'owner-run', 'scope': 'Windows DLL loading plus desktop smoke'}
        if system == 'linux':
            libraries = set()
            for executable in (app / 'poliscope', engine):
                linked = subprocess.check_output(['ldd', str(executable)], text=True, timeout=30)
                if 'not found' in linked:
                    raise ValueError('Missing native shared library')
                libraries.update(line.strip().split()[0] for line in linked.splitlines() if line.strip())
            dependencies = dict(status='resolved-on-build-host', libraries=sorted(libraries),
                scope='Electron and engine direct dependencies; optional desktop/GPU/keyring integrations owner-run')
        installer = 'install-windows.ps1' if system == 'win32' else 'install-linux.sh'
        (bundle / installer).write_text((ROOT / 'packaging' / installer).read_text().replace('@VERSION@', version), encoding='utf-8', newline='\n')
        (bundle / installer).chmod(0o755)
        if system == 'linux':
            shutil.copyfile(ROOT / 'packaging/sandbox-notice.sh', bundle / 'sandbox-notice.sh')
            shutil.copytree(ROOT / 'packaging/icons', bundle / 'icons')
        if sign and system == 'win32':
            subprocess.run(['powershell.exe', '-NoProfile', '-File', str(ROOT / 'packaging/sign-windows.ps1'),
                '-AppDirectory', str(app)], check=True)
        # Empty PATH demonstrates the engine never needs an installed interpreter.
        env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'LANG', 'LC_ALL') if key in os.environ}
        env['PATH'] = ''
        probe = subprocess.run([str(engine), '--self-test'], cwd=root, env=env,
            capture_output=True, timeout=60, check=True)
        result = json.loads(probe.stdout)
        if result.get('status') != 'passed' or result.get('application') != version or probe.stderr:
            raise ValueError('Bundled runtime identity/self-test failed')
        files = inventory(bundle)
        if any('\n' in row['path'] or '\r' in row['path'] or '\\' in row['path'] for row in files):
            raise ValueError('Unsupported distribution filename')
        (bundle / 'payload.sha256').write_text(''.join(f"{row['sha256']}  {row['path']}\n" for row in files))
        metadata = dict(format_version=1, application=version, target=f'{system}-x64',
            source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            source_dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
            locks={p: sha256(ROOT / p) for p in ('package-lock.json', 'uv.lock')},
            contracts={p.relative_to(ROOT).as_posix(): sha256(p) for p in sorted((ROOT / 'contracts').glob('*.schema.json'))},
            content={p.relative_to(ROOT).as_posix(): sha256(p) for p in sorted((ROOT / 'content/release-v1').rglob('*')) if p.is_file()},
            signing='windows-authenticode-verified' if sign and system == 'win32' else 'linux-detached-gpg' if sign else 'unsigned',
            asar=asar, native_dependencies=dependencies, probe=result, files=files)
        (bundle / 'manifest.json').write_text(json.dumps(metadata, indent=2) + '\n')
        if system == 'win32':
            shutil.make_archive(str(output / name), 'zip', root, name)
        else:
            with tarfile.open(archive, 'w:gz', compresslevel=1) as packed:
                packed.add(bundle, arcname=name)
    if sign and system == 'linux':
        identity = os.environ.get('POLISCOPE_GPG_IDENTITY')
        if not identity:
            archive.unlink()
            raise ValueError('Set POLISCOPE_GPG_IDENTITY to an external signing key')
        try:
            subprocess.run(['gpg', '--batch', '--local-user', identity, '--armor', '--detach-sign', str(archive)], check=True)
            subprocess.run(['gpg', '--verify', str(archive) + '.asc', str(archive)], check=True)
        except Exception:
            archive.unlink(missing_ok=True)
            Path(str(archive) + '.asc').unlink(missing_ok=True)
            raise
    metadata['artifact'] = dict(name=archive.name, sha256=sha256(archive), bytes=archive.stat().st_size)
    if sign and system == 'linux':
        metadata['signature_sha256'] = sha256(Path(str(archive) + '.asc'))
    receipt.write_text(json.dumps(metadata, indent=2) + '\n')
    checksum.write_text(f'{sha256(archive)}  {archive.name}\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'release')
    parser.add_argument('--sign', action='store_true')
    args = parser.parse_args()
    print(build(args.output.resolve(), sign=args.sign))
