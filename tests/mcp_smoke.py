"""Actual MCP stdio round-trip in an isolated temporary data root."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import time
from datetime import datetime, timezone

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    with tempfile.TemporaryDirectory() as folder:
        rules=Path(folder)/'config/player/AGENTS.md'
        rules.parent.mkdir(parents=True)
        rules.write_text('Player-only rules: no pretrained game knowledge',encoding='utf-8')
        (Path(folder)/'AGENTS.md').write_text('Engineering-only context',encoding='utf-8')
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

                guide=await call('read_player_guide',{})
                assert set(guide)=={'AGENTS.md','Player-Persona.md','Recording-Rules.md','Day-Review-Template.md'}
                assert guide['AGENTS.md']=='Player-only rules: no pretrained game knowledge'
                assert 'Engineering-only' not in json.dumps(guide)

                memo=await call('save_playbook_entry',{'entry':{
                    'title':'fixture memo','author':'smoke-test','category':'custom-format',
                    'content':{'own_structure':['not actual gameplay']},'startup':True}})
                found=await call('read_playbook',{'query':'fixture'})
                assert found['entries'][0]['id']==memo['id']
                loaded=await call('read_playbook',{'entry_id':memo['id']})
                assert loaded['content']=={'own_structure':['not actual gameplay']}
                memory=await call('read_player_memory',{})
                assert memory['playbook_startup']['entries'][0]['id']==memo['id']

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
                # Contract test only: temporary snapshot and queue, never actual OS input.
                live_dir = Path(folder) / '.robotomy/live'
                (live_dir / 'control').mkdir(parents=True, exist_ok=True)
                (live_dir / 'latest.json').write_text(json.dumps({
                    'schema_version':1,'environment':'lobotomy_live','read_only':True,
                    'captured_at_utc':datetime.now(timezone.utc).isoformat(),'process_id':123,'sequence':1,
                    'scene':'fixture','screen':{'width':1280,'height':720},'ui_texts':[],
                    'isolation':{'company_name':'Robotomy_AI','product_name':'Lobotomy_Observer',
                    'persistent_data_path':'C:/fixture/Robotomy_AI/Lobotomy_Observer'}}),encoding='utf-8')
                (live_dir/'control/view.json').write_text(json.dumps({'id':'fixture-view','captured_epoch':time.time(),
                    'process_id':123,'scene':'fixture','width':734,'height':437,'bridge_id':'fixture-bridge',
                    'screenshot_id':'fixture-shot','window_id':123}),encoding='utf-8')
                d = await call('prepare_live_action',{'view_id':'fixture-view','kind':'click','x':100,'y':100,
                    'rationale':'MCP queue validation only','expected':'A pending record without OS input'})
                queued = await call('execute_live_action',{'decision_id':d['id']})
                assert queued['status']=='rejected'  # Legacy/fixture view must never reach Win32.
                assert 'virtual control view' in queued['reason']
                assert (await call('execute_live_action',{'decision_id':d['id']}))==queued
                receipt=await call('live_action_receipt',{'decision_id':d['id']})
                assert all(queued[k]==v for k,v in receipt.items())
                assert queued['current'] is None
                timeline = await call('read_live_timeline',{})
                if isinstance(timeline, dict): timeline = timeline['result']
                assert len(timeline)==3
                history = await call('read_live_history', {})
                assert history['historical'] and not history['actionable'] and history['status']=='unavailable'
                history = await call('view_live_history_frame', {'session':'a'*32, 'sequence':1})
                assert history['historical'] and not history['actionable']
                # Temporary-root player recording lifecycle, never real gameplay.
                attempt = await call('begin_player_attempt', {'day':1,'player':'MCP fixture, not actual play'})
                delivered = await call('observe_live', {'max_items':1})
                eid = delivered['experience_recording']['event_id']
                note = await call('record_player_note', {'text':'Synthetic integration test only','author':'test harness','evidence_ids':[eid]})
                events = await call('read_experience_events', {'attempt_id':attempt['id'],'limit':2})
                assert len(events['events'])==2 and events['has_more']
                exact = await call('read_experience_event', {'event_id':eid})
                assert exact['data']['state']==delivered['state']
                assert delivered['schema']=='player_delta_v2' and delivered['mode']=='full'
                await call('finish_player_attempt', {'attempt_id':attempt['id'],'status':'completed','evidence_ids':[eid]})
                review = await call('complete_day_review', {'attempt_id':attempt['id'],'author':'test harness',
                    'summary':'MCP plumbing test, no game was played','evidence_ids':[eid],
                    'lessons':[{'text':'Fixture linkage works; not a game mechanic','basis':'hypothesis','evidence_ids':[eid]}],
                    'experiences':[{'kind':'story','text':'Synthetic subjective entry, not actual play',
                                    'evidence_ids':[eid],'remember':True}]})
                assert review['experiences'][0]['basis']=='subjective_experience'
                memory = await call('read_player_memory', {})
                assert memory['entries'][0]['id']==review['memory_updates'][0]['id']
                assert len(memory['entries'])==2
                bundle = await call('export_player_experience', {})
                assert (Path(bundle['directory'])/'Bundle.json').exists()
                assert (await call('player_experience_status', {}))['active'] is None
                print(f"MCP stdio smoke passed: {len(names)} tools, decision/outcome/checkpoint round-trip")


if __name__ == "__main__":
    asyncio.run(main())
