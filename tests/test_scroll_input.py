import sys,unittest,tempfile
from pathlib import Path
from unittest.mock import Mock
from robotomy.quick_input import QuickInput,scroll_command,targets
from robotomy.player_adapter import PlayerAdapter,model_state
class ScrollTests(unittest.TestCase):
 def test_bounds_and_sign(self):
  self.assertEqual(scroll_command(['S',[10,20],-5]),([10,20],-600))
  for n in [0,6,-6,True,1.5]:
   with self.assertRaises(ValueError):scroll_command(['S',[10,20],n])
 def test_one_gesture_then_result(self):
  with tempfile.TemporaryDirectory() as td:
   q=QuickInput(Path(td),Mock(),Mock());q.executor._snapshot.return_value={}
   q.gesture=Mock(return_value={'status':'input_sent'});q.finish=Mock(return_value={'observation':'new'})
   self.assertEqual(q.input(['S',[10,20],2]),{'observation':'new'})
   q.gesture.assert_called_once_with({},'scroll',target_ref=None,x=10,y=20,scroll_y=240)
 def test_current_management_target_only(self):
  self.assertFalse(any(r['ref']=='management:list' for r in targets({})))
  s={'console':{'hazards':{'creature_management':{'details':[{'kind':'management_tip','label':'tip','x':40,'y':50}]}}}}
  self.assertEqual(next(r for r in targets(s) if r['ref']=='management:list')['x'],40)
 def test_adapter_accepts_and_empty_closes(self):
  a=PlayerAdapter(Path('.'),Mock(),Mock());a.validate({'kind':'input','command':['S','management:list',-3]})
  self.assertIsNone(model_state({})['management_tips'])
if __name__=='__main__':unittest.main()
