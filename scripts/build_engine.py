"""Build a native one-directory engine, preserving resources outside ASAR."""
from pathlib import Path
import subprocess
import sys
import platform

root = Path(__file__).resolve().parents[1]
if sys.platform not in ('win32', 'linux') or platform.machine().lower() not in ('amd64', 'x86_64'):
    raise SystemExit('Build the engine natively on Windows x64 or Linux x64')
subprocess.run([sys.executable, str(root / 'scripts/build_content.py'), '--check'], cwd=root, check=True)
subprocess.run([
    sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
    "--name", "poliscope-engine", "--onedir",
    "--distpath", str(root / "build" / "engine"),
    "--workpath", str(root / "build" / "pyinstaller"),
    "--specpath", str(root / "build"),
    "--paths", str(root / "engine"),
    "--add-data", str(root / "content/release-v1") + ":poliscope_content",
    str(root / "packaging" / "engine_entry.py"),
], cwd=root, check=True)
