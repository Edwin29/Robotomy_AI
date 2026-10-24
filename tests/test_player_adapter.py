"""Contract cases; runtime replay evidence is separate."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from robotomy.combat import CombatDelivery,validate_combat
from robotomy.quick_input import resolve,TargetError
from robotomy.player_adapter import PlayerAdapter
from robotomy.perception import Delivery


def sample(n=1):
 return dict(process_id=1,scene='Main',sequence=n,captured_at_utc='2026-10-23T00:00:00Z',screen={'width':100,'height':100},ui_texts=[],buttons=[],console={'session':'a'*32,'signal_epoch':1})

def event(i,subject='unit:a',value='5',t=None):
 return dict(id=i,kind='damage_display',at='2026-10-23T00:00:00Z',game_time=2,real_time=t or i*.1,frame=i,subject=subject,type='RED',display=value,position={'x':50,'y':50})


class CombatTests(unittest.TestCase):
 def test_transients_group_once_and_unknown_never_merge(self):
  d=CombatDelivery();s=sample();s['console']['combat']=validate_combat({'latest_id':4,'events':[event(1),event(2),event(3,None),event(4,None)]})
  r=d.offer(s);self.assertEqual([g['count'] for g in r['damage']],[2,1,1]);self.assertEqual(r['damage'][0]['sum_displayed'],10)
  self.assertEqual(d.offer(s)['damage'],[]);self.assertEqual(len(d.read()['events']),4)
 def test_immunity_not_fabricated_zero_and_gap_explicit(self):
  d=CombatDelivery();s=sample();s['console']['combat']={'latest_id':1,'events':[event(1,value=None)]}
  r=d.offer(s);self.assertEqual(r['damage'][0]['numeric_count'],0);self.assertIsNone(r['damage'][0]['max_displayed'])
  s['console']['combat']={'latest_id':10,'events':[event(10)]};self.assertTrue(d.offer(s)['gap'])
 def test_unknown_fields_do_not_leak(self):
  e={**event(1),'attack_timer':.63,'hidden_hp':5};out=validate_combat({'latest_id':1,'events':[e]})['events'][0]
  self.assertNotIn('hidden_hp',out);self.assertNotIn('attack_timer',out)
 def test_journal_pages_ignore_incomplete_tail(self):
  from robotomy.combat import read_journal
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'.robotomy/live';path.mkdir(parents=True)
   (path/('combat-'+'a'*32+'.jsonl')).write_text('\n'.join(json.dumps(event(i)) for i in (1,2,3))+'\n{"id":4',encoding='utf8')
   first=read_journal(td,'a'*32,0,2);self.assertTrue(first['more']);self.assertEqual(first['next'],2)
   self.assertEqual([e['id'] for e in read_journal(td,'a'*32,2)['events']],[3])
 def test_projectiles_compact_without_claiming_impact(self):
  d=CombatDelivery();s=sample();s['console']['combat']={'latest_id':3,'events':[{**event(i),'kind':'projectile_display','subject':'visual:a','state':'moving' if i<3 else 'left_view'} for i in (1,2,3)]}
  r=d.offer(s);self.assertEqual(len(r['projectiles']),1);self.assertEqual(r['projectiles'][0]['state'],'left_view');self.assertEqual(len(d.read()['events']),3)
 def test_restart_resets_and_motion_relation_is_not_attacker(self):
  d=CombatDelivery();s=sample();motion={**event(1),'kind':'motion_changed','motion':'motion:1'}
  s['console']['combat']={'latest_id':2,'events':[motion,event(2)]};d.offer(s)
  self.assertEqual(d.read()['relations'][0]['basis'],'temporal_spatial_only')
  s['console']['signal_epoch']=2;s['console']['combat']={'latest_id':2,'events':[]};d.offer(s)
  self.assertEqual(d.read()['events'],[])


class AdapterTests(unittest.TestCase):
 def test_embedded_state_prevents_cross_call_identity_mismatch(self):
  with tempfile.TemporaryDirectory() as td:
   reader=Mock();reader._delivery=Delivery();r=reader._delivery.offer(sample());r['_adapter_state']=copy.deepcopy(reader._delivery.state);r['_adapter_identity']=reader._delivery.identity
   reader._delivery.state['employees']={'later':{'name':'later','ref':'unit:later'}}
   a=PlayerAdapter(Path(td),reader,Mock());result=a.pack(r)
   self.assertNotIn('employees',result['updated'])
 def test_current_frame_crop_uses_validated_snapshot_not_tuple(self):
  from unittest.mock import patch
  from tests.test_live import LiveReaderTests
  from PIL import Image
  import io,hashlib
  fixture=LiveReaderTests();fixture.setUp();self.addCleanup(fixture.temp.cleanup)
  root=fixture.root;reader=fixture.reader;fixture.publish();snapshot=fixture.obj
  buf=io.BytesIO();Image.new('RGB',(1280,720)).save(buf,format='PNG');data=buf.getvalue()
  (reader.directory/'frame-motion.json').write_text(json.dumps({'sha256':hashlib.sha256(data).hexdigest(),'session':None,'snapshot':snapshot}),encoding='utf8')
  a=PlayerAdapter(root,reader,Mock())
  with patch.object(reader,'frame_after',return_value=({},data)),patch('robotomy.quick_input.resolve',return_value={'x':50,'y':50}):
   rows=a.images('fixture');self.assertEqual(len(rows),1);self.assertEqual(rows[0][0]['crop'][:2],[0,0])
 def test_compact_rows_retain_identity_and_removal_reason(self):
  with tempfile.TemporaryDirectory() as td:
   reader=Mock();reader._delivery=Delivery();a=PlayerAdapter(Path(td),reader,Mock());s=sample();r=reader._delivery.offer(s)
   reader._delivery.state['employees']={'a':{'ref':'unit:a','name':'브룩','position':{'x':1,'y':2}}}
   first=a.pack(r);self.assertEqual(first['updated']['employees'][0]['name'],'브룩')
   reader._delivery.state['employees']={};second=a.pack(r)
   self.assertEqual(second['left_view']['employees'][0]['reason'],'no_longer_observed')
 def test_stable_ref_prefers_displayed_row_but_move_can_select_body(self):
  from unittest.mock import patch
  rows=[{'ref':'unit:a','label':'브룩','kind':'employee','x':1,'y':1},{'ref':'unit:a','label':'브룩','kind':'row','x':50,'y':50}]
  with patch('robotomy.quick_input.targets',return_value=rows):
   self.assertEqual(resolve({},'unit:a')['kind'],'row');self.assertEqual(resolve({},'unit:a','employee')['kind'],'employee')
 def test_ambiguous_error_gives_candidates(self):
  from unittest.mock import patch
  with patch('robotomy.quick_input.targets',return_value=[{'ref':'a','kind':'button','label':'X','x':1,'y':1},{'ref':'b','kind':'button','label':'X','x':2,'y':2}]):
   with self.assertRaises(TargetError) as caught:resolve({},'X')
   self.assertEqual(len(caught.exception.detail['candidates']),2)
 def test_request_id_never_replays_uncertain_input(self):
  with tempfile.TemporaryDirectory() as td:
   reader=Mock();reader.brief.return_value={'status':'unavailable'};reader._delivery=None;q=Mock();q.input.return_value={'status':'unknown'}
   a=PlayerAdapter(Path(td),reader,q);item={'kind':'input','command':['K','Space']}
   a.action(item,'same');a.action(item,'same');self.assertEqual(q.input.call_count,1)
   with self.assertRaises(ValueError):a.action({'kind':'input','command':['K','D']},'same')
 def test_schedule_validates_all_before_start(self):
  a=PlayerAdapter(Path('.'),Mock(),Mock())
  with self.assertRaises(ValueError):a.schedule([{'kind':'input','command':['K','Space']},{'kind':'state','setting':'speed','value':3}])
  a.quick.executor._snapshot.assert_not_called()
 def test_schedule_stops_before_second_input_after_scene_or_pause_barrier(self):
  import time
  for change in ('scene','pause'):
   with tempfile.TemporaryDirectory() as td:
    s=sample();q=Mock();q.executor._snapshot.side_effect=lambda:copy.deepcopy(s)
    a=PlayerAdapter(Path(td),Mock(),q)
    def first(*args,**kwargs):
     if change=='scene':s['scene']='NewTitleScene'
     else:
      p=Path(td)/'.robotomy/live/control/pause-generation';p.parent.mkdir(parents=True);p.write_text('new')
     return {'action':{'dispatch':'input_sent'}}
    a.action=Mock(side_effect=first)
    job=a.schedule([{'kind':'input','command':['K','Space']}]*2)
    for _ in range(100):
     if a.jobs[job['id']]['status']!='running':break
     time.sleep(.01)
    self.assertEqual(a.action.call_count,1)
    self.assertEqual(a.jobs[job['id']]['status'],'context_changed' if change=='scene' else 'pause_barrier')

if __name__=='__main__':unittest.main()
