import importlib.util
import json
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
import subprocess
import pytest

spec = importlib.util.spec_from_file_location('evidence', Path(__file__).parents[2] / 'scripts/evidence.py')
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


@pytest.mark.parametrize('xml', [
    '<testsuites/>', '<broken',
    '<testsuite errors="1"><testcase name="collection"/></testsuite>',
    '<testsuite><testcase name="bad"><failure/></testcase></testsuite>',
    '<testsuite><testcase name="later"><skipped message="not implemented"/></testcase></testsuite>',
])
def test_invalid_reports(tmp_path, xml):
    report = tmp_path / 'report.xml'
    report.write_text(xml)
    try:
        result = evidence.summarize(report)
    except (ValueError, evidence.ET.ParseError):
        return
    assert result['failed'] or result['skipped']


def test_skips_retain_reason(tmp_path):
    report = tmp_path / 'report.xml'
    report.write_text('<testsuite><testcase><skipped message="expected failure: missing service"/></testcase></testsuite>')
    assert evidence.summarize(report)['skip_reasons'] == ['expected failure: missing service']


def test_candidate_covers_untracked_and_deleted_files(tmp_path):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    file = tmp_path / 'fixture'
    file.write_text('first')
    first = evidence.candidate(tmp_path)
    file.write_text('second')
    assert evidence.candidate(tmp_path) != first
    subprocess.run(['git', 'add', 'fixture'], cwd=tmp_path, check=True)
    second = evidence.candidate(tmp_path)
    file.unlink()
    assert evidence.candidate(tmp_path) != second


def test_exact_oracle_exposes_decimal_lost_transfer(synthetic):
    # Fractions use integer ratios, independently of the production Decimal context.
    stock, transfer = synthetic['stock'], synthetic['transfer']
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = 'ROUND_HALF_EVEN'
        rounded = Decimal(stock) - Decimal(transfer)
    assert Fraction(rounded) != Fraction(stock) - Fraction(transfer)
    assert Fraction(stock) - Fraction(transfer) + Fraction(transfer) == Fraction(stock)


def test_private_directory(isolated_data):
    assert isolated_data.is_dir()
    assert not list(isolated_data.iterdir())


def test_verify_rejects_stale_and_modified_report(tmp_path, monkeypatch):
    report = tmp_path / 'junit.xml'
    report.write_text('<testsuite><testcase name="works"/></testsuite>')
    record = dict(status='passed', exit_code=0, candidate='old',
                  report_sha256=evidence.hashlib.sha256(report.read_bytes()).hexdigest(),
                  results=evidence.summarize(report))
    (tmp_path / 'evidence.json').write_text(json.dumps(record))
    monkeypatch.setattr(evidence, 'candidate', lambda root: 'new')
    with pytest.raises(ValueError, match='Stale'):
        evidence.verify(tmp_path)
    monkeypatch.setattr(evidence, 'candidate', lambda root: 'old')
    evidence.verify(tmp_path)
    report.write_text('<testsuites/>')
    with pytest.raises(ValueError, match='changed'):
        evidence.verify(tmp_path)


@pytest.mark.parametrize('exit_code,xml', [
    (1, '<testsuite><testcase name="claimed pass"/></testsuite>'),
    (0, '<testsuites/>'),
    (0, '<testsuite><testcase name="bad"><failure/></testcase></testsuite>'),
    (0, '<testsuite><testcase name="later"><skipped/></testcase></testsuite>'),
])
def test_runner_rejects_exit_and_bad_results(tmp_path, monkeypatch, exit_code, xml):
    monkeypatch.setattr(evidence, 'candidate', lambda root: 'stable')
    monkeypatch.setattr(evidence.subprocess, 'check_output', lambda *a, **kw: 'fixture-version')
    def execute(command, **kwargs):
        report = next(arg.split('=', 1)[1] for arg in command if arg.startswith('--junitxml='))
        Path(report).write_text(xml)
        return subprocess.CompletedProcess(command, exit_code)
    monkeypatch.setattr(evidence.subprocess, 'run', execute)
    assert not evidence.run('engine', tmp_path / 'run')
    with pytest.raises(FileExistsError):
        evidence.run('engine', tmp_path / 'run')
