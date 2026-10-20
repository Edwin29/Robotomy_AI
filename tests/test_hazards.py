import copy
import unittest
from robotomy.live import _hazards, observation_diff, observation_sections

class HazardTests(unittest.TestCase):
    def value(self):
        return {'ordeal':{'color':'핏빛','stage':'여명','label':'untrusted','hidden_id':123},
                'meltdown_level':'III','meltdown_gauge':{'filled':2,'max':6,'ratio':99},
                'target_rooms':None,'room_timers':[{'room_label':'???','seconds':30,'x':100,'y':200,'internal_timer':29.2}],
                'next_ordeal':'spoiler'}

    def test_only_visible_contract_and_derived_labels(self):
        h=_hazards(self.value(),{'width':1280,'height':720})
        self.assertEqual(h['ordeal'],dict(color='핏빛',stage='여명',label='핏빛 여명'))
        self.assertEqual(h['meltdown_gauge'],dict(filled=2,max=6,ratio=2/6,label='2/6'))
        self.assertNotIn('next_ordeal',h)
        self.assertNotIn('internal_timer',h['room_timers'][0])

    def test_invalid_gauge_and_offscreen_timer_rejected(self):
        for modify in (lambda h:h['meltdown_gauge'].update(filled=7),lambda h:h['room_timers'][0].update(x=1300)):
            h=self.value();modify(h)
            with self.assertRaises(ValueError):_hazards(h,{'width':1280,'height':720})

    def test_change_priority_and_visible_loss(self):
        h=_hazards(self.value(),{'width':1280,'height':720})
        s={'captured_at_utc':'2026-10-19T00:00:00Z','ui_texts':[],'console':{'hazards':h}}
        prev=dict(id='a',identity='same',selection={},sections=observation_sections(s),captured_at_utc=s['captured_at_utc'])
        now=copy.deepcopy(s);now['console']['hazards']['ordeal']=None;now['console']['hazards']['room_timers']=[]
        d=observation_diff(prev,now,'b',{},'same')
        self.assertEqual(next(iter(d)),'priority_changes')
        self.assertEqual(d['priority_changes'],{'ordeal':None,'room_timers':[]})
        self.assertEqual(d['changed_sections'][0],'/console/hazards')
        self.assertNotIn('핏빛',str(d['priority_changes']))

    def test_unchanged_hazards_not_repeated_in_priority(self):
        s={'captured_at_utc':'2026-10-19T00:00:00Z','console':{'hazards':self.value()}}
        prev=dict(id='a',identity='same',selection={},sections=observation_sections(s),captured_at_utc=s['captured_at_utc'])
        self.assertEqual(observation_diff(prev,s,'b',{},'same')['priority_changes'],{})
