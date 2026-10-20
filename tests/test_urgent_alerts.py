import unittest
from robotomy.live import urgent_alerts

class AlertTests(unittest.TestCase):
    def test_preview_and_gauge_are_not_active_meltdowns(self):
        s={'console':{'hazards':{'ordeal':{'label':'호박색 여명'},'target_rooms':4,
           'meltdown_gauge':{'filled':5,'max':5},'room_timers':[]}}}
        self.assertEqual(urgent_alerts(s),[])
    def test_visible_countdowns_sorted_including_zero(self):
        s={'captured_at_utc':'t','console':{'hazards':{'room_timers':[
          {'room_label':'A','seconds':40},{'room_label':None,'seconds':0}]}}}
        a=urgent_alerts(s)[0]
        self.assertEqual(a['min_remaining_seconds'],0)
        self.assertIsNone(a['visible_rooms'][0]['room'])
        self.assertEqual(a['captured_at_utc'],'t')
    def test_no_stale_warning_after_visibility_loss(self):
        self.assertEqual(urgent_alerts({'console':{}}),[])
        self.assertEqual(urgent_alerts({}),[])
