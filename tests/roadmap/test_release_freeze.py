"""A release freeze must catch changed, removed and newly introduced inputs."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from freeze_release import freeze, verify


class ReleaseFreezeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name, value in {
            'package.json': {'version': '0.1.0'},
            'contracts/wire.schema.json': {'$defs': {'Versions': {'properties': {'protocol': {'const': 1}, 'schema_version': {'const': 1}}}}},
            'content/release-v1/release.json': {'version': 'v1', 'catalogs': []},
            'content/release-v1/society.inventory.json': {'revision': 'pinned', 'archive_digest': 'digest'},
        }.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value))
        for name, text in {
            'engine/poliscope_engine/storage/store.py': 'SCHEMA_VERSION = 2',
            'engine/poliscope_engine/numeric/__init__.py': 'RUNTIME_ID = \'numeric-v1\'',
            'engine/poliscope_engine/workspace.py': 'MODEL = (\'model\', \'v1\')\nTIME = dict(calendar_id=\'calendar-v1\')',
        }.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', 'add', '.'], cwd=self.root, check=True)
        subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                        'commit', '-qm', 'Synthetic baseline'], cwd=self.root, check=True)
        self.record = freeze(self.root)

    def test_valid_freeze_and_later_documentation_commit(self):
        self.assertEqual(verify(self.record, self.root), len(self.record['files']))
        (self.root / 'README.md').write_text('Release guide only')
        subprocess.run(['git', 'add', '.'], cwd=self.root, check=True)
        subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                        'commit', '-qm', 'Guide'], cwd=self.root, check=True)
        self.assertEqual(verify(self.record, self.root), len(self.record['files']))

    def test_changed_and_removed_frozen_inputs_fail(self):
        path = self.root / 'package.json'
        path.write_text('{"version":"0.2.0"}')
        with self.assertRaisesRegex(ValueError, 'drift'):
            verify(self.record, self.root)
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            verify(self.record, self.root)

    def test_new_product_and_evidence_files_fail(self):
        for name in ('engine/new.py', 'docs/roadmap/execution/WP-055-new.json'):
            with self.subTest(name=name):
                path = self.root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('new input')
                with self.assertRaisesRegex(ValueError, 'drift'):
                    verify(self.record, self.root)
                path.unlink()

    def test_dirty_product_cannot_be_frozen_with_a_clean_source_sha(self):
        (self.root / 'package.json').write_text('{\"version\":\"0.2.0\"}')
        with self.assertRaises(subprocess.CalledProcessError):
            freeze(self.root)

    def test_symlink_is_not_a_release_input(self):
        path = self.root / 'package.json'
        path.unlink()
        path.symlink_to('outside')
        with self.assertRaisesRegex(ValueError, 'symbolic'):
            verify(self.record, self.root)

    def test_summary_and_fingerprint_tampering_fail(self):
        for field in ('app_version', 'fingerprint', 'catalogs', 'source_archive_digest'):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.record)
                changed[field] = 'forged'
                with self.assertRaises(ValueError):
                    verify(changed, self.root)


class RetainedReleaseTests(unittest.TestCase):
    def test_retained_product_and_evidence_inventory_matches_checkout(self):
        from freeze_release import ROOT, DEFAULT
        record = json.loads(DEFAULT.read_text())
        self.assertGreater(verify(record, ROOT), 600)
