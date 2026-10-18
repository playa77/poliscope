"""Build a native one-directory engine, preserving resources outside ASAR."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
subprocess.run([
    sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
    "--name", "poliscope-engine", "--onedir",
    "--distpath", str(root / "build" / "engine"),
    "--workpath", str(root / "build" / "pyinstaller"),
    "--specpath", str(root / "build"),
    "--paths", str(root / "engine"),
    str(root / "packaging" / "engine_entry.py"),
], cwd=root, check=True)
