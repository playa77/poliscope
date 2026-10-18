import json
import subprocess
import sys


def run(*args, input=""):
    return subprocess.run([sys.executable, "-I", "-m", "poliscope_engine", *args],
                          input=input, text=True, capture_output=True, timeout=10)


def test_identity_and_eof_shutdown():
    result = run()
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"kind": "bootstrap-ready", "version": "0.1.0"}
    assert len(result.stdout.splitlines()) == 1
    assert result.stderr == ""


def test_requests_are_explicitly_unsupported():
    result = run(input='{"method":"apply"}\n')
    assert result.returncode == 2
    assert "does not accept requests" in result.stderr


def test_unknown_arguments_fail():
    result = run("--arbitrary")
    assert result.returncode == 2
    assert result.stdout == ""
