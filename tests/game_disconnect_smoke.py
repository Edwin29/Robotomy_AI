"""Explicit live check: status only, then kill our own MCP test connection's job.

Requires an already running private game. Never starts/closes/controls the game,
records observations, or touches the real player's MCP process.
"""
import ctypes
from ctypes import wintypes as w
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from independent_launch_smoke import wait_for

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from robotomy.virtual_input import read_json, verify_process


def main():
    live = ROOT/'.robotomy/live'
    initial = read_json(live/'latest.json')
    pid = initial['process_id']
    verify_process(pid, ROOT/'.robotomy/runtime/LobotomyCorp/LobotomyCorp.exe')
    paused = (live/'control/PAUSED').exists()
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
    kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    kernel.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    with tempfile.TemporaryDirectory(prefix='robotomy-mcp-disconnect-') as tmp:
        marker = Path(tmp)
        code = '''import asyncio,json,sys,time
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
root=Path(sys.argv[1]);marker=Path(sys.argv[2])
while not (marker/'go').exists():time.sleep(.05)
async def main():
    params=StdioServerParameters(command=sys.executable,args=['-X','utf8',str(root/'scripts/run_player_mcp.py')],cwd=str(root))
    async with stdio_client(params) as (incoming,outgoing):
        async with ClientSession(incoming,outgoing) as client:
            await client.initialize()
            tools=await client.list_tools()
            result=await client.call_tool('game_power_status',{})
            assert not result.isError
            status=result.structuredContent or json.loads(result.content[0].text)
            assert status['status']=='running',status
            (marker/'ready.json').write_text(json.dumps({'tools':len(tools.tools),'power':status}))
            await asyncio.Event().wait()
asyncio.run(main())
'''
        caller = subprocess.Popen([sys.executable,'-X','utf8','-c',code,str(ROOT),str(marker)],
            cwd=ROOT, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            if not kernel.AssignProcessToJobObject(job, w.HANDLE(caller._handle)):
                raise ctypes.WinError(ctypes.get_last_error())
            (marker/'go').touch()
            wait_for(lambda: (marker/'ready.json').exists())
            connection = read_json(marker/'ready.json')
            before = read_json(live/'latest.json')
            helper_before = read_json(live/'observer-window.json')
            if not kernel.TerminateJobObject(job, 93):
                raise ctypes.WinError(ctypes.get_last_error())
            caller.wait(timeout=10)
            wait_for(lambda: read_json(live/'latest.json')['sequence'] > before['sequence'])
            wait_for(lambda: read_json(live/'observer-window.json')['at_epoch'] > helper_before['at_epoch'])
            after = read_json(live/'latest.json')
            verify_process(pid, ROOT/'.robotomy/runtime/LobotomyCorp/LobotomyCorp.exe')
            assert after['process_id'] == pid and (live/'control/PAUSED').exists() == paused
            report = dict(result='passed', game_pid=pid, scene=after['scene'],
                test_mcp_tools=connection['tools'], caller_exit=caller.returncode,
                sequence_before=before['sequence'], sequence_after=after['sequence'],
                aspect_helper_survived=True, input_stop_preserved=True, game_input_sent=False,
                actual_codex_app_restart_tested=False)
            target=live/'verification/independent-launch'
            target.mkdir(parents=True,exist_ok=True)
            (target/'mcp-disconnect.json').write_text(json.dumps(report,indent=2))
            print(json.dumps(report))
        finally:
            if caller.poll() is None:
                kernel.TerminateJobObject(job,94)
                caller.wait(timeout=10)
            kernel.CloseHandle(job)


if __name__ == '__main__':
    main()
