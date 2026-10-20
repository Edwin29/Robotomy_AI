import unittest
from robotomy.live import visible_employees,observation_sections,observation_diff,_motion,dead_employees

class VisibleEmployeeTests(unittest.TestCase):
 def test_semantic_state_is_independent_of_pause_and_camera(self):
  s=self.snapshot();s['console']['motion']['tracks'][0]['employee']['status']='working'
  e=visible_employees(s)[0];self.assertEqual(e['status_label'],'작업 중');self.assertEqual(e['movement'],'stationary')
 def test_death_exception_exposes_no_location_or_vitals(self):
  rows=dead_employees([{'employee_id':'1','name':'A','status':'dead','x':10,'hp':0,'cause':'hidden'}])
  self.assertEqual(rows,[{'employee_id':'1','name':'A','status':'dead','status_label':'사망'}])
  self.assertEqual(dead_employees([]),[])
  with self.assertRaises(ValueError):dead_employees([{'employee_id':'1','name':'A','status':'working'}])
 def snapshot(self):
  v={'x':0,'y':0}
  return {'captured_at_utc':'2026-10-19T00:00:00Z','console':{'motion':{'status':'available','tracks':[{'track_id':'a'*32,'employee':{'name':'A','condition':'unknown','click':{'x':12,'y':15}},'position':{'x':10,'y':10},'object_velocity':v,'screen_velocity':{'x':50,'y':0},'camera_velocity':{'x':50,'y':0}}]}}}
 def test_camera_motion_is_not_employee_motion(self):
  s=self.snapshot();self.assertEqual(visible_employees(s)[0]['movement'],'stationary')
  s['console']['motion']['tracks'][0]['object_velocity']={'x':-20,'y':0}
  self.assertEqual(visible_employees(s)[0]['movement'],'moving')
  s['console']['motion']['tracks'][0]['object_velocity']=None
  self.assertEqual(visible_employees(s)[0]['movement'],'unknown')
 def test_expiry_and_diff_remove_employees(self):
  s=self.snapshot();s['visible_employees']=visible_employees(s)
  old={'id':'a','identity':'x','selection':{},'sections':observation_sections(s),'captured_at_utc':s['captured_at_utc']}
  s['console']['motion']['status']='expired';s['visible_employees']=visible_employees(s)
  self.assertEqual(s['visible_employees'],[])
  self.assertEqual(observation_diff(old,s,'b',{},'x')['replacements']['/visible_employees'],[])
