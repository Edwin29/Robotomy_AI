"""A slow executor must not block an independent read on the MCP event loop."""
import asyncio
import tempfile
import threading
import unittest
from unittest.mock import patch
from robotomy.mcp_server import create_server


class MCPConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_observation_while_execution_waits(self):
        started, release = threading.Event(), threading.Event()
        def slow_execute(*args):
            started.set()
            release.wait(2)
            return {'status': 'fixture_only'}
        with tempfile.TemporaryDirectory() as root:
            server = create_server(root)
            with patch('robotomy.virtual_input.VirtualExecutor.execute', slow_execute), \
                 patch('robotomy.live.LiveReader.status', return_value={'status': 'read_completed'}):
                task = asyncio.create_task(server.call_tool('execute_live_action', {'decision_id': 'a'*32}))
                try:
                    for _ in range(100):
                        if started.is_set(): break
                        await asyncio.sleep(.01)
                    self.assertTrue(started.is_set())
                    await asyncio.wait_for(server.call_tool('live_status', {}), timeout=.5)
                    self.assertFalse(task.done(), 'read must finish while executor is still waiting')
                finally:
                    release.set()
                    await task
