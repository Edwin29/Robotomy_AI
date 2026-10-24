"""Generate a local-only plugin catalog; no game assets, saves or secrets are packaged."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def generate(root=ROOT):
    root=Path(root).resolve()
    catalog=root/'.robotomy/plugin-marketplace'
    plugin=catalog/'plugins/robotomy-player'
    def save(path,obj):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save(plugin/'.codex-plugin/plugin.json',{
        'name':'robotomy-player','version':'1.0.2',
        'description':'Local Lobotomy game console: visible observations, virtual input and attributed experience. No walkthroughs.',
        'mcpServers':'./.mcp.json','interface':{
            'displayName':'Lobotomy Player','shortDescription':'로보토미 AI 게임기 · 관찰, 가상 입력, 경험 기록',
            'longDescription':'이 PC의 격리 실행본을 사용하는 로컬 게임기. 게임과 원본 세이브는 플러그인에 포함하지 않습니다.',
            'developerName':'Lobotomy AI','category':'Productivity'}})
    # Codex compatibility manifest explicitly references the bundled MCP file.
    save(plugin/'.mcp.json',{'mcpServers':{'robotomy_player':{
        'command':str(root/'.venv/Scripts/python.exe'),
        'args':['-X','utf8',str(root/'scripts/run_player_mcp.py')]}}})
    for obsolete in ('plugin.json', 'mcp.json'):
        (plugin/obsolete).unlink(missing_ok=True)
    save(catalog/'.agents/plugins/marketplace.json',{
        'name':'robotomy-local','interface':{'displayName':'Lobotomy Local'},
        'plugins':[{'name':'robotomy-player','source':{'source':'local','path':'./plugins/robotomy-player'},
                    'policy':{'installation':'AVAILABLE','authentication':'ON_INSTALL'},'category':'Productivity'}]})
    return catalog

if __name__=='__main__':print(generate())
