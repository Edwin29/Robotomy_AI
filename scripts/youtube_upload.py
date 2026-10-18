"""Operator CLI; never imported by the player MCP or game."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from robotomy.youtube_upload import Uploader, authorize, initialize, worker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init','connect','start','stop','status','scan','worker'])
    parser.add_argument('--folder', default=r'D:\NVIDIA\Lobotomycorp')
    parser.add_argument('--include-existing', action='store_true')
    parser.add_argument('--include-file', action='append', default=[])
    args = parser.parse_args()
    directory = ROOT/'.robotomy/youtube'
    if args.command == 'init':
        result = initialize(directory, args.folder, args.include_existing, args.include_file)
    elif args.command == 'connect':
        result = authorize(directory)
    elif args.command == 'worker':
        worker(directory); return
    elif args.command == 'start':
        if not (directory/'config.json').exists():
            raise ValueError('Initialize first')
        (directory/'STOP').unlink(missing_ok=True)
        subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-WindowStyle','Hidden',
            '-File',str(ROOT/'scripts/start_youtube_task.ps1'),'-Root',str(ROOT)],check=True)
        return
    elif args.command == 'stop':
        (directory/'STOP').touch()
        result = {'status':'stop_requested','note':'Finishes current HTTP request, keeps resumable state. Does not stop NVIDIA recording.'}
    else:
        uploader = Uploader(directory)
        try:
            if args.command == 'scan':
                uploader.scan(); uploader.prepare()
            result = uploader.summary()
            heartbeat = directory/'status.json'
            if heartbeat.exists():
                state = json.loads(heartbeat.read_text(encoding='utf8'))
                import time
                result['worker'] = {k:state.get(k) for k in ('pid','worker','at_epoch','error_type')}
                result['worker']['age_seconds'] = round(time.time()-state['at_epoch'],1)
            result['stop_requested'] = (directory/'STOP').exists()
        finally:
            uploader.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Keep URLs, OAuth callbacks, tokens and arbitrary server messages out of console logs.
        print(json.dumps({'status':'error','type':type(exc).__name__,
                          'help':'See docs/youtube-auto-upload.md. No game or recording action was taken.'}))
        raise SystemExit(1)
