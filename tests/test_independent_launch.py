"""Launch handoff checks. Temporary state only, no Windows task or real game."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import launch_live


class IndependentLaunchTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.private = self.root/'.robotomy'
        (self.private/'live').mkdir(parents=True)
        self.addCleanup(patch.stopall)
        patch.object(launch_live, 'ROOT', self.root).start()
        patch.object(launch_live, 'PRIVATE', self.private).start()
        self.run = patch.object(launch_live.subprocess, 'run',
            return_value=Mock(returncode=0, stdout=b'{}', stderr=b'')).start()
        self.popen = patch.object(launch_live.subprocess, 'Popen').start()
        self.verify = patch('robotomy.virtual_input.verify_process').start()

    def state(self, **kwargs):
        (self.private/'live/launch-state.json').write_text(json.dumps(kwargs))

    def test_ready_requires_os_verified_game_and_worker(self):
        self.state(state='ready', game_pid=12, worker_pid=34)
        launch_live.request_independent_launch()
        self.assertEqual([c.args[0] for c in self.verify.call_args_list], [12, 34])
        self.assertIn(str(self.root/'scripts/start_game_task.ps1'), self.run.call_args.args[0])
        self.popen.assert_not_called()

    def test_registration_failure_never_falls_back_to_child_launch(self):
        self.run.return_value.returncode = 1
        self.run.return_value.stderr = b'Access denied'
        with self.assertRaisesRegex(RuntimeError, 'registration failed'):
            launch_live.request_independent_launch()
        self.popen.assert_not_called()

    def test_worker_failure_propagates(self):
        self.state(state='failed', updated_at_epoch=200, error='Save path mismatch')
        with patch.object(launch_live.time, 'time', return_value=100):
            with self.assertRaisesRegex(RuntimeError, 'Save path mismatch'):
                launch_live.request_independent_launch()
        self.popen.assert_not_called()

    def test_stale_ready_cannot_claim_success_or_kill_existing_process(self):
        self.state(state='ready', game_pid=12, worker_pid=34)
        self.verify.side_effect = ValueError('dead process')
        with patch.object(launch_live.time, 'monotonic', side_effect=[0, 1, 112]), \
             patch.object(launch_live.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'confirmation timed out'):
                launch_live.request_independent_launch()
        self.popen.assert_not_called()

    def test_default_main_checks_original_then_delegates(self):
        (self.private/'live/isolation.json').write_text('{}')
        with patch.object(sys, 'argv', ['launch_live.py']), \
             patch.object(launch_live, 'check_original', return_value={'ok': True}), \
             patch.object(launch_live, 'request_independent_launch') as request:
            launch_live.main()
            request.assert_called_once()
        self.popen.assert_not_called()
