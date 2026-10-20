"""Real pinned text regression plus synthetic mutations and independent oracles."""
import copy
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from poliscope_engine.corpus import (CorpusError, LEDGER, MAP, REVISION, _ledger, _map,
                                     _transform, canonical, import_repository, snapshot)
from poliscope_engine.packs import PackArchive, PackError

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fixtures/corpus/society-text.json'
INVENTORY = ROOT / 'docs/roadmap/execution/society/inventory.json'


@pytest.fixture(scope='module')
def files():
    # PDF bytes are synthetic: no production identity assertion is made for them.
    texts = json.loads(FIXTURE.read_text())
    return {k: v.encode() for k, v in texts.items()} | {'02_AI-Essay.pdf': b'%PDF-synthetic-context'}


@pytest.fixture(scope='module')
def result(files):
    return _transform(files)


def test_real_text_inventory_and_digest_are_exhaustive(files, result):
    expected = json.loads(INVENTORY.read_text())
    assert result.archive.digest == expected['archive_digest']
    assert len(result.report['files']) == 28
    for row in expected['files']:
        if row['path'] == '02_AI-Essay.pdf':
            assert row['archived'] is False and row['bytes'] == 62590
            continue
        assert row['digest'] == 'sha256:' + hashlib.sha256(files[row['path']]).hexdigest()
        assert row['bytes'] == len(files[row['path']])
        assert row in result.report['files']
    for key in ['domains', 'decisions', 'content_layers', 'changelog_ids', 'preserved_alternative_index_labels']:
        assert result.report[key] == expected[key]
    assert len(result.archive.pack.files) == 27
    assert result.archive.pack.files == PackArchive(canonical(result.archive.pack.model_dump(mode='json'))).pack.files


def test_all_domains_branches_and_missing_coverage_are_visible(result):
    domains = result.report['domains']
    assert [row['roman'] for row in domains] == ['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII']
    assert len(domains) == 12
    assert sum(len(d['branches']) for d in domains) == 38
    leaves = [leaf for domain in domains for branch in domain['branches'] for leaf in branch['leaves']]
    assert len(leaves) == 115
    detailed = [leaf for leaf in leaves if leaf['coverage'] == 'source_design_only']
    assert [leaf['id'] for leaf in detailed] == [f'society:domain/01/1/{i}' for i in range(1,5)] + [f'society:domain/01/2/{i}' for i in range(1,4)]
    assert all(len(leaf['documents']) == 2 for leaf in detailed)
    assert len([leaf for leaf in leaves if leaf['coverage'] == 'map_only']) == 108


def test_full_alternatives_compound_identity_and_tentative_status(result):
    definitions = {d.id: d for d in result.archive.pack.definitions}
    decisions = {d['id']: d for d in result.report['decisions']}
    assert len(decisions) == 24
    assert len([d for d in definitions.values() if d.kind == 'option']) == 87
    for identity in ['DEC-021', 'DEC-022']:
        record = decisions[identity]
        assert len(record['option_ids']) == 9 and len(set(record['option_ids'])) == 9
        assert len(record['round_ids']) == 3
        for option_id in record['option_ids']:
            option = definitions[option_id]
            assert definitions[option.parent_ref].kind == 'question'
            assert option.original_text in definitions[option.parent_ref].original_text
    assert [row['qualifier'] for row in decisions['DEC-021']['option_statuses']].count('ownership') == 3
    assert 'alt-A both parts' in decisions['DEC-009']['recorded_decision']
    assert len(decisions['DEC-009']['round_ids']) == 1  # One joint bundle, no invented combinatorics.
    for identity in ['DEC-013','DEC-017']:
        option = definitions[f'society:{identity}/option/A']
        assert option.historical_status == 'unspecified'
        assert decisions[identity]['option_statuses'][0]['status'] == 'chosen_tentatively'
        assert '[CHOSEN tentatively]' in option.original_text


