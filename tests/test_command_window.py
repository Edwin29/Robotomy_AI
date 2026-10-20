import unittest
from robotomy.live import _ui_items, command_window, command_rows, observation_diff, observation_sections

def item(text, role, row, **extra):
    return dict(panel='command', text=text, role=role, row_id=row, x=10, y=20, width=40, height=20, **extra)

class CommandWindowTest(unittest.TestCase):
    def test_rendered_unknown_ranges_and_all_text(self):
        raw=[item('Unknown','max_pe_boxes','summary'),item('8 - 10','pe_range','result_good'),
             item('Unknown','pe_range','result_bad'),item('작업 결과','display_text','window'),
             item('에덴','name','32'),item('높음','success_rate','32'),item('21','work_time','32')]
        s={'ui_texts':_ui_items(raw,100),'buttons':[]};w=command_window(s)
        self.assertEqual(w['summary']['max_pe_boxes'],'Unknown')
        self.assertEqual(w['work_results'],[{'result':'good','pe_range':'8 - 10'},{'result':'bad','pe_range':'Unknown'}])
        self.assertEqual(len(w['employees']),1)
        self.assertEqual(sum(len(g['fields']) for g in w['text_groups']),len(raw))
    def test_verified_points_and_disabled_selection(self):
        raw=[item('본능','work_type','work_1',interactable=True,input_verified=True,target_id='1',hit_x=15,hit_y=25),
             item('통찰','work_type','work_2',interactable=False,input_verified=False),
             item('에덴','click','32',interactable=True,input_verified=True,target_id='32',hit_x=17,hit_y=28)]
        s={'buttons':_ui_items(raw,100,True)};w=command_window(s)
        self.assertEqual(w['work_types'][0]['click']['x'],15)
        self.assertIsNone(w['work_types'][1]['click'])
        self.assertEqual(w['employees'][0]['click']['y'],28)
        self.assertEqual(len(command_rows(s)),1)
    def test_close_retracts_and_diff_reconstructs(self):
        old={'command_window':command_window({'ui_texts':[item('A','name','summary')]})}
        new={'command_window':command_window({}),'captured_at_utc':'2026-10-19T00:00:00+00:00'}
        prev={'id':'a','identity':'same','selection':{},'sections':observation_sections(old),'captured_at_utc':'2026-10-19T00:00:00+00:00'}
        d=observation_diff(prev,new,'b',{},'same')
        self.assertIsNone(d['replacements']['/command_window'])

if __name__=='__main__':unittest.main()
