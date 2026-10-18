"""Explicit real MCP input check: one pointer move, never clicks or key presses."""
import asyncio
import json
from pathlib import Path
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


async def main():
    if '--execute' not in sys.argv:
        raise SystemExit('Pass --execute to authorize one real pointer move in the isolated game.')
    params = StdioServerParameters(command=sys.executable, args=['-m','robotomy','mcp'], cwd=str(ROOT))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            async def call(name, arguments):
                result = await client.call_tool(name, arguments)
                if result.isError: raise RuntimeError(str(result.content))
                return result.structuredContent or json.loads(result.content[0].text)
            capture = await call('capture_live_control', {})
            view = capture['view']
            x, y = view['width'] * .75, view['height'] * .75
            decision = await call('prepare_live_action', {'view_id':view['id'], 'kind':'move', 'x':x,'y':y,
                'rationale':'독립 MCP 입력 왕복 검증: 클릭 없이 게임 안 포인터만 이동한다.',
                'expected':'Win32 화면 좌표로 포인터가 이동하며 중복 요청은 같은 receipt만 반환한다.'})
            receipt = await call('execute_live_action', {'decision_id':decision['id']})
            assert receipt['status'] == 'input_sent', receipt
            expected = [view['geometry'][0] + int(x*view['geometry'][2]/view['width']),
                        view['geometry'][1] + int(y*view['geometry'][3]/view['height'])]
            assert receipt['pointer_screen'] == expected, receipt
            assert await call('execute_live_action', {'decision_id':decision['id']}) == receipt
            await asyncio.sleep(2)
            observed = await call('observe_live', {})
            await call('record_live_outcome', {'decision_id':decision['id'],
                'observation_id':observed['observation_id'],
                'result':'MCP로 독립 Win32 포인터 이동 및 동일 ID 재요청 무중복을 확인했다. 게임 행동 성공을 뜻하지 않는 입력 연결 검증이다.'})
            report = {'tools':len((await client.list_tools()).tools), 'receipt':receipt,
                      'duplicate_returned_same_receipt':True, 'expected_pointer_screen':expected,
                      'observation_id':observed['observation_id']}
            directory = ROOT / '.robotomy/live/verification/20261017-native'
            directory.mkdir(parents=True, exist_ok=True)
            (directory/'mcp-native.json').write_text(json.dumps(report, ensure_ascii=False, indent=2),encoding='utf-8')
            print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit("Historical native check. Current default uses virtual input; run scripts/check_virtual_mcp.py --execute.")
