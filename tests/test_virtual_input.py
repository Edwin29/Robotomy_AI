import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from robotomy.live_control import atomic
from robotomy.virtual_input import VirtualExecutor, encode_command, read_json


class VirtualInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.executor = VirtualExecutor(self.root)
        self.control = self.executor.control
        self.control.reader.status = Mock(return_value={'status':'live','process_id':123})
        self.view = {'id':'v1','backend':'virtual_unity','captured_epoch':time.time(),
                     'process_id':123,'width':1280,'height':720,'scene':'Tutorial_3',
                     'bridge_id':'virtual_unity_v1','screenshot_id':'s1','window_id':123}
        atomic(self.control.directory/'view.json',self.view)

    def decision(self, **kw):
        return self.control.prepare('v1',rationale='visible target',expected='observed change',**kw)

    def hover_frame(self, **changes):
        from datetime import datetime, timezone
        meta = dict(status='live', process_id=123, scene='Tutorial_3',
                    frame_captured_at_utc=datetime.fromtimestamp(time.time()+2, timezone.utc).isoformat())
        meta.update(changes)
        data = b'\x89PNG\r\n\x1a\n' + b'\0'*8 + (1280).to_bytes(4, 'big') + (720).to_bytes(4, 'big')
        return meta, data

    def test_scroll_explains_delta_without_silently_rescaling(self):
        for amount, notches in [(-2,-1/60),(-120,-1),(-240,-2),(600,5)]:
            d=self.decision(kind='scroll',x=100,y=100,scroll_y=amount)
            self.assertEqual(d['scroll_y'],amount)
            self.assertEqual(d['scroll_info']['units_per_notch'],120)
            self.assertAlmostEqual(d['scroll_info']['notches'],notches)
            self.assertEqual(float(encode_command(d,self.view).split('\n')[14]),amount)
        self.assertNotIn('scroll_info',self.decision(kind='move',x=100,y=100))

    def test_hover_moves_only_and_returns_fresh_frame_without_claiming_tooltip(self):
        self.executor.execute = Mock(return_value={'status':'input_sent'})
        status, png = self.hover_frame()
        self.control.reader.frame = Mock(return_value=(status,png))
        result, frame = self.executor.hover('v1',100,100)
        self.assertEqual(result['status'],'frame_returned')
        self.assertFalse(result['clicked']); self.assertEqual(frame,png)
        d = self.control._read('decisions/'+result['decision_id']+'.json')
        self.assertEqual((d['kind'],d['x'],d['y']),('move',100,100))
        self.executor.execute.assert_called_once()
        self.assertNotIn('tooltip', result)

    def test_hover_never_retries_uncertain_input(self):
        self.executor.execute = Mock(return_value={'status':'unknown'})
        self.control.reader.frame = Mock()
        result, frame = self.executor.hover('v1',100,100)
        self.assertEqual(result['status'],'input_not_confirmed'); self.assertIsNone(frame)
        self.control.reader.frame.assert_not_called(); self.executor.execute.assert_called_once()

    def test_hover_read_failure_keeps_execution_receipt(self):
        self.executor.execute = Mock(return_value={'status':'input_sent','id':'original-receipt'})
        self.control.reader.frame = Mock(side_effect=OSError('publisher unavailable'))
        result, frame = self.executor.hover('v1',100,100)
        self.assertEqual(result['receipt']['id'],'original-receipt')
        self.assertEqual(result['status'],'observation_unavailable'); self.assertIsNone(frame)
        self.executor.execute.assert_called_once()

    def test_hover_rejects_other_context_and_operator_stop(self):
        self.executor.execute = Mock(return_value={'status':'input_sent'})
        for changes in ({'scene':'Other'},{'process_id':456}):
            self.control.reader.frame = Mock(return_value=self.hover_frame(**changes))
            result, frame = self.executor.hover('v1',100,100)
            self.assertEqual(result['status'],'context_changed'); self.assertIsNone(frame)
        status, png = self.hover_frame()
        self.control.reader.frame = Mock(return_value=(status,png[:16]+(1600).to_bytes(4,'big')+png[20:]))
        self.assertEqual(self.executor.hover('v1',100,100)[0]['status'],'context_changed')
        (self.control.directory/'PAUSED').write_text('operator stop')
        result, frame = self.executor.hover('v1',100,100)
        self.assertEqual(result['status'],'operator_paused'); self.assertIsNone(frame)
        self.assertTrue((self.control.directory/'PAUSED').exists())

    def test_hover_does_not_offer_pre_move_frame_or_repeat_on_timeout(self):
        from datetime import datetime, timezone
        self.executor.execute = Mock(return_value={'status':'input_sent'})
        self.control.reader.frame = Mock(return_value=self.hover_frame(
            frame_captured_at_utc=datetime.fromtimestamp(time.time()-1,timezone.utc).isoformat()))
        with patch('robotomy.virtual_input.time.monotonic',side_effect=[0,0,4]), \
             patch('robotomy.virtual_input.time.sleep'):
            result, frame = self.executor.hover('v1',100,100)
        self.assertEqual(result['status'],'observation_unavailable'); self.assertIsNone(frame)
        self.executor.execute.assert_called_once()

    def test_hover_respects_input_lease_and_validates_before_input(self):
        from robotomy.input_sequence import input_lock
        self.executor.execute = Mock()
        for bad in (True,199,1501):
            with self.assertRaises(ValueError): self.executor.hover('v1',100,100,bad)
        with input_lock(self.root), self.assertRaisesRegex(ValueError,'Another input'):
            self.executor.hover('v1',100,100)
        with self.assertRaises(ValueError): self.executor.hover('stale-view',100,100)
        self.executor.execute.assert_not_called()

    def test_virtual_holds_drags_and_bounds(self):
        self.decision(kind='key',key='d',duration_ms=3000)
        self.decision(kind='drag',x=0,y=0,to_x=1279,to_y=719,duration_ms=1200)
        for changes in ({'duration_ms':3001},{'to_x':1280},{'x':float('nan')}):
            args=dict(kind='drag',x=10,y=10,to_x=50,to_y=50,duration_ms=80);args.update(changes)
            with self.assertRaises(ValueError): self.decision(**args)

    def test_protocol_has_exact_fields_and_lf_on_disk(self):
        d=self.decision(kind='key',key='w',duration_ms=1500)
        command=encode_command(d,self.view)
        path=self.root/'command';path.write_text(command,encoding='ascii',newline='\n')
        self.assertNotIn(b'\r',path.read_bytes())
        fields=command.split('\n');self.assertEqual(len(fields),16)
        self.assertEqual(fields[12],'v1');self.assertEqual(fields[13],'1500')
        d['scene']='Tutorial\ninjection'
        with self.assertRaises(ValueError): encode_command(d,self.view)

    def test_all_gesture_protocols_and_key_aliases(self):
        cases = [dict(kind=k,x=0,y=719) for k in ('click','right_click','move')]
        cases += [dict(kind=k,x=0,y=0,to_x=1279,to_y=719,duration_ms=3000)
                  for k in ('drag','right_drag')]
        cases += [dict(kind='scroll',x=100,y=100,scroll_y=v) for v in (-600,-120,120,600)]
        for args in cases:
            fields=encode_command(self.decision(**args),self.view).split('\n')
            self.assertEqual(fields[6],args['kind'])
            self.assertEqual(float(fields[8]),args['x'])
            self.assertEqual(float(fields[9]),args['y'])
            self.assertEqual(float(fields[14]),args.get('scroll_y',0))
        for label,expected in [(' D ','d'),('ESC','Escape'),('Enter','Return'),('Spacebar','space')]:
            fields=encode_command(self.decision(kind=' KEY ',key=label),self.view).split('\n')
            self.assertEqual(fields[6:8],['key',expected])

    def test_irrelevant_arguments_rejected_before_dispatch(self):
        for args in [dict(kind='click',x=10,y=10,to_x=9999),
                     dict(kind='move',x=10,y=10,scroll_y=1),
                     dict(kind='drag',x=0,y=0,to_x=20,to_y=20,key='D'),
                     dict(kind='key',key='D',x=10),dict(kind='key',key='D',scroll_y=float('nan'))]:
            with self.assertRaisesRegex(ValueError,'Arguments not used'): self.decision(**args)
        self.assertFalse((self.control.directory/'request.json').exists())
        self.assertFalse((self.control.directory/'decisions').exists())

    def test_long_gesture_needs_remaining_view_lifetime(self):
        self.view['captured_epoch']=time.time()-28
        atomic(self.control.directory/'view.json',self.view)
        with self.assertRaisesRegex(ValueError,'insufficient time'):
            self.decision(kind='key',key='D',duration_ms=3000)
        self.decision(kind='key',key='D',duration_ms=80)

    def test_dispatch_rechecks_lifetime_after_integrity_check(self):
        d=self.decision(kind='key',key='D',duration_ms=3000)
        self.executor._snapshot=Mock(return_value={'scene':'Tutorial_3','screen':{'width':1280,'height':720}})
        # The request object is read before integrity validation, so advance the clock instead.
        with patch('robotomy.virtual_input.subprocess.run',return_value=Mock(returncode=0)), \
             patch('robotomy.virtual_input.time.time',return_value=d['expires_epoch']-1):
            receipt=self.executor.execute(d['id'])
        self.assertEqual(receipt['status'],'rejected')
        self.assertIn('Insufficient time',receipt['reason'])
        self.assertFalse((self.control.directory/'virtual-command.txt').exists())

    def test_shared_file_read_retries_only_permission_error(self):
        path=Mock();path.read_text.side_effect=[PermissionError(),'{"ready":true}']
        with patch('robotomy.virtual_input.time.sleep'):
            self.assertEqual(read_json(path),{'ready':True})
        path.read_text.side_effect=PermissionError()
        with patch('robotomy.virtual_input.time.sleep'), self.assertRaises(PermissionError):read_json(path)

    def test_scene_change_rejects_before_dispatch_and_dedupes(self):
        d=self.decision(kind='click',x=100,y=100)
        self.executor._snapshot=Mock(return_value={'scene':'Other','screen':{'width':1280,'height':720}})
        receipt=self.executor.execute(d['id'])
        self.assertEqual(receipt['status'],'rejected')
        self.assertIn('Scene',receipt['reason'])
        self.assertFalse((self.control.directory/'virtual-command.txt').exists())
        self.assertEqual(self.executor.execute(d['id']),receipt)

    def test_original_integrity_failure_blocks_command(self):
        d=self.decision(kind='click',x=100,y=100)
        self.executor._snapshot=Mock(return_value={'scene':'Tutorial_3','screen':{'width':1280,'height':720}})
        with patch('robotomy.virtual_input.subprocess.run',return_value=Mock(returncode=1)):
            receipt=self.executor.execute(d['id'])
        self.assertEqual(receipt['status'],'rejected')
        self.assertIn('integrity',receipt['reason'])
        self.assertFalse((self.control.directory/'virtual-command.txt').exists())

    def test_resize_during_capture_never_publishes_mixed_coordinate_view(self):
        self.executor._snapshot=Mock(return_value={'process_id':123,'scene':'Tutorial_3',
                                                   'screen':{'width':1280,'height':720}})
        png=b'\x89PNG\r\n\x1a\n'+b'\0'*8+(1920).to_bytes(4,'big')+(1080).to_bytes(4,'big')
        self.control.reader.frame=Mock(return_value=({'process_id':123,'scene':'Tutorial_3'},png))
        with self.assertRaisesRegex(ValueError,'Resolution changed while capturing'):
            self.executor.capture()
        self.assertEqual(self.control._read('view.json')['id'],'v1')
        self.assertFalse((self.control.directory/'views').exists())

    def test_resize_after_prepare_rejects_old_coordinates(self):
        d=self.decision(kind='click',x=100,y=100)
        self.executor._snapshot=Mock(return_value={'scene':'Tutorial_3','screen':{'width':1920,'height':1080}})
        receipt=self.executor.execute(d['id'])
        self.assertEqual(receipt['status'],'rejected')
        self.assertIn('resolution changed',receipt['reason'])
        self.assertFalse((self.control.directory/'virtual-command.txt').exists())


if __name__=='__main__':unittest.main()