def test_supersession_is_explicit_and_document_work_is_provenance(result):
    definitions = {d.id: d for d in result.archive.pack.definitions}
    assert definitions['society:DEC-003'].supersedes_refs == ['society:DEC-002.2']
    assert definitions['society:DEC-002.2'].historical_status == 'superseded'
    assert not definitions['society:DEC-003/option/A'].supersedes_refs
    for identity in ['DEC-018','DEC-023','DEC-024']:
        assert definitions['society:' + identity].historical_status == 'provenance'
        assert all(d.historical_status == 'provenance' for d in definitions.values() if d.parent_ref == 'society:' + identity)
    assert definitions['society:DEC-007/option/A'].historical_status == 'adopted'
    decision19 = next(d for d in result.report['decisions'] if d['id'] == 'DEC-019')
    assert decision19['amends'] == ['DEC-007']  # Partial amendment, not whole-option erasure.
    assert definitions['society:DEC-022/round/2'].historical_status == 'provenance'
    assert all(d.historical_status == 'provenance' for d in definitions.values() if d.parent_ref == 'society:DEC-022/round/2')
    assert len(result.report['preserved_alternative_index_labels']) == 52
    assert len(result.report['changelog_ids']) == 16


def test_import_is_deterministic_nonactivating_and_detached(files, result):
    reverse = dict(reversed(list(files.items())))
    rerun = _transform(reverse)
    assert canonical(result.report) == canonical(rerun.report)
    assert canonical(result.archive.pack.model_dump(mode='json')) == canonical(rerun.archive.pack.model_dump(mode='json'))
    assert all(d.modeling == 'unsupported' and d.evidence == 'unreviewed' and not d.mechanism_refs for d in result.archive.pack.definitions)
    assert not result.archive.pack.variables and not result.archive.pack.assumptions
    assert not result.report['content_layers']['selected_player_policies']
    assert not result.report['content_layers']['activated_mechanisms']
    pack = result.archive.pack
    pack.definitions.clear()
    assert result.archive.pack.definitions


@pytest.mark.parametrize('change,code', [
    (lambda p:p.pop('LICENSE'), 'license_unavailable'),
    (lambda p:p.update(LICENSE=b'No permission'), 'license_requires_review'),
    (lambda p:p.update({'../outside.md':b'untrusted'}), 'unsafe_source_path'),
    (lambda p:p.update({'plugin.py':b'raise Exception()'}), 'unclassified_source_file'),
    (lambda p:p.pop(MAP), 'source_inventory_incomplete'),
    (lambda p:p.update({'large.md':b'x'*(4*1024*1024)}), 'source_size'),
])
def test_missing_license_unknown_files_and_oversize_fail_closed(files, change, code):
    mutated = copy.copy(files)
    change(mutated)
    with pytest.raises(CorpusError, match=code):
        _transform(mutated)


@pytest.mark.parametrize('old,new,code', [
    ('**Question:**', '**Prompt:**', 'missing_ledger_field'),
    ('[CHOSEN]', '[UNKNOWN]', 'missing_option_status'),
    ('DEC-024 —', 'DEC-025 —', 'foreign_option'),
])
def test_new_or_ambiguous_ledger_layout_is_not_silently_guessed(files, old, new, code):
    text = files[LEDGER].decode().replace(old,new,1)
    with pytest.raises(CorpusError, match=code):
        _ledger(text,'society:source')


def test_duplicate_option_ids_and_source_tampering_are_rejected(files, result):
    altered = copy.copy(files)
    altered[LEDGER] = altered[LEDGER].replace(b'DEC-001-alt-B',b'DEC-001-alt-A',1)
    with pytest.raises(PackError,match='duplicate_identity'):
        _transform(altered)
    payload = result.archive.pack.model_dump(mode='json')
    payload['files'][0]['text'] += '\nchanged'
    with pytest.raises(PackError,match='file_digest'):
        PackArchive(canonical(payload))


def test_missing_pinned_revision_is_not_replaced_by_head(tmp_path):
    subprocess.run(['git','init',str(tmp_path)],check=True,capture_output=True)
    with pytest.raises(CorpusError,match='pinned_revision_unavailable'):
        import_repository(tmp_path)


def test_cli_help_describes_offline_local_inputs():
    # Check help is available offline; output overwrite is exercised using the
    # real pinned repository during the recorded package acceptance run.
    completed = subprocess.run([sys.executable,str(ROOT/'scripts/import_society.py'),'--help'],capture_output=True,text=True)
    assert completed.returncode == 0 and 'local Git clone' in completed.stdout


