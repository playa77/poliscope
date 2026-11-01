"""Identical known answers run in managed Python and the packaged engine."""
from poliscope_engine.native_probe import check


def test_offline_runtime_known_answers_and_cold_replay():
    result = check()
    assert result['status'] == 'passed'
    assert result['numeric_runtime'] == 'decimal28-half-even-exact-v1'
    assert result['checks'] == ['decimal-known-answers', 'named-draw-known-answer',
        'sqlite-cold-replay', 'archive-roundtrip']


def test_probe_fails_closed_with_constant_diagnostic(monkeypatch, capsys):
    from poliscope_engine import native_probe
    def failure():
        raise RuntimeError('private path or credential canary')
    monkeypatch.setattr(native_probe, 'check', failure)
    assert native_probe.main() == 1
    assert capsys.readouterr().out == '{"probe_version":1,"status":"failed"}\n'
