"""Explicit bounded live verification on the title screen; leaves AI input paused."""
import asyncio
import ctypes
from ctypes import wintypes as W
import json
from pathlib import Path
import sys
import time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from robotomy.virtual_input import read_json
from robotomy.live_control import LiveControl


def os_state():
    user=ctypes.WinDLL('user32');user.GetForegroundWindow.restype=W.HWND
    user.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)]
    point=W.POINT();user.GetCursorPos(ctypes.byref(point))
    foreground=user.GetForegroundWindow();pid=W.DWORD();user.GetWindowThreadProcessId(foreground,ctypes.byref(pid))
    return {'cursor':[point.x,point.y],'foreground':foreground,'foreground_pid':pid.value,
            'physical_w':bool(user.GetAsyncKeyState(ord('W'))&0x8000),
            'physical_d':bool(user.GetAsyncKeyState(ord('D'))&0x8000)}


async def main():
    if '--execute' not in sys.argv: raise SystemExit('Use --execute for bounded virtual move/hold/stop verification.')
    control=LiveControl(ROOT)
    if control.reader.status().get('scene') != 'NewTitleScene': raise SystemExit('Title screen only.')
    control.resume()
    state_path=control.directory/'virtual-status.json'
    report={'os_before':os_state(),'tests':[]}
    params=StdioServerParameters(command=sys.executable,args=['-m','robotomy','mcp'],cwd=str(ROOT))
    try:
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as client:
                await client.initialize()
                async def call(name,args):
                    r=await client.call_tool(name,args)
                    if r.isError: raise RuntimeError(str(r.content))
                    return r.structuredContent or json.loads(r.content[0].text)
                async def prepare(**action):
                    capture=await call('capture_live_control',{})
                    assert capture['view']['backend']=='virtual_unity'
                    return await call('prepare_live_action',{'view_id':capture['view']['id'],
                        'rationale':'개발 검증: 타이틀에서 가상 입력·시간 제한·중지 동작을 시험한다. 튜토리얼 경험과 분리한다.',
                        'expected':'OS 입력 없이 가상 상태만 변경되고 해제된다.',**action})
                d=await prepare(kind='move',x=960,y=540)
                receipt=await call('execute_live_action',{'decision_id':d['id']})
                assert receipt['status']=='input_sent',receipt
                assert await call('execute_live_action',{'decision_id':d['id']})==receipt
                await asyncio.sleep(.6)
                state=read_json(state_path);assert state['pointer']==[960,540],state
                report['tests'].append({'kind':'move_and_duplicate','receipt':receipt,'virtual_state':state,'os_after':os_state()})
                for key,duration,stop in [('d',1500,False),('w',3000,True)]:
                    d=await prepare(kind='key',key=key,duration_ms=duration)
                    task=asyncio.create_task(call('execute_live_action',{'decision_id':d['id']}))
                    deadline=time.monotonic()+4;held=None
                    while time.monotonic()<deadline:
                        await asyncio.sleep(.04)
                        state=read_json(state_path)
                        if state['held_key']==key.upper():held=state;break
                        if task.done():break
                    assert held, 'Held state was not observed'
                    physical=os_state()
                    if stop:control.pause()
                    receipt=await task
                    assert receipt['status']==('unknown' if stop else 'input_sent'),receipt
                    await asyncio.sleep(.6)
                    released=read_json(state_path)
                    assert released['held_key']=='None' and released['held_button']==-1,released
                    report['tests'].append({'kind':'pause_during_hold' if stop else 'timed_hold','held':held,
                        'physical_during_hold':physical,'receipt':receipt,'released':released})
                report['tool_count']=len((await client.list_tools()).tools)
    finally:
        control.pause()
        report['os_after']=os_state()
        folder=ROOT/'.robotomy/live/verification/20261017-virtual';folder.mkdir(parents=True,exist_ok=True)
        (folder/'mcp-virtual.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');asyncio.run(main())
