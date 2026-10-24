"""Verify actual-game observation through stdio MCP, with private evidence output."""
import asyncio
import base64
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


async def main():
    params = StdioServerParameters(command=sys.executable,
        args=[str(ROOT / 'scripts/run_mcp.py')], cwd=str(ROOT))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            listed = await client.list_tools()
            response = await client.call_tool('observe_live', {'compact': False})
            assert not response.isError, response.content
            observation = response.structuredContent or json.loads(response.content[0].text)
            compact_response = await client.call_tool('observe_live', {'max_items': 16, 'motion_only': True})
            assert not compact_response.isError, compact_response.content
            compact = compact_response.structuredContent or json.loads(compact_response.content[0].text)
            assert 'audio_events' not in json.dumps(compact)
            assert observation['status'] == 'live', observation
            frame = await client.call_tool('view_live_frame', {})
            assert not frame.isError, frame.content
            pictures = [item for item in frame.content if item.type == 'image']
            assert len(pictures) == 1 and pictures[0].mimeType == 'image/png', frame.content
            image = base64.b64decode(pictures[0].data, validate=True)
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            evidence = ROOT / '.robotomy/live/verification' / stamp
            evidence.mkdir(parents=True)
            (evidence / 'observation.json').write_text(json.dumps(observation, ensure_ascii=False, indent=2), encoding='utf-8')
            (evidence / 'motion-compact.json').write_text(json.dumps(compact, ensure_ascii=False, indent=2), encoding='utf-8')
            (evidence / 'frame.png').write_bytes(image)
            report = {'verified_at_utc': stamp, 'transport': 'MCP stdio', 'tool_count': len(listed.tools),
                'status': observation['status'], 'scene': observation['scene'],
                'ui_text_count': observation['ui_text_count'], 'png_bytes': len(image),
                'observation_id': observation['observation_id'], 'evidence_path': str(evidence),
                'boundary': 'Actual UI reading only; JSON and frame are sampled separately; no game commands.'}
            (evidence / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
