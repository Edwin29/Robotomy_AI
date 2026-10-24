import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from robotomy.appearance import validate,attach,VisualNames
from robotomy.player_adapter import PlayerAdapter
from robotomy.perception import Delivery
def sample():return dict(process_id=1,scene='Main',sequence=1,captured_at_utc='2026-10-23T00:00:00Z',screen={'width':100,'height':100},ui_texts=[],buttons=[],console={'session':'a'*32,'signal_epoch':1})

def item(kind='mark',digit='a'):
 return {'ref':kind+':'+digit*20,'kind':kind,'label':{'form':'상태','motion':'동작','mark':'표식'}[kind]}
def appearance():return {'subject':'unit:a','room_id':'12','form':item('form'),'motions':[item('motion')],'marks':[item()]}

class AppearanceTests(unittest.TestCase):
 def test_visible_fog_label_alias_and_removal(self):
  row=appearance();row['marks'][0]['label']='검은 안개';row=validate([row])[0]
  with tempfile.TemporaryDirectory() as td:
   names=VisualNames(td);names.decorate(row)
   self.assertEqual(row['marks'][0]['label'],'검은 안개')
   names.name(row['marks'][0]['ref'],'내가 붙인 안개 이름')
   fresh=appearance();fresh['marks'][0]['label']='검은 안개';names.decorate(fresh)
   self.assertEqual(fresh['marks'][0]['alias'],'내가 붙인 안개 이름')
   state={'hazards':{'room_status':{'12':{}}}}
   attach(state,[fresh]);self.assertEqual(len(state['hazards']['room_status']['12']['appearance']['marks']),1)
   fresh['marks']=[];attach(state,[fresh]);self.assertEqual(state['hazards']['room_status']['12']['appearance']['marks'],[])
  row['marks'][0]['label']='고독 효과 발동'
  with self.assertRaises(ValueError):validate([row])

 def test_display_whitelist(self):
  row=appearance();row.update(hidden_buff='transfer',remaining=99);row['form']['hidden_phase']=3
  parsed=validate([row])[0];self.assertNotIn('hidden_buff',parsed);self.assertNotIn('hidden_phase',parsed['form'])
  row['marks'][0]['label']='damage transfer target'
  with self.assertRaises(ValueError):validate([row])
 def test_join_visible_only_and_empty_marks(self):
  state={'employees':{'a':{'ref':'unit:a'}},'entities':{},'hazards':{'room_status':{'12':{'label':'room'}}}}
  row=appearance();attach(state,[row]);self.assertEqual(state['employees']['a']['appearance']['marks'],row['marks'])
  row['marks']=[];attach(state,[row]);self.assertEqual(state['employees']['a']['appearance']['marks'],[])
  hidden={'employees':{},'entities':{},'hazards':{'room_status':{}},'creature_appearances':{}};self.assertEqual(attach(copy.deepcopy(hidden),[row]),hidden)
 def test_native_visible_presentation_without_motion_track(self):
  row=appearance();row['position']={'x':12,'y':34};state=attach({},[row]);self.assertFalse(state['creature_appearances']['a']['input_target'])
  self.assertEqual(state['creature_appearances']['a']['position'],row['position'])
  self.assertEqual(attach(state,[])['creature_appearances'],{})
 def test_name_persists_with_history_and_clears(self):
  with tempfile.TemporaryDirectory() as td:
   n=VisualNames(td);v=appearance();n.decorate(v);self.assertEqual(v['marks'][0]['label'],'표식1')
   ref=v['marks'][0]['ref'];n.name(ref,'가면','내가 붙인 이름')
   another=VisualNames(td);fresh=appearance();another.decorate(fresh);self.assertEqual(fresh['marks'][0]['alias'],'가면')
   self.assertEqual(fresh['marks'][0]['alias_source'],'player');another.name(ref,'')
   self.assertNotIn('alias',another.decorate(appearance())['marks'][0]);self.assertEqual(len(another.load()['labels'][ref]['revisions']),2)
 def test_only_offered_refs_can_be_named(self):
  with tempfile.TemporaryDirectory() as td:
   n=VisualNames(td);n.decorate(appearance(),offered=False)
   self.assertFalse(n.path.exists())
   with self.assertRaises(ValueError):n.name(item()['ref'],'가면')
 def test_two_clients_keep_names(self):
  with tempfile.TemporaryDirectory() as td:
   a=VisualNames(td);b=VisualNames(td);a.decorate(appearance());b.read();a.name(item()['ref'],'가면');b.decorate({'marks':[item('mark','b')]})
   self.assertEqual(a.read('가면')['total'],1);self.assertEqual(len(a.load()['labels']),4)
 def test_diff_does_not_repeat_and_removes_mark(self):
  with tempfile.TemporaryDirectory() as td:
   reader=Mock();reader._delivery=Delivery();raw=reader._delivery.offer(sample());reader._delivery.state['employees']={'a':{'ref':'unit:a','appearance':appearance()}}
   adapter=PlayerAdapter(Path(td),reader,Mock());first=adapter.pack(raw);self.assertEqual(len(first['updated']['employees']),1)
   self.assertNotIn('employees',adapter.pack(raw)['updated'])
   adapter.visual_names.name(item()['ref'],'가면');self.assertEqual(adapter.pack(raw)['updated']['employees'][0]['appearance']['marks'][0]['alias'],'가면')
   reader._delivery.state['employees']['a']['appearance']['marks']=[]
   self.assertEqual(adapter.pack(raw)['updated']['employees'][0]['appearance']['marks'],[])
 def test_deferred_schedule_does_not_register_or_advance_baseline(self):
  with tempfile.TemporaryDirectory() as td:
   reader=Mock();reader._delivery=Delivery();raw=reader._delivery.offer(sample());reader._delivery.state['entities']={'a':{'ref':'unit:a','appearance':appearance()}}
   adapter=PlayerAdapter(Path(td),reader,Mock());adapter.pack(raw,record_view=False)
   self.assertFalse(adapter.visual_names.path.exists());self.assertIsNone(adapter.previous)
   adapter.pack(raw);self.assertTrue(adapter.visual_names.path.exists())

if __name__=='__main__':unittest.main()
