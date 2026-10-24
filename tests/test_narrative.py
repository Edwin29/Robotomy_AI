import tempfile
import unittest
from unittest.mock import patch
from robotomy.mcp_server import create_server
from robotomy.live import _ui_items
from robotomy.perception import panel_rows


class NarrativeTests(unittest.IsolatedAsyncioTestCase):
    async def test_story_wait_does_not_block_for_facility_events(self):
        with tempfile.TemporaryDirectory() as root:
            server = create_server(root)
            with patch('robotomy.live.LiveReader._read', return_value=({}, {'scene':'Story'})):
                result = await server.call_tool('wait_for_event', {'conditions':['meltdown_cycle'], 'timeout_s':20})
            self.assertIn('not_applicable', str(result))

    async def test_input_can_return_image_in_same_response(self):
        with tempfile.TemporaryDirectory() as root:
            server = create_server(root)
            with patch('robotomy.quick_input.QuickInput.input', return_value={'status':'input_sent','at':'2026-10-20T00:00:00+00:00'}), \
                 patch('robotomy.live.LiveReader.frame_after', return_value=({'status':'live'}, b'fixture')), \
                 patch('robotomy.mcp_server.record', return_value={}):
                result = await server.call_tool('game_input', {'command':['L',[10,20]], 'include_frame':True})
            self.assertIn('image/png', str(result))

    def test_research_visible_text_and_gestures_survive_reader(self):
        rows = [
            dict(text='Visible research', panel='research',row_id='12',role='name',x=1,y=2,width=4,height=6),
            dict(text='',panel='research',row_id='12',role='drag_start',x=10,y=20,width=40,height=60)]
        parsed = _ui_items(rows, 100)
        self.assertEqual(panel_rows({'ui_texts':parsed},'research'),
                         {'12':{'name':'Visible research','drag_start':{'x':30,'y':50}}})
