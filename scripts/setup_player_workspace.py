"""Create a clean, player-facing folder without replacing existing files."""
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def setup(destination):
    destination=Path(destination).resolve()
    if destination==ROOT or ROOT in destination.parents:
        raise ValueError('Player workspace must be outside the engineering repository')
    if destination.exists(): raise ValueError('Destination already exists; inspect it instead of overwriting')
    python=ROOT/'.venv/Scripts/python.exe'
    if not python.is_file(): raise ValueError('Project Python not installed')
    destination.mkdir(parents=True)
    for name in ('AGENTS.md','START-HERE.md','RUN-PROMPT.md'):
        (destination/name).write_bytes((ROOT/'config/player'/name).read_bytes())
    settings=destination/'.codex/config.toml'; settings.parent.mkdir()
    settings.write_text('[mcp_servers.robotomy_player]\ncommand = '+json.dumps(str(python))+
                        '\nargs = '+json.dumps(['-X','utf8',str(ROOT/'scripts/run_player_mcp.py')])+
                        '\nstartup_timeout_sec = 20\ntool_timeout_sec = 30\n',encoding='utf-8')
    for name,args in [('Ready-Player','--start-game --enable-input'),('Stop-Player','--stop')]:
        (destination/(name+'.cmd')).write_text(
            '@echo off\r\nchcp 65001 >nul\r\n'+
            f'"{python}" -X utf8 "{ROOT / "scripts/prepare_player.py"}" {args}\r\n'+
            'if errorlevel 1 echo FAILED - review the error above.\r\npause\r\n',encoding='utf-8',newline='')
    return destination


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    print(setup(parser.parse_args().destination))
