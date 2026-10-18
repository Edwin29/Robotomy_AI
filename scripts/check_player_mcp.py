"""Read-only real player MCP preflight. No input, attempt, or experience fabrication."""
import asyncio
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT=Path(__file__).resolve().parents[1]


async def main():
    pause=ROOT/'.robotomy/live/control/PAUSED'
    before=pause.read_bytes() if pause.exists() else None
    params=StdioServerParameters(command=sys.executable,args=['-X','utf8',str(ROOT/'scripts/run_player_mcp.py')],
                                 cwd=str(ROOT.parent/'Robotomy_Player'))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as client:
            await client.initialize()
            names={t.name for t in (await client.list_tools()).tools}
            assert len(names)==26 and not ({'observe','start_session','read_live_timeline','resume'} & names)
            async def call(name,args=None):
                response=await client.call_tool(name,args or {})
                assert not response.isError, response.content
                return response.structuredContent or json.loads(response.content[0].text)
            experience=await call('player_experience_status')
            assert experience['active'] is None, 'Do not run engineering probes during a player attempt'
            guides=await call('read_player_guide')
            assert len(guides)==4 and all('Not configured' != v for v in guides.values())
            assert '사전 지식' in guides['AGENTS.md']
            assert '행동 변화' in guides['Day-Review-Template.md']
            status=await call('live_status'); assert status['status']=='live',status
            observation=await call('observe_live',{'max_items':24})
            assert observation['experience_recording']['status']=='inactive'
            control=await call('capture_live_control')
            assert control['view']['backend']=='virtual_unity'
            frame=await client.call_tool('view_live_frame',{})
            assert not frame.isError
            pictures=[v for v in frame.content if v.type=='image']
            assert len(pictures)==1
            data=base64.b64decode(pictures[0].data,validate=True)
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            folder=ROOT/'.robotomy/live/verification'/('player-'+stamp); folder.mkdir()
            (folder/'frame.png').write_bytes(data)
            (folder/'observation.json').write_text(json.dumps(observation,ensure_ascii=False,indent=2),encoding='utf-8')
            after=await call('player_experience_status')
            assert after['attempts']==experience['attempts'] and after['active'] is None
            assert before==(pause.read_bytes() if pause.exists() else None)
            report={'verified_at':stamp,'player_tools':len(names),'scene':status['scene'],
                    'process_id':status['process_id'],'png_bytes':len(data),'guide_files':list(guides),
                    'operator_pause_preserved':True,'player_attempts':len(after['attempts']),
                    'evidence_path':str(folder),'boundary':'Read-only actual UI/tool connection; no gameplay test'}
            (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__': asyncio.run(main())
