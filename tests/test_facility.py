import json
import tempfile
import unittest
from pathlib import Path
from robotomy.facility import atlas,decode,resolve,read_map,entity_location
from robotomy.live import visible_entities,observation_sections,observation_diff

class FacilityTest(unittest.TestCase):
 def data(self):
  return {'known':{'version':1,'landmarks':[{'id':'corridor:1:2','kind':'corridor','x':1,'y':2}]},'visible':[{'id':'corridor:1:2','kind':'corridor','position':{'x':10,'y':20},'click':{'x':12,'y':20,'button':'right'}}]}
 def test_status_is_visible_only_and_diff_replaces_it(self):
  d=self.data();d['visible'][0]['status']={'warning_light':'red','surface_effects':[{'visual_id':'surface-1234abcd','label':'hidden cause','hidden_damage':99}]}
  a=decode(d,{'width':100,'height':100});state=a['visible'][0]['status']
  self.assertEqual(state['warning_light'],'red');self.assertEqual(state['surface_effects'],[{'visual_id':'surface-1234abcd','appearance':'unclassified','label':'미분류 표면 효과'}])
  self.assertNotIn('status',a['known']['landmarks'][0])
  d['visible']=[];b=decode(d,{'width':100,'height':100});self.assertEqual(b['visible'],[])
  prev={'id':'a','identity':'same','selection':{},'captured_at_utc':'2026-10-19T00:00:00Z','sections':observation_sections({'facility_map':a})}
  diff=observation_diff(prev,{'captured_at_utc':'2026-10-19T00:00:01Z','facility_map':b},'b',{},'same')
  self.assertEqual(diff['replacements']['/facility_map'],b)
 def test_no_warning_is_not_no_enemies(self):
  d=self.data();d['visible'][0]['status']={'warning_light':None,'surface_effects':[]}
  self.assertIsNone(decode(d,{'width':100,'height':100})['visible'][0]['status']['warning_light'])
 def test_location_preserves_continuous_coordinates_and_requires_current_facility(self):
  fm=decode(self.data(),{'width':100,'height':100});loc={'facility_id':'corridor:1:2','relative':{'u':.271,'v':.433},'map_position':{'x':1.2,'y':2.3}}
  snap={'console':{'facility_map':fm}};self.assertEqual(entity_location({'facility_location':loc},snap)['relative']['u'],.271)
  fm['visible']=[];self.assertIsNone(entity_location({'facility_location':loc},snap))
 def test_appearance_uses_visual_labels_only(self):
  d=self.data();d['visible'][0]['status']={'warning_light':'off','surface_effects':[{'visual_id':'surface-1234abcd','appearance':'flames_embers','cause':'hidden'}]}
  e=decode(d,{'width':100,'height':100})['visible'][0]['status']['surface_effects'][0]
  self.assertEqual(e['label'],'불꽃·불티');self.assertNotIn('cause',e)
 def test_fixed_id_resolves_current_camera(self):
  d=self.data();a=decode(d,{'width':100,'height':100});d['visible'][0]['click']['x']=80;b=decode(d,{'width':200,'height':100})
  self.assertEqual(a['known'],b['known']);self.assertEqual(resolve({'console':{'facility_map':b}},'corridor:1:2')['x'],80)
 def test_offscreen_locked_or_covered_never_uses_history(self):
  d=self.data();d['visible']=[];v=decode(d,{'width':100,'height':100})
  self.assertEqual(len(v['known']['landmarks']),1)
  with self.assertRaises(ValueError):resolve({'console':{'facility_map':v}},'corridor:1:2')
 def test_persistence_is_geometry_not_live_state(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'.robotomy/live';p.mkdir(parents=True);d=self.data()['known'];d['landmarks'][0].update(click={'x':9,'y':9},hp=100)
   (p/'facility-map.json').write_text(json.dumps(d));m=read_map(folder)
   self.assertEqual(m['status'],'remembered');self.assertNotIn('click',m['landmarks'][0]);self.assertNotIn('hp',m['landmarks'][0])
 def test_invalid_or_unknown_anchor_rejected(self):
  d=self.data();d['visible'][0]['id']='hidden'
  with self.assertRaises(ValueError):decode(d,{'width':100,'height':100})
  d=self.data();d['known']['landmarks'][0]['x']=float('nan')
  with self.assertRaises(ValueError):atlas(d['known'])
 def test_connection_is_not_inferred_from_proximity(self):
  d={'version':1,'landmarks':[{'id':'a','kind':'corridor','x':0,'y':10},{'id':'b','kind':'elevator','x':2,'y':0},{'id':'c','kind':'main_room','x':3,'y':0}], 'connections':[{'a':'a','b':'b'}]}
  m=atlas(d);self.assertEqual(m['landmarks'][0]['connections'][0]['direction'],'down_right')
  self.assertEqual(m['landmarks'][2]['connections'],[])
  self.assertEqual(m['layout_top_to_bottom'][1]['spaces'],['b','c'])
  d['connections'].append({'a':'b','b':'hidden'})
  with self.assertRaises(ValueError):atlas(d)
 def test_entity_expiry_and_diff(self):
  t={'track_id':'a','entity':{'kind':'creature','name':None},'position':{'x':3,'y':4},'bounds':{},'state':'tracking','object_velocity':{'x':1,'y':0},'screen_velocity':{'x':2,'y':0},'camera_velocity':{'x':1,'y':0}}
  s={'console':{'motion':{'status':'available','tracks':[t]}}};r=visible_entities(s);self.assertEqual(r[0]['object_velocity']['x'],1)
  s['console']['motion']['status']='expired';self.assertEqual(visible_entities(s),[])
  p={'id':'a','identity':'same','selection':{},'captured_at_utc':'2026-10-19T00:00:00Z','sections':observation_sections({'visible_entities':r})}
  d=observation_diff(p,{'captured_at_utc':'2026-10-19T00:00:01Z','visible_entities':[]},'b',{},'same');self.assertEqual(d['replacements']['/visible_entities'],[])

if __name__=='__main__':unittest.main()
