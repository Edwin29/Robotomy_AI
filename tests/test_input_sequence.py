import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock
from robotomy.input_sequence import Sequences, input_lock
from robotomy.live_control import LiveControl, atomic


class SequenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.control=LiveControl(self.root)
        self.control.reader.status=Mock(return_value={'status':'live','process_id':123})
        self.view=dict(id='v1',backend='virtual_unity',captured_epoch=time.time(),process_id=123,
            width=1280,height=720,scene='Tutorial_3',bridge_id='v1',screenshot_id='s1',window_id=123)
        atomic(self.control.directory/'view.json',self.view)
        self.snapshot=dict(process_id=123,scene='Tutorial_3',screen={'width':1280,'height':720},ui_texts=[],buttons=[])
        self.executor=Mock(control=self.control)
        self.snapshot['sequence']=0
        def snapshot():
            self.snapshot['sequence']+=1
            return self.snapshot
        self.executor._snapshot.side_effect=snapshot
        self.executor.execute.return_value={'status':'input_sent'}
        self.q=Sequences(self.root,self.executor)
        self.ids=[self.control.prepare('v1',kind='key',key='d')['id'] for _ in range(3)]

    def finish(self, identity):
        for _ in range(200):
            result=self.q.status(identity)
            if result['status']!='running':
                # Worker persists final state and releases its file lock.
                time.sleep(.02)
                return result
            time.sleep(.01)
        self.fail('Worker did not finish')

    def test_order_and_single_writer(self):
        entered=threading.Event(); release=threading.Event()
        def execute(identity):
            entered.set(); release.wait(2); return {'status':'input_sent','id':identity}
        self.executor.execute.side_effect=execute
        identity=self.q.submit(self.ids)['id']; self.assertTrue(entered.wait(1))
        try:
            with self.assertRaises(ValueError):
                with input_lock(self.root): pass
            with self.assertRaises(ValueError): self.q.submit(self.ids)
            self.assertEqual(self.q.status(identity)['status'],'running')
        finally: release.set()
        self.assertEqual(self.finish(identity)['status'],'completed')
        self.assertEqual([x.args[0] for x in self.executor.execute.call_args_list],self.ids)

    def test_cancel_keeps_current_input_only(self):
        entered=threading.Event(); release=threading.Event()
        def execute(identity):
            entered.set(); release.wait(2); return {'status':'input_sent'}
        self.executor.execute.side_effect=execute
        identity=self.q.submit(self.ids)['id']; self.assertTrue(entered.wait(1))
        self.q.cancel(identity); release.set()
        self.assertEqual(self.finish(identity)['stop_reason'],'cancel_requested')
        self.assertEqual(self.executor.execute.call_count,1)

    def test_screen_change_and_unknown_stop(self):
        def execute(identity):
            self.snapshot['ui_texts']=[{'text':'new dialogue'}]
            return {'status':'input_sent'}
        self.executor.execute.side_effect=execute
        identity=self.q.submit(self.ids)['id']
        self.assertEqual(self.finish(identity)['stop_reason'],'screen_changed')
        self.assertEqual(self.executor.execute.call_count,1)
        self.executor.execute.side_effect=None
        self.executor.execute.return_value={'status':'unknown'}
        identity=self.q.submit(self.ids)['id']
        self.assertEqual(self.finish(identity)['stop_reason'],'input_not_confirmed')

    def test_verified_target_survives_menu_close(self):
        self.snapshot['buttons']=[dict(target_id='speed', input_verified=True, interactable=True,
            hit_x=310,hit_y=600,x=300,y=590,width=20,height=20,text='',panel='input_target')]
        ids=[self.control.prepare('v1',kind='click',x=310,y=600)['id'] for _ in range(2)]
        def execute(identity):
            self.snapshot['ui_texts']=[{'text':'menu closed'}]
            return {'status':'input_sent'}
        self.executor.execute.side_effect=execute
        self.assertEqual(self.finish(self.q.submit(ids)['id'])['status'],'completed')
        self.assertEqual(self.executor.execute.call_count,2)

    def test_verified_target_disappears_disabled_moves_or_replaced(self):
        for mutation in ('missing','disabled','moved','replaced','occluded'):
            with self.subTest(mutation=mutation):
                self.snapshot['buttons']=[dict(target_id='speed',input_verified=True,interactable=True,
                    hit_x=310,hit_y=600,x=300,y=590,width=20,height=20,text='',panel='input_target')]
                ids=[self.control.prepare('v1',kind='click',x=310,y=600)['id'] for _ in range(2)]
                def execute(identity):
                    b=self.snapshot['buttons'][0]
                    if mutation=='missing': self.snapshot['buttons']=[]
                    elif mutation=='disabled': b['interactable']=False
                    elif mutation=='moved': b['x']=321; b['hit_x']=331
                    elif mutation=='replaced': b['target_id']='different'
                    else: b['input_verified']=False
                    return {'status':'input_sent'}
                self.executor.execute.reset_mock(); self.executor.execute.side_effect=execute
                result=self.finish(self.q.submit(ids)['id'])
                self.assertEqual(result['stop_reason'],'target_invalid')
                self.assertEqual(self.executor.execute.call_count,1)

    def test_limits(self):
        for ids in ([],self.ids*2):
            with self.assertRaises(ValueError): self.q.submit(ids)
        ids=[self.control.prepare('v1',kind='key',key='d',duration_ms=3000)['id'] for _ in range(2)]
        with self.assertRaises(ValueError): self.q.submit(ids)

    def test_scene_transition_stops_next_input(self):
        def execute(identity):
            self.snapshot['scene']='different_scene'
            return {'status':'input_sent'}
        self.executor.execute.side_effect=execute
        identity=self.q.submit(self.ids)['id']
        self.assertEqual(self.finish(identity)['stop_reason'],'screen_changed')
        self.assertEqual(self.executor.execute.call_count,1)

    def test_receipt_preserved_if_observation_fails_after_input(self):
        def execute(identity):
            self.executor._snapshot.side_effect=ValueError('stale')
            return {'status':'input_sent','id':identity}
        self.executor.execute.side_effect=execute
        identity=self.q.submit(self.ids)['id']
        result=self.finish(identity)
        self.assertEqual(result['receipts'][0]['id'],self.ids[0])
        self.assertEqual(result['status'],'stopped')
        with input_lock(self.root): pass


class TargetTransportTests(unittest.TestCase):
    def test_verified_fields_survive_reader_validation(self):
        from robotomy.live import _ui_items
        from robotomy.input_sequence import bind_target
        button=dict(panel='input_target',text='',x=300,y=590,width=20,height=20,
                    interactable=True,target_id='opaque',input_verified=True,hit_x=310,hit_y=600)
        result=_ui_items([button],100,buttons=True)
        self.assertIsNotNone(bind_target({'buttons':result},{'kind':'click','x':310,'y':600}))
        button['hit_x']=1000
        with self.assertRaises(ValueError):_ui_items([button],100,buttons=True)
