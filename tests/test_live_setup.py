"""Protection checks using temporary files only; never touch installed game/profile."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import launch_live
import prepare_live


class OriginalProtectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.private = root / 'private'
        (self.private / 'live').mkdir(parents=True)
        self.saves = root / 'original-saves'
        self.saves.mkdir()
        (self.saves / 'progress.dat').write_bytes(b'original progress')
        source = root / 'game'
        self.metadata = source / 'LobotomyCorp_Data/globalgamemanagers'
        self.metadata.parent.mkdir(parents=True)
        self.metadata.write_bytes(b'original settings')
        self.manifest = {'source': str(source), 'original_save_root': str(self.saves),
            'isolated_save_path': str(root / 'ai-saves'),
            'original_save_hashes': prepare_live.inventory(self.saves),
            'original_metadata_sha256': prepare_live.digest(self.metadata),
            'original_preferences': {'example': [4, 1]}}
        self.addCleanup(patch.stopall)
        patch.object(launch_live, 'PRIVATE', self.private).start()
        patch.object(launch_live, 'prefs_snapshot', return_value={'example': [4, 1]}).start()

    def test_unchanged_passes_without_modifying_originals(self):
        report = launch_live.check_original(self.manifest)
        self.assertTrue(report['ok'])
        self.assertEqual(prepare_live.inventory(self.saves), self.manifest['original_save_hashes'])

    def test_changed_added_and_deleted_save_files_are_reported(self):
        (self.saves / 'progress.dat').write_bytes(b'changed')
        (self.saves / 'new.dat').write_bytes(b'added')
        report = launch_live.check_original(self.manifest)
        self.assertTrue(report['ok'])
        self.assertEqual(report['changed_original_files'], ['new.dat', 'progress.dat'])
        (self.saves / 'progress.dat').unlink()
        self.assertIn('progress.dat', launch_live.check_original(self.manifest)['changed_original_files'])

    def test_metadata_and_preferences_changes_fail(self):
        self.metadata.write_bytes(b'changed settings')
        with patch.object(launch_live, 'prefs_snapshot', return_value={}):
            report = launch_live.check_original(self.manifest)
        self.assertFalse(report['ok'])
        self.assertFalse(report['original_metadata_unchanged'])
        self.assertFalse(report['original_preferences_unchanged'])

    def test_preferences_change_is_allowed(self):
        with patch.object(launch_live, 'prefs_snapshot', return_value={}):
            self.assertTrue(launch_live.check_original(self.manifest)['ok'])

    def test_overlapping_save_roots_block(self):
        for path in (self.saves, self.saves / 'child', self.saves.parent):
            self.manifest['isolated_save_path'] = str(path)
            self.assertFalse(launch_live.check_original(self.manifest)['ok'])

    def test_changed_save_allows_launch_request_without_rebaselining(self):
        (self.private / 'live/isolation.json').write_text(json.dumps(self.manifest), encoding='utf-8')
        (self.saves / 'progress.dat').write_bytes(b'new user progress')
        with patch.object(sys, 'argv', ['launch_live.py']), patch.object(launch_live, 'request_independent_launch') as request:
            launch_live.main()
            request.assert_called_once()
        self.assertEqual(json.loads((self.private / 'live/isolation.json').read_text()), self.manifest)
        self.assertEqual((self.saves / 'progress.dat').read_bytes(), b'new user progress')

    def test_changed_metadata_blocks_process_launch(self):
        (self.private / 'live/isolation.json').write_text(json.dumps(self.manifest), encoding='utf-8')
        (self.saves / 'progress.dat').write_bytes(b'changed')
        self.metadata.write_bytes(b'changed metadata')
        with patch.object(sys, 'argv', ['launch_live.py']), patch.object(launch_live.subprocess, 'Popen') as process:
            with self.assertRaisesRegex(RuntimeError, 'Save isolation or original game metadata'):
                launch_live.main()
            process.assert_not_called()


if __name__ == '__main__':
    unittest.main()
