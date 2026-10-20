"""Real stdio MCP reload test; isolated data and source, no live game tools."""
import asyncio
import json
from pathlib import Path
import shutil
import sys
import tempfile
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT=Path(__file__).resolve().parents[1]
async def main():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);package=root/'robotomy'
        shutil.copytree(ROOT/'robotomy',package,ignore=shutil.ignore_patterns('__pycache__'))
        code="import asyncio; from robotomy.reload_host import serve; asyncio.run(serve("+repr(str(root/'data'))+"))"
        params=StdioServerParameters(command=sys.executable,args=['-X','utf8','-c',code],cwd=str(root))
        async with stdio_client(params) as (incoming,outgoing):
            async with ClientSession(incoming,outgoing) as client:
                await client.initialize()
                names={t.name for t in (await client.list_tools()).tools}
                assert len(names)==37 and {'hover_live_control','player_runtime_status','reload_player_code','start_game',
                    'submit_input_sequence','input_sequence_status','cancel_input_sequence'}<=names
                async def call(name):
                    response=await client.call_tool(name,{})
                    assert not response.isError,response.content
                    return response.structuredContent or json.loads(response.content[0].text)
                first=await call('player_runtime_status')
                assert (await call('live_status'))['status']=='never_connected'
                p=package/'live.py';original=p.read_text(encoding='utf-8')
                p.write_text(original.replace('return summary\n\n    def frame',"return {**summary, 'reload_probe': 'new implementation'}\n\n    def frame"),encoding='utf-8')
                assert (await call('live_status'))['reload_probe']=='new implementation'
                assert (await call('player_runtime_status'))['code_revision']!=first['code_revision']
                p.write_text('def broken(',encoding='utf-8')
                assert (await call('player_runtime_status'))['status']=='blocked'
                blocked=await client.call_tool('live_status',{});assert blocked.isError
                p.write_text(original,encoding='utf-8')
                assert (await call('live_status'))['status']=='never_connected'
                assert (await call('player_runtime_status'))['code_revision']==first['code_revision']
                print('Reload MCP smoke passed: 37 tools; same connection applied change, blocked bad edit, recovered.')
if __name__=='__main__':asyncio.run(main())
