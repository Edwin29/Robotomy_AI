import unittest
from robotomy.live import _ui_items,command_rows

class CommandRowsTests(unittest.TestCase):
 def item(self,role,text='Ed',row='42'):
  return dict(panel='command',row_id=row,role=role,text=text,x=20,y=40,width=100,height=20)
 def test_only_admitted_display_fields_and_no_model_values(self):
  raw=[self.item('name'),self.item('hp','33/33'),self.item('status','이동 중')]
  raw[0].update(CurrentAgent={'hp':999},IsOrderable=True)
  rows=command_rows({'ui_texts':_ui_items(raw,100)})
  self.assertEqual(rows[0]['name'],'Ed');self.assertEqual(rows[0]['hp'],'33/33')
  self.assertIsNone(rows[0]['sp']);self.assertIsNone(rows[0]['selectable'])
  self.assertNotIn('CurrentAgent',rows[0])
 def test_no_stale_rows_and_click_not_orderable(self):
  click={**self.item('click'), 'interactable':True}
  rows=command_rows({'buttons':_ui_items([click],100,buttons=True)})
  self.assertEqual(rows[0]['click']['x'],70);self.assertIsNone(rows[0]['selectable'])
  self.assertEqual(command_rows({'ui_texts':[],'buttons':[]}),[])
 def test_hidden_backing_fields_not_accepted(self):
  raw=[self.item('CurrentAgent.hp','999')]
  self.assertEqual(command_rows({'ui_texts':_ui_items(raw,100)}),[])
