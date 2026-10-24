import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from robotomy.live import _hazards
from robotomy.perception import Delivery
from robotomy.realtime import Realtime


class RoomNarrationTests(unittest.TestCase):
    def test_current_text_is_retracted_in_diff(self):
        row={'room_id':'1','room_label':'shown name','x':10,'y':20,
             'work_narration':'화면에 표시된 문구','hidden_story':'must not escape'}
        clean=_hazards({'room_status':[row]}, {'width':100,'height':100})
        self.assertNotIn('hidden_story',str(clean))
        s={'process_id':1,'scene':'Main','screen':{'width':100,'height':100},
           'sequence':1,'captured_at_utc':'2026-10-21T00:00:00Z','console':{'hazards':clean},'ui_texts':[],'buttons':[]}
        d=Delivery();d.offer(s)
        s=copy.deepcopy(s);s['sequence']=2;s['console']['hazards']['room_status'][0]['work_narration']=None
        delta=d.offer(s)
        self.assertIn({'set':['hazards','room_status','1','work_narration'],'value':None},delta['priority_changes'])

    def test_observed_event_survives_text_disappearing_without_repeat_or_pause(self):
        with tempfile.TemporaryDirectory() as root:
            r=Realtime(Path(root),Mock(),Mock())
            s={'process_id':1,'scene':'Main','sequence':1,'captured_at_utc':'2026-10-21T00:00:00Z',
               'console':{'signals':[],'signal_epoch':1}}
            r.ingest(s)
            event={'id':1,'kind':'room_narration','at':s['captured_at_utc'],'text':'shown','room_id':'12','room_label':'display name'}
            s['sequence']=2;s['console']['signals']=[event];r.ingest(s)
            s['sequence']=3;r.ingest(s)
            s['sequence']=4;s['console']['signals']=[];r.ingest(s)
            rows=[e for e in r.events if e['kind']=='room_narration']
            self.assertEqual(len(rows),1)
            self.assertEqual((rows[0]['text'],rows[0]['room_id'],rows[0]['room_label']),('shown','12','display name'))
            self.assertFalse(r.pending.exists())


if __name__=='__main__':unittest.main()
