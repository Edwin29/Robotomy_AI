import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from robotomy.quick_input import QuickInput,resolve,current
from robotomy.live import visible_employees

class QuickTests(unittest.TestCase):
 def sample(self):
  return {'process_id':1,'scene':'Main','screen':{'width':100,'height':100},'sequence':1,'captured_at_utc':'2026-10-19T00:00:00Z','ui_texts':[],
   'buttons':[{'target_id':'a','text':'통찰','input_verified':True,'interactable':True,'x':10,'y':10,'width':10,'height':10,'hit_x':15,'hit_y':15,'role':'work_type','panel':'command'}],
   'console':{'facility_map':{'known':{'landmarks':[]},'visible':[]},'motion':{'status':'available','tracks':[]}}}
 def test_alias_and_ambiguity(self):
  s=self.sample();self.assertEqual(resolve(s,'work:통찰')['x'],15);self.assertEqual(resolve(s,'통찰')['x'],15)
  s['buttons'].append({**s['buttons'][0],'target_id':'b','hit_x':50})
  with self.assertRaises(ValueError):resolve(s,'통찰')
  s['buttons']=[]
  with self.assertRaises(ValueError):resolve(s,'button:a')
 def test_current_has_no_geometry_or_raw_audio(self):
  s=self.sample();s['console']['audio_events']=[{'secret':'raw'}]
  out=current(s);self.assertNotIn('console',out);self.assertNotIn('facility_map',out)
  self.assertIn('work:통찰',[x['ref'] for x in out['targets']])
 def test_unknown_receipt_never_reexecutes(self):
  with tempfile.TemporaryDirectory() as root:
   executor=Mock();q=QuickInput(Path(root),Mock(),executor)
   result=q.finish({'status':'unknown'})
   executor.execute.assert_not_called();self.assertIsNone(result['current'])
 def test_no_frame_required_for_internal_gesture(self):
  s=self.sample();ex=Mock();ex.capture.return_value={'snapshot':s,'view':{'id':'v'}};ex.control.prepare.return_value={'id':'d'};ex.execute.return_value={'status':'input_sent'}
  q=QuickInput(Path('.'),Mock(),ex);q.gesture(s,'click',target_ref='button:a')
  ex.capture.assert_called_once_with(record_observation=False,include_frame=False)
  self.assertEqual(ex.control.prepare.call_args.kwargs['x'],15)
 def test_context_change_prevents_input(self):
  s=self.sample();ex=Mock();ex.capture.return_value={'snapshot':{**s,'scene':'Story'},'view':{'id':'v'}}
  with self.assertRaises(ValueError):QuickInput(Path('.'),Mock(),ex).gesture(s,'click',target_ref='button:a')
  ex.execute.assert_not_called()
 def test_employee_target_is_preserved_for_unity_dispatch(self):
  s=self.sample();ex=Mock();ex.capture.return_value={'snapshot':s,'view':{'id':'v'}};ex.control.prepare.return_value={'id':'d'}
  token='a'*32
  with patch('robotomy.quick_input.resolve',return_value={'ref':'employee:'+token,'kind':'employee','x':15,'y':20}):
   QuickInput(Path('.'),Mock(),ex).gesture(s,'click',target_ref='employee:'+token)
  self.assertEqual(ex.control.prepare.call_args.kwargs['employee_token'],token)
 def test_target_protocol_is_optional_and_click_only(self):
  from robotomy.virtual_input import encode_command
  d={'id':'b'*32,'process_id':1,'scene':'Main','expires_epoch':2,'kind':'click','duration_ms':80,'created_epoch':1}
  view={'width':100,'height':100}
  self.assertEqual(len(encode_command(d,view).splitlines()),16)
  targeted=encode_command(dict(d,employee_token='a'*32),view).splitlines()
  self.assertEqual(targeted[12],'v2');self.assertEqual(targeted[16],'a'*32)
  with self.assertRaises(ValueError):encode_command(dict(d,employee_token='a'*32,kind='right_click'),view)
 def test_does_not_move_when_selection_unconfirmed(self):
  with tempfile.TemporaryDirectory() as root:
   q=QuickInput(Path(root),Mock(),Mock());q.executor._snapshot.return_value=self.sample();q.gesture=Mock(return_value={'status':'input_sent'});q.wait=Mock(return_value=(self.sample(),'pending'))
   refs=[{'ref':'employee:t','x':1,'y':1},{'ref':'corridor:1:2','button':'right','x':5,'y':5}]
   with patch('robotomy.quick_input.resolve',side_effect=refs):r=q.move('a','b')
   self.assertEqual(q.gesture.call_count,1);self.assertEqual(r['status'],'stopped')
if __name__=='__main__':unittest.main()
