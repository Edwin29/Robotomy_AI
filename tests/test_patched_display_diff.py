import unittest,copy
from robotomy.live import observation_sections,observation_diff
class PatchedDisplayDiffTests(unittest.TestCase):
 def test_all_new_displays_and_removals_roundtrip(self):
  old={'captured_at_utc':'2026-10-19T00:00:00+00:00','equipment_rows':[{'owners':['A']}],'equipment_controls':[{'target_id':'1'}],'playback':{'state':'paused'},'command_rows':[{'name':'A','hp':'10/20'}],'creature_record':[{'text':'old'}],'console':{'hazards':{'room_status':[{'stored_pe_boxes':10,'work_boxes':{'pe_boxes':1,'ne_boxes':0}}],'creature_management':{'details':[{'kind':'work_preference','I':'낮음'}]},'ordeal':{'label':'녹빛 여명'},'meltdown_gauge':{'label':'1/3'}},'motion':{'tracks':[{'track_id':'a'}]}}}
  new=copy.deepcopy(old);new.update(equipment_rows=[{'owners':['B']}],equipment_controls=[],playback={'state':'2x'},command_rows=[],creature_record=[])
  new['console']['hazards'].update(room_status=[],creature_management=None,ordeal=None,meltdown_gauge={'label':'2/3'});new['console']['motion']['tracks']=[]
  before=observation_sections(old);p={'id':'old','identity':'same','selection':{},'sections':before,'captured_at_utc':old['captured_at_utc']};d=observation_diff(p,new,'new',{},'same')
  reconstructed=dict(before);reconstructed.update(d['replacements'])
  for k in d['removed_sections']:reconstructed.pop(k,None)
  self.assertEqual(reconstructed,observation_sections(new));self.assertIsNone(d['priority_changes']['creature_management']);self.assertEqual(d['priority_changes']['room_status'],[])
  self.assertEqual(d['replacements']['/equipment_rows'][0]['owners'],['B']);self.assertEqual(d['replacements']['/equipment_controls'],[])
  p.update(id='new',sections=reconstructed);self.assertTrue(observation_diff(p,new,'next',{},'same')['no_structured_changes'])
