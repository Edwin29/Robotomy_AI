import asyncio
from pathlib import Path
import tempfile
import tomllib
import unittest
import sys
from unittest.mock import patch, MagicMock

from robotomy.mcp_server import create_server
from scripts.setup_player_workspace import setup, ROOT
sys.path.insert(0,str(ROOT/'scripts'))
import prepare_player


class PlayerSetupTests(unittest.TestCase):
    def test_player_tool_surface_excludes_synthetic_and_operator_tools(self):
        with tempfile.TemporaryDirectory() as temp:
            server=create_server(Path(temp),player_only=True)
            names={tool.name for tool in asyncio.run(server.list_tools())}
            self.assertEqual(len(names),28)
            self.assertIn('hover_live_control', names)
            self.assertTrue({'submit_input_sequence','input_sequence_status','cancel_input_sequence'} <= names)
            self.assertTrue({'read_player_guide','capture_live_control','complete_day_review',
                             'read_player_memory','view_live_frame'} <= names)
            self.assertFalse({'start_session','observe','execute_decision','read_live_timeline',
                              'pause','resume','checkpoint'} & names)
            self.assertIn('read_player_guide',server.instructions)

    def test_workspace_is_external_valid_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=setup(Path(temp)/'Player')
            config=tomllib.loads((folder/'.codex/config.toml').read_text(encoding='utf-8'))
            server=config['mcp_servers']['robotomy_player']
            self.assertTrue(Path(server['command']).is_file())
            self.assertEqual(server['args'][-1],str(ROOT/'scripts/run_player_mcp.py'))
            self.assertTrue((folder/'RUN-PROMPT.md').is_file())
            (folder/'AGENTS.md').write_text('User changes',encoding='utf-8')
            with self.assertRaises(ValueError): setup(folder)
            self.assertEqual((folder/'AGENTS.md').read_text(encoding='utf-8'),'User changes')
        with self.assertRaises(ValueError): setup(ROOT/'Player')

    def test_readiness_preserves_pause_and_failed_enable_never_resumes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            control=MagicMock(); control.directory=root
            (root/'PAUSED').write_text('existing stop')
            control.reader.frame.return_value=({'process_id':123,'scene':'fixture'},b'png')
            with patch.object(prepare_player,'LiveControl',return_value=control), \
                 patch.object(prepare_player,'preflight',return_value={'ok':True}), \
                 patch.object(prepare_player,'VirtualExecutor') as executor, \
                 patch.object(prepare_player,'ensure_aspect_guard') as display, \
                 patch.object(prepare_player,'ensure_monitor',return_value='local observer'), \
                 patch('builtins.print'):
                executor.return_value._snapshot.return_value={'process_id':123,'scene':'fixture'}
                with patch.object(sys,'argv',['prepare_player']): prepare_player.main()
                control.pause.assert_not_called(); control.resume.assert_not_called()
                display.assert_not_called()
                self.assertEqual((root/'PAUSED').read_text(),'existing stop')
                (root/'request.json').write_text('unresolved command')
                with patch.object(sys,'argv',['prepare_player','--enable-input']):
                    with self.assertRaisesRegex(ValueError,'Unresolved input'): prepare_player.main()
                control.pause.assert_called_once(); control.resume.assert_not_called()
                (root/'request.json').unlink()
                with patch.object(sys,'argv',['prepare_player','--enable-input']): prepare_player.main()
                control.resume.assert_called_once()

    def test_integrity_failure_stops_before_input_enable(self):
        control=MagicMock()
        with patch.object(prepare_player,'LiveControl',return_value=control), \
             patch.object(prepare_player,'preflight',side_effect=ValueError('Integrity failed')), \
             patch.object(sys,'argv',['prepare_player','--enable-input']):
            with self.assertRaisesRegex(ValueError,'Integrity failed'): prepare_player.main()
        control.pause.assert_called_once(); control.resume.assert_not_called()
