"""Distribution rejection and real per-user install/upgrade behavior."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('distribution', ROOT / 'scripts/distribution.py')
distribution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(distribution)


def test_reject_wrong_architecture_and_non_binary(tmp_path):
    path = tmp_path / 'wrong'
    path.write_bytes(b'not a native executable')
    with pytest.raises(ValueError): distribution.check_binary(path, 'linux')
    with pytest.raises(ValueError): distribution.check_binary(path, 'win32')
    elf = bytearray(64); elf[:6] = b'\x7fELF\x02\x01'; elf[18:20] = (183).to_bytes(2, 'little')
    path.write_bytes(elf); path.chmod(0o755)
    with pytest.raises(ValueError): distribution.check_binary(path, 'linux')


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX installer and permissions')
def test_reject_symlink_and_missing_executable_permissions(tmp_path):
    path = tmp_path / 'engine'; shutil.copyfile('/bin/true', path); path.chmod(0o600)
    with pytest.raises(ValueError): distribution.check_binary(path, 'linux')
    (tmp_path / 'outside').symlink_to('/etc/passwd')
    with pytest.raises(ValueError): distribution.inventory(tmp_path)


@pytest.mark.skipif(sys.platform != 'linux', reason='POSIX installer')
def test_per_user_install_in_spaces_upgrade_retains_data_and_previous_version(tmp_path):
    bundle = tmp_path / 'bundle with spaces'
    engine = bundle / 'app/resources/poliscope-engine/poliscope-engine'
    engine.parent.mkdir(parents=True)
    engine.write_text('#!/bin/sh\ntest "$1" = --self-test\n'); engine.chmod(0o755)
    (bundle / 'app/poliscope').write_text('synthetic app')
    shutil.copyfile(ROOT / 'packaging/sandbox-notice.sh', bundle / 'sandbox-notice.sh')
    shutil.copytree(ROOT / 'packaging/icons', bundle / 'icons')
    home = tmp_path / 'home'; home.mkdir()
    data = home / '.config/Poliscope'; data.mkdir(parents=True)
    (data / 'private-canary').write_text('preserve')
    env = {**os.environ, 'HOME': str(home), 'XDG_DATA_HOME': str(home / 'data')}
    script = bundle / 'install-linux.sh'
    def checksums():
        files = distribution.inventory(bundle)
        (bundle / 'payload.sha256').write_text(''.join(f"{row['sha256']}  {row['path']}\n" for row in files if row['path'] != 'payload.sha256'))
    template = (ROOT / 'packaging/install-linux.sh').read_text()
    first = tmp_path / 'installed old'; second = tmp_path / 'installed new'
    script.write_text(template.replace('@VERSION@', '1.0'))
    checksums()
    assert subprocess.run(['sh', str(script), str(tmp_path / 'line\nbreak')], env=env).returncode != 0
    assert not (tmp_path / 'line\nbreak').exists()
    subprocess.run(['sh', str(script), str(first)], env=env, check=True)
    # Same-version retry cannot overwrite, including when the app is still open.
    assert subprocess.run(['sh', str(script), str(first)], env=env).returncode != 0
    script.write_text(template.replace('@VERSION@', '2.0'))
    checksums()
    subprocess.run(['sh', str(script), str(second)], env=env, check=True)
    assert (first / 'poliscope').read_text() == 'synthetic app'
    assert (data / 'private-canary').read_text() == 'preserve'
    desktop = (home / 'data/applications/poliscope.desktop').read_text()
    assert f'Exec="{second}/poliscope"' in desktop
    assert 'Icon=poliscope\n' in desktop
    assert (home / 'data/icons/hicolor/256x256/apps/poliscope.png').is_file()
    assert (bundle / 'icons/poliscope-256.png').is_file()
    # Tampered payload is rejected before creating the destination.
    (bundle / 'app/poliscope').write_text('tampered')
    assert subprocess.run(['sh', str(script), str(tmp_path / 'tampered')], env=env).returncode != 0
    assert not (tmp_path / 'tampered').exists()
    # Failure leaves the previous working launcher and data unchanged.
    engine.write_text('#!/bin/sh\nexit 1\n')
    checksums()
    assert subprocess.run(['sh', str(script), str(tmp_path / 'failed')], env=env).returncode != 0
    assert (home / 'data/applications/poliscope.desktop').read_text() == desktop


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX installer helper')
def test_sandbox_notice_prints_guidance_only_for_restricted_systems(tmp_path):
    helper = ROOT / 'packaging/sandbox-notice.sh'
    sysctl = tmp_path / 'sysctl'
    sysctl.write_text('0\n')
    unrestricted = subprocess.run(['sh', str(helper), str(sysctl), '1'], capture_output=True)
    assert unrestricted.returncode == 0 and unrestricted.stdout == b''
    missing = subprocess.run(['sh', str(helper), str(tmp_path / 'absent'), '1'], capture_output=True)
    assert missing.returncode == 0 and missing.stdout == b''
    sysctl.write_text('1\n')
    note = subprocess.run(['sh', str(helper), str(sysctl), '1'], capture_output=True)
    assert note.returncode == 0
    assert b'AppArmor' in note.stdout and b'chrome-sandbox' in note.stdout
