"""Actual MCP stdio round-trip in an isolated temporary data root."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    with tempfile.TemporaryDirectory() as folder:
        params = StdioServerParameters(command=sys.executable,
            args=["-m", "robotomy", "--root", folder, "mcp"],
            cwd=str(Path(__file__).resolve().parents[1]))
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                listed = await client.list_tools()
                names = {t.name for t in listed.tools}
                assert {"observe", "record_decision", "execute_decision", "checkpoint"} <= names
                assert not ({"pause", "resume", "import_bundle", "message"} & names)

                async def call(name, args):
                    response = await client.call_tool(name, args)
                    assert not response.isError, response.content
                    return response.structuredContent or json.loads(response.content[0].text)

                run = await call("start_session", {"player": "mcp-smoke", "max_actions": 1})
                sid = run["id"]
                obs = await call("observe", {"session_id": sid})
                decision = await call("record_decision", {"session_id": sid,
                    "observation_id": obs["observation_id"], "action": "work", "goal": "verify",
                    "rationale": "모의 작업 결과를 확인한다", "expected_outcome": "change", "uncertainty": "fixture"})
                assert decision["data"]["rationale"] == "모의 작업 결과를 확인한다"
                outcome = await call("execute_decision", {"session_id": sid, "decision_id": decision["id"]})
                assert outcome["data"]["status"] == "budget_reached"
                saved = await call("checkpoint", {"session_id": sid})
                assert Path(saved["bundle_path"]).is_file()
                print(f"MCP stdio smoke passed: {len(names)} tools, decision/outcome/checkpoint round-trip")


if __name__ == "__main__":
    asyncio.run(main())
