import asyncio
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import AsyncMock
from robotomy.reload_host import ReloadHost,HOT,PINNED

SOURCE=Path(__file__).resolve().parents[1]/'robotomy'

class ReloadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'code';self.source.mkdir()
        for name in set(HOT+PINNED):shutil.copy2(SOURCE/(name+'.py'),self.source/(name+'.py'))
        self.host=ReloadHost(self.root,self.source);await self.host.initialize()
    async def asyncTearDown(self):
        self.host.discard(self.host.prefix)
    def change(self):
        p=self.source/'live.py';s=p.read_text(encoding='utf-8')
        s=s.replace('return summary\n\n    def frame', "return {**summary, 'reload_probe': 'updated'}\n\n    def frame")
        p.write_text(s,encoding='utf-8')
    async def test_generation_resolves_all_relative_imports_including_lazy_tools(self):
        import ast, importlib
        for reloaded in (False, True):
            if reloaded:
                self.change()
                await self.host.call('reload_player_code',{})
            for name in HOT:
                tree=ast.parse((self.source/(name+'.py')).read_text(encoding='utf-8'))
                for node in ast.walk(tree):
                    if isinstance(node,ast.ImportFrom) and node.level:
                        module=importlib.import_module('.'*node.level+(node.module or ''),self.host.prefix)
                        for alias in node.names:
                            if alias.name!='*':
                                self.assertTrue(hasattr(module,alias.name),(name,node.lineno,alias.name))
    async def test_adapter_state_uses_resident_input_lock_after_reload(self):
        from unittest.mock import Mock
        for reloaded in (False, True):
            if reloaded:
                self.change()
                await self.host.call('reload_player_code',{})
            adapter=self.host.backend._player_adapter
            quick=adapter.quick
            adapter.quick=Mock()
            try:
                for setting,value,shown in [('paused',True,'paused'),('speed',2,'2x')]:
                    snapshot={'ui_texts':[{'panel':'playback','text':shown}]}
                    adapter.quick.executor._snapshot.return_value=snapshot
                    adapter.set_state({'kind':'state','setting':setting,'value':value})
                    adapter.quick.offered.assert_called_with({'status':'already_set','setting':setting,'value':value},snapshot,'ready')
                adapter.quick.input.assert_not_called()
            finally:
                adapter.quick=quick
    async def test_reload_changes_result_preserves_storage_and_stop(self):
        before=self.host.revision;experience=self.host.experience;power=self.host.power
        stop=self.root/'.robotomy/live/control/PAUSED';stop.parent.mkdir(parents=True);stop.write_text('operator stop')
        self.change();result=await self.host.call('live_status',{})
        self.assertIn('updated',str(result));self.assertNotEqual(before,self.host.revision)
        self.assertIs(self.host.experience,experience);self.assertIs(self.host.power,power)
        self.assertEqual(stop.read_text(),'operator stop')
    async def test_bad_edit_blocks_dispatch_until_repaired(self):
        original=(self.source/'live.py').read_bytes();prefix=self.host.prefix
        self.host.backend.call_tool=AsyncMock()
        (self.source/'live.py').write_text('def broken(',encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError,'SyntaxError'):await self.host.call('execute_live_action',{})
        self.host.backend.call_tool.assert_not_called();self.assertEqual(prefix,self.host.prefix)
        (self.source/'live.py').write_bytes(original)
        self.assertEqual((await self.host.call('player_runtime_status',{}))['status'],'ready')
    async def test_inflight_call_finishes_before_swap(self):
        entered=asyncio.Event();release=asyncio.Event()
        async def delayed(*args):entered.set();await release.wait();return {'old':'completed'}
        self.host.backend.call_tool=delayed
        task=asyncio.create_task(self.host.call('live_status',{}));await entered.wait()
        before=self.host.revision;self.change()
        reload=asyncio.create_task(self.host.call('reload_player_code',{}))
        await asyncio.sleep(.05);self.assertFalse(reload.done());self.assertEqual(before,self.host.revision)
        release.set();self.assertEqual(await task,{'old':'completed'})
        self.assertEqual((await reload)['status'],'ready');self.assertNotEqual(before,self.host.revision)
    async def test_schema_change_requires_reconnect(self):
        p=self.source/'mcp_server.py';p.write_text(p.read_text(encoding='utf-8').replace('max_items: int = 100','max_items: int = 90'),encoding='utf-8')
        result=await self.host.call('reload_player_code',{})
        self.assertIn('schema changed',result['reload_error'])
    async def test_pinned_change_requires_reconnect(self):
        with (self.source/'experience.py').open('a',encoding='utf-8') as f:f.write('\n# storage change\n')
        self.assertIn('Resident component', (await self.host.call('player_runtime_status',{}))['reload_error'])
    async def test_pending_command_blocks_reload(self):
        p=self.root/'.robotomy/live/control/virtual-command.txt';p.parent.mkdir(parents=True);p.write_text('unresolved')
        self.change();r=await self.host.call('reload_player_code',{})
        self.assertIn('Pending game input',r['reload_error']);self.assertEqual(p.read_text(),'unresolved')
        receipt=await self.host.call('live_action_receipt',{'decision_id':'a'*32})
        self.assertIn('pending',str(receipt))
        p.unlink();self.assertEqual((await self.host.call('reload_player_code',{}))['status'],'ready')

    async def test_background_sequence_blocks_reload_but_cancel_remains_available(self):
        q=self.host.backend._input_sequences
        q.jobs['fixture']={'id':'fixture','status':'running','cancel_requested':False}
        self.change()
        result=await self.host.call('reload_player_code',{})
        self.assertIn('sequence active',result['reload_error'])
        result=await self.host.call('cancel_input_sequence',{'sequence_id':'fixture'})
        self.assertTrue(q.jobs['fixture']['cancel_requested'])
        q.jobs['fixture']['status']='stopped'
        self.assertEqual((await self.host.call('reload_player_code',{}))['status'],'ready')
    async def test_active_attempt_and_queued_evidence_survive_reload(self):
        j=self.host.experience
        attempt=j.begin(1,'reload-fixture',phase='tutorial')
        queued=j.record('fixture_before_reload',{'evidence':'original'})
        self.change()
        await self.host.call('reload_player_code',{})
        self.assertEqual(j.status()['active']['id'],attempt['id'])
        self.assertEqual(j.status()['active']['run'],1)
        self.assertIn('original',str(j.events(attempt['id'])))
        j.record('fixture_after_reload',{'evidence':'new'})
        j.flush()
        self.assertIn('new',str(j.events(attempt['id'])))
    async def test_observation_can_run_while_input_waits(self):
        entered=asyncio.Event();release=asyncio.Event()
        async def backend(name,args):
            if name=='execute_live_action':entered.set();await release.wait()
            return {'name':name}
        self.host.backend.call_tool=backend
        task=asyncio.create_task(self.host.call('execute_live_action',{}));await entered.wait()
        self.assertEqual(await asyncio.wait_for(self.host.call('live_status',{}),.5),{'name':'live_status'})
        release.set();await task
