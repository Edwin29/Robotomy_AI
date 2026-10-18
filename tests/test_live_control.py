import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from robotomy.live_control import LiveControl, atomic


class LiveControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.control = LiveControl(self.root)
        self.control.reader.status = Mock(return_value={'status':'live','process_id':123})
        self.view = {'id':'view1', 'captured_epoch':time.time(), 'process_id':123,
            'width':734,'height':437,'scene':'Tutorial_1','bridge_id':'bridge1',
            'screenshot_id':'shot1','window_id':12}
        self.publish()

    def publish(self): atomic(self.control.directory/'view.json', self.view)

    def decision(self):
        return self.control.prepare('view1','click','Visible tutorial target','Menu opens',100,100)

    def test_prepare_records_before_queue_and_duplicate_queue_is_idempotent(self):
        d=self.decision()
        self.assertFalse((self.control.directory/'request.json').exists())
        self.assertEqual(self.control.timeline()[0]['kind'],'decision')
        self.assertEqual(self.control.execute(d['id'])['status'],'queued')
        self.assertEqual(self.control.execute(d['id'])['status'],'queued')
        self.assertEqual(sum(e['kind']=='queued' for e in self.control.timeline()),1)

    def test_receipt_and_uncertain_claim_are_never_replayed(self):
        d=self.decision()
        atomic(self.control.directory/'claims'/f'{d["id"]}.json',{})
        self.assertEqual(self.control.execute(d['id'])['status'],'unknown')
        self.assertFalse((self.control.directory/'request.json').exists())
        receipt={'id':d['id'],'status':'input_sent'}
        atomic(self.control.directory/'receipts'/f'{d["id"]}.json',receipt)
        self.assertEqual(self.control.execute(d['id']),receipt)

    def test_pause_stale_or_changed_view_prevents_queue(self):
        d=self.decision(); self.control.pause()
        with self.assertRaisesRegex(ValueError,'paused'): self.control.execute(d['id'])
        (self.control.directory/'PAUSED').unlink()
        self.view['id']='new'; self.publish()
        with self.assertRaisesRegex(ValueError,'view changed'): self.control.execute(d['id'])
        self.view['captured_epoch']=time.time()-31; self.publish()
        with self.assertRaisesRegex(ValueError,'expired'): self.control.view()
        self.assertFalse((self.control.directory/'request.json').exists())

    def test_original_or_restarted_process_is_not_accepted(self):
        self.control.reader.status.return_value={'status':'invalid'}
        with self.assertRaises(ValueError): self.decision()
        self.control.reader.status.return_value={'status':'live','process_id':456}
        with self.assertRaisesRegex(ValueError,'Process changed'): self.decision()

    def test_disallowed_coordinates_keys_and_scroll_rejected(self):
        for x,y in ((-1,100),(100,10),(734,100),(100,float('nan'))):
            with self.assertRaises(ValueError): self.control.prepare('view1','click','why','expected',x,y)
        for key in ('Alt+F4','Control_L+l','Meta','x'):
            with self.assertRaises(ValueError): self.control.prepare('view1','key','why','expected',key=key)
        for amount in (0,601,-601,2.5):
            with self.assertRaises(ValueError): self.control.prepare('view1','scroll','why','expected',100,100,scroll_y=amount)

    def test_key_labels_normalized_without_expanding_allowlist(self):
        for label, expected in [('D','d'),('W','w'),('A','a'),('S','s'),('F','f'),
                                ('G','g'),('Space','space'),('ESCAPE','Escape'),
                                ('Enter','Return'),('RETURN','Return'),('d','d')]:
            decision=self.control.prepare('view1','key',key=label)
            self.assertEqual(decision['key'],expected)
            self.assertFalse((self.control.directory/'request.json').exists())
        for label in ('X','ALT+F4',None,[],{}):
            with self.assertRaises(ValueError): self.control.prepare('view1','key',key=label)

    def test_second_pending_command_cannot_overwrite_first(self):
        first=self.decision(); second=self.decision()
        self.control.execute(first['id'])
        with self.assertRaisesRegex(ValueError,'pending'): self.control.execute(second['id'])
        self.assertEqual(json.loads((self.control.directory/'request.json').read_text())['id'],first['id'])

    def test_resume_never_reauthorizes_old_decision(self):
        # Windows wall-clock resolution can put all three events on the same tick.
        with patch('robotomy.live_control.time.time',return_value=time.time()):
            decision=self.decision()
            self.control.pause(); self.control.resume()
            with self.assertRaisesRegex(ValueError,'predates'): self.control.execute(decision['id'])
        self.assertFalse((self.control.directory/'request.json').exists())

    def test_path_traversal_id_rejected(self):
        with self.assertRaises(ValueError): self.control.execute('../isolation')
        with self.assertRaises(ValueError): self.control.receipt('../isolation')


if __name__ == '__main__': unittest.main()
