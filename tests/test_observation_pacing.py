import unittest
from unittest.mock import Mock
from datetime import timedelta
import test_live

class ObservationPacingTests(unittest.TestCase):
 setUp=test_live.LiveReaderTests.setUp
 publish=test_live.LiveReaderTests.publish

 def test_new_sample_returns_without_fixed_wait(self):
  self.publish()
  result=self.reader.observe(compact=True,after_sequence=self.obj['sequence']-1,wait_ms=1000)
  self.assertLess(result['waited_ms'],200)
  self.assertIn('visual_check',result)
  self.assertTrue(result['visual_check']['recommended'])

 def test_timeout_does_not_advance_offered_baseline(self):
  self.publish(); first=self.reader.observe(compact=True)
  result=self.reader.observe(compact=True,after_sequence=self.obj['sequence'],wait_ms=0)
  self.assertEqual(result['status'],'no_new_observation')
  self.assertNotIn('snapshot',result)
  self.obj['sequence']+=1;self.publish()
  self.assertEqual(self.reader.observe(compact=True)['change_summary']['base_observation_id'],first['observation_id'])

 def test_frame_wait_never_returns_pre_action_image(self):
  old={'status':'live','frame_captured_at_utc':'2026-10-18T00:00:00Z'}
  new={**old,'frame_captured_at_utc':'2026-10-18T00:00:01Z'}
  self.reader.frame=Mock(side_effect=[(old,b'old'),(new,b'new')])
  result,data=self.reader.frame_after('2026-10-18T00:00:00Z',wait_ms=100)
  self.assertEqual(data,b'new')
  self.reader.frame=Mock(return_value=(old,b'old'))
  result,data=self.reader.frame_after('2026-10-18T00:00:00Z',wait_ms=0)
  self.assertEqual(result['status'],'no_new_frame');self.assertIsNone(data)

 def test_wait_limits(self):
  for value in (-1,1001,True):
   with self.assertRaises(ValueError):self.reader.observe(wait_ms=value)
  for value in (-1,2001,True):
   with self.assertRaises(ValueError):self.reader.frame_after(wait_ms=value)

 def test_scene_change_does_not_wait_for_old_sequence(self):
  self.publish(); self.reader.observe(compact=True)
  old=self.obj['sequence']; self.obj['scene']='StoryV2';self.obj['sequence']=0;self.publish()
  result=self.reader.observe(compact=True,after_sequence=old,wait_ms=0)
  self.assertEqual(result['change_summary']['mode'],'reset')
  self.assertIn('story_or_other_scene',result['visual_check']['reasons'])