def test_arithmetic_review_uses_independent_dimensional_oracles():
    # Source annual volume cannot directly yield a daily intake. Its two
    # interpretations differ by 365, so no corrected agronomic model is inferred.
    D = Decimal
    with localcontext() as ctx:
        ctx.prec = 50
        source_literal_annual_kcal = [D('505')*D('.75'), D('540')*D('.75')]
        assert source_literal_annual_kcal == [D('378.75'), D('405.00')]
        assert source_literal_annual_kcal[0]/D(365) < D('1.04')
        annual_water_for_daily_target = D(1400)*D('.7')*D(365)/D('.75')
        assert annual_water_for_daily_target > D(476933)  # Source claims about 1,300.
        # Labor's 21–34% is rounded interval arithmetic, not evidence that all
        # service labor is already exhausted. Extreme endpoints vary together.
        assert D(13)/D(62)*100 > D('20.96')
        assert D(19)/D(55)*100 < D('34.55')
        corridor_low = D('.22')+D('.013')+D('.4')
        corridor_high = D('.25')+D('.013')+D('.6')
        assert (corridor_low,corridor_high) == (D('.633'),D('.863'))
        assert corridor_low > D('.5') and corridor_high < D('1.5')
        stock_low = D(25)+D('1.2')+D('.2')+D('.1')
        stock_high = D(29)+D('1.8')+D('.4')+D('.4')
        assert (stock_low,stock_high)==(D('26.5'),D('31.6'))


def test_pinned_snapshot_ignores_dirty_checkout_and_git_replacement(tmp_path, monkeypatch):
    import poliscope_engine.corpus as corpus
    subprocess.run(['git','init',str(tmp_path)],check=True,capture_output=True)
    def git(*args):
        return subprocess.check_output(['git','-C',str(tmp_path),*args],stderr=subprocess.PIPE).decode().strip()
    original = tmp_path/'source.md'
    original.write_text('immutable original\n')
    git('add','source.md')
    git('-c','user.name=Synthetic','-c','user.email=synthetic@example.invalid','commit','-m','synthetic source')
    first = git('rev-parse','HEAD')
    monkeypatch.setattr(corpus,'REVISION',first)
    original.write_text('committed replacement\n')
    git('add','source.md')
    git('-c','user.name=Synthetic','-c','user.email=synthetic@example.invalid','commit','-m','replacement')
    git('replace',first,git('rev-parse','HEAD'))
    original.write_text('dirty edit\n')
    assert snapshot(tmp_path) == {'source.md':b'immutable original\n'}


@pytest.mark.parametrize('entry_type',['symlink','executable','nested'])
def test_snapshot_rejects_unexpected_git_entry_modes_and_paths(tmp_path, monkeypatch, entry_type):
    import poliscope_engine.corpus as corpus
    subprocess.run(['git','init',str(tmp_path)],check=True,capture_output=True)
    path = tmp_path/'source.md'
    if entry_type == 'symlink':
        path.symlink_to('/tmp/outside-corpus')
    elif entry_type == 'executable':
        path.write_text('data')
        path.chmod(0o755)
    else:
        path = tmp_path/'nested/source.md'
        path.parent.mkdir()
        path.write_text('data')
    subprocess.run(['git','-C',str(tmp_path),'add','.'],check=True,capture_output=True)
    subprocess.run(['git','-C',str(tmp_path),'-c','user.name=Synthetic','-c','user.email=synthetic@example.invalid','commit','-m','synthetic'],check=True,capture_output=True)
    commit = subprocess.check_output(['git','-C',str(tmp_path),'rev-parse','HEAD']).decode().strip()
    monkeypatch.setattr(corpus,'REVISION',commit)
    with pytest.raises(CorpusError,match='unsupported_source_entry'):
        snapshot(tmp_path)


def test_system_provenance_and_unindexed_rejections_are_preserved(result):
    assert result.report['system_decisions'][0]['id'] == 'DEC-SYS-001'
    assert any(d.id == 'society:DEC-SYS-001' and d.historical_status == 'provenance' for d in result.archive.pack.definitions)
    assert result.report['unindexed_alternatives'] == [
        'society:DEC-006/option/C', 'society:DEC-009/option/B',
        'society:DEC-011/option/C', 'society:DEC-014/option/C',
        'society:DEC-015/option/C', 'society:DEC-021/round/1/option/C',
        'society:DEC-021/round/2/option/B']
    definitions = {d.id:d for d in result.archive.pack.definitions}
    assert all(definitions[key].historical_status == 'alternative' for key in result.report['unindexed_alternatives'])


def test_report_mutation_does_not_change_future_imports(files, result):
    report = _transform(files).report
    next(d for d in report['decisions'] if d['id']=='DEC-003')['supersedes'].clear()
    next(d for d in report['decisions'] if d['id']=='DEC-019')['amends'].append('invented')
    assert canonical(_transform(files).report) == canonical(result.report)
