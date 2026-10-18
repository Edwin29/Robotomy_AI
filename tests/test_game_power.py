import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from robotomy.game_power import GamePower

class PowerTests(unittest.TestCase):
    def test_running_does_not_launch_or_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); stop=root/'.robotomy/live/control/PAUSED'
            stop.parent.mkdir(parents=True);stop.write_text('operator stop')
            with patch('robotomy.game_power.LiveReader') as reader, patch('robotomy.game_power.verify_process'), patch('robotomy.game_power.subprocess.Popen') as popen:
                reader.return_value.status.return_value={'status':'stale','process_id':123}
                result=GamePower(root).start()
                self.assertEqual(result['status'],'running');self.assertFalse(result['input_enabled'])
                popen.assert_not_called();self.assertEqual(stop.read_text(),'operator stop')

    def test_start_is_fixed_nonblocking_and_not_duplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('robotomy.game_power.verify_process',side_effect=ValueError()), patch('robotomy.game_power.subprocess.Popen') as popen:
                popen.return_value.poll.return_value=None
                power=GamePower(tmp)
                self.assertEqual(power.start()['status'],'starting')
                self.assertEqual(power.start()['status'],'starting')
                self.assertEqual(popen.call_count,1)
                self.assertEqual(popen.call_args.args[0][-1],str(Path(tmp)/'scripts/launch_live.py'))
                self.assertEqual(power.close()['status'],'starting')

    def test_unverified_close_never_sends_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('robotomy.game_power.configure',side_effect=ValueError('identity mismatch')), patch('robotomy.game_power.ctypes.WinDLL') as api:
                with self.assertRaises(ValueError): GamePower(tmp).close()
                api.assert_not_called()

    def test_pending_input_blocks_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            pending=Path(tmp)/'.robotomy/live/control/virtual-command.txt'
            pending.parent.mkdir(parents=True);pending.write_text('pending')
            with patch('robotomy.game_power.configure') as window:
                with self.assertRaisesRegex(ValueError,'pending'): GamePower(tmp).close()
                window.assert_not_called()

    def test_missing_process_is_stopped_not_stale(self):
        with tempfile.TemporaryDirectory() as tmp, patch('robotomy.game_power.verify_process',side_effect=ValueError()):
            self.assertEqual(GamePower(tmp).status()['status'],'stopped')
    def test_launcher_process_check_handles_localized_bytes(self):
        from scripts.prepare_live import assert_game_stopped
        with patch('scripts.prepare_live.subprocess.check_output',return_value='정보: 없음'.encode('cp949')):
            assert_game_stopped()
        with patch('scripts.prepare_live.subprocess.check_output',return_value=b'"LobotomyCorp.exe","123"'):
            with self.assertRaises(RuntimeError): assert_game_stopped()
