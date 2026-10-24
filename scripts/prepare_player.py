"""Operator-only readiness check/start/stop. Never plays or creates player memories."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from launch_live import check_original, digest
from robotomy.live import LiveReader
from robotomy.live_control import LiveControl
from robotomy.virtual_input import VirtualExecutor, verify_process
from robotomy.observer_window import ensure_aspect_guard


def preflight():
    manifest=json.loads((ROOT/'.robotomy/live/isolation.json').read_text(encoding='utf-8'))
    report=check_original(manifest)
    if not report['ok']: raise ValueError('Save isolation or original game metadata check failed. Input remains blocked.')
    runtime=ROOT/'.robotomy/runtime/LobotomyCorp'
    if Path(manifest['runtime']).resolve()!=runtime.resolve() or not manifest.get('prepared'):
        raise ValueError('Unrecognized private runtime')
    for relative,key in [('LobotomyCorp.exe','runtime_exe_sha256'),
                         ('LobotomyCorp_Data/globalgamemanagers','runtime_metadata_sha256'),
                         ('LobotomyCorp_Data/BaseMods/RobotomyObserver/RobotomyObserver.dll','observer_sha256')]:
        if digest(runtime/relative)!=manifest[key]: raise ValueError('Private runtime integrity mismatch: '+relative)
    return report


def ensure_monitor():
    url='http://127.0.0.1:8765/'
    def healthy():
        try:
            with urlopen(url,timeout=2) as response:
                page=response.read(1024*1024).decode('utf-8')
            if 'Robotomy' not in page: raise ValueError('Port 8765 is occupied by another server')
            return True
        except URLError:
            return False
    if not healthy():
        subprocess.Popen([sys.executable,str(ROOT/'scripts/live_monitor.py')],cwd=ROOT,
                         stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                         creationflags=subprocess.CREATE_NO_WINDOW)
        for _ in range(30):
            time.sleep(.1)
            if healthy(): break
        else: raise ValueError('Observer page did not become available')
    return url


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--enable-input',action='store_true')
    group.add_argument('--stop',action='store_true')
    parser.add_argument('--start-game',action='store_true')
    args=parser.parse_args()
    control=LiveControl(ROOT)
    if args.stop:
        control.pause()
        print('AI INPUT STOPPED. This is an input stop, not an in-game time pause.')
        return
    # Explicit activation fails closed. Default verification preserves the existing pause.
    if args.enable_input: control.pause()
    report=preflight()
    if args.start_game:
        status=LiveReader(ROOT).status()
        try:
            verify_process(status.get('process_id',0),ROOT/'.robotomy/runtime/LobotomyCorp/LobotomyCorp.exe')
            running=True
        except (ValueError,OSError): running=False
        if not running:
            # The official launcher also refuses an already running/original game.
            subprocess.run([sys.executable,'-X','utf8',str(ROOT/'scripts/launch_live.py')],
                           cwd=ROOT,check=True)
    if args.enable_input: ensure_aspect_guard(ROOT)
    snapshot=VirtualExecutor(ROOT)._snapshot()
    frame_status,frame=control.reader.frame()
    if frame is None or frame_status.get('process_id')!=snapshot['process_id'] or frame_status.get('scene')!=snapshot['scene']:
        raise ValueError('Fresh matching screenshot required')
    pending=[name for name in ('request.json','virtual-command.txt') if (control.directory/name).exists()]
    if pending: raise ValueError('Unresolved input; do not replay automatically: '+', '.join(pending))
    monitor=ensure_monitor() if args.enable_input else 'http://127.0.0.1:8765/'
    if args.enable_input: control.resume()
    print(json.dumps({'ready':True,'scene':snapshot['scene'],'process_id':snapshot['process_id'],
                      'input_enabled':not (control.directory/'PAUSED').exists(),
                      'original_integrity':report,'observer_url':monitor,
                      'note':'No gameplay or attempt started. Use one player MCP host.'},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
