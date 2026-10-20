import unittest
from robotomy.live import _ui_items,reading_panels,observation_diff,observation_sections

def item(text,role,panel='ego',row='1',**extra):
 return dict(text=text,role=role,panel=panel,row_id=row,x=10,y=10,width=20,height=10,**extra)
class ReadingTest(unittest.TestCase):
 def test_only_disclosed_fields_and_slots(self):
  raw=[item('참회','name'),item('WHITE','damage_type'),item('5-7','damage'),item('에덴','owner'),item('secret','internal_id')]
  texts=_ui_items(raw,100);self.assertNotIn('role',texts[-1])
  buttons=_ui_items([item('에덴','equipment_slot',interactable=True,input_verified=True,target_id='a',hit_x=15,hit_y=15)],100,True)
  rows=reading_panels(dict(ui_texts=texts,buttons=buttons))['equipment_rows'];self.assertEqual(rows[0]['owners'],['에덴']);self.assertEqual(rows[0]['damage'],'5-7');self.assertNotIn('internal_id',rows[0]);self.assertEqual(rows[0]['actions'][0]['x'],15)
 def test_record_order_and_paragraphs(self):
  texts=_ui_items([item('첫 줄','line','creature_record','p1'),item('둘째 줄','line','creature_record','p1'),item('다음 문단','line','creature_record','p2')],100)
  self.assertEqual(reading_panels({'ui_texts':texts})['creature_record'],[{'paragraph_id':'p1','text':'첫 줄\n둘째 줄'},{'paragraph_id':'p2','text':'다음 문단'}])
 def test_closed_window_does_not_retain_rows(self):
  self.assertEqual(reading_panels({'ui_texts':[],'buttons':[]}),{'equipment_rows':[],'equipment_controls':[],'creature_record':[],'selected_equipment':None})
 def test_diff_unchanged_and_retract(self):
  s={'captured_at_utc':'2026-10-19T00:00:00+00:00',**reading_panels({'ui_texts':[item('참회','name')]})}
  previous={'captured_at_utc':s['captured_at_utc'],'id':'o1','identity':'same','selection':{},'sections':observation_sections(s)}
  d=observation_diff(previous,s,'o2',{},'same');self.assertTrue(d['no_structured_changes'])
  closed={**s,**reading_panels({})};d=observation_diff(previous,closed,'o3',{},'same');self.assertEqual(d['replacements']['/equipment_rows'],[])
 def test_selected_card_replaced_without_stale_fields(self):
  def snap(fields):return {'captured_at_utc':'2026-10-19T00:00:00+00:00',**reading_panels({'ui_texts':_ui_items([item(v,k,row='selected') for k,v in fields.items()],100)})}
  old=snap({'selected_name':'A','weapon_name':'W','suit_name':'S','hidden_model':'secret'})
  self.assertEqual(old['selected_equipment'],{'selected_name':'A','weapon_name':'W','suit_name':'S'})
  new=snap({'selected_name':'B','weapon_name':'Default'})
  p={'id':'a','identity':'same','selection':{},'sections':observation_sections(old),'captured_at_utc':old['captured_at_utc']}
  d=observation_diff(p,new,'b',{},'same');self.assertEqual(d['replacements']['/selected_equipment'],{'selected_name':'B','weapon_name':'Default'})
  self.assertEqual(observation_diff(p,snap({}),'c',{},'same')['replacements']['/selected_equipment'],None)
if __name__=='__main__':unittest.main()
