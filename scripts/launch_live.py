"""Launch the verified private copy in a visible window, or check original integrity."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone

from prepare_live import ROOT, PRIVATE, assert_game_stopped, digest, inventory, prefs_snapshot


def launch_state(state, **fields):
    sys.path.insert(0, str(ROOT))
    from robotomy.live_control import atomic
    atomic(PRIVATE / 'live/launch-state.json', dict(state=state,
        worker_pid=os.getpid(), updated_at_epoch=time.time(), **fields))


def request_independent_launch():
    """Task Scheduler owns the worker, game and aspect helper, not the MCP client."""
    requested = time.time()
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive',
        '-WindowStyle', 'Hidden', '-File', str(ROOT / 'scripts/start_game_task.ps1'),
        '-Root', str(ROOT)], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError('Independent launcher registration failed: ' +
                           result.stderr.decode('utf-8', errors='replace'))
    print(result.stdout.decode('utf-8', errors='replace').strip(), flush=True)
    sys.path.insert(0, str(ROOT))
    from robotomy.virtual_input import verify_process
    deadline = time.monotonic() + 110
    while time.monotonic() < deadline:
        try:
            state = json.loads((PRIVATE / 'live/launch-state.json').read_text(encoding='utf-8'))
            if state['state'] == 'ready':
                verify_process(state['game_pid'], PRIVATE / 'runtime/LobotomyCorp/LobotomyCorp.exe')
                verify_process(state['worker_pid'], Path(sys._base_executable).with_name('pythonw.exe'))
                print('LIVE (Windows-owned): PID ' + str(state['game_pid']), flush=True)
                return
            if state['state'] == 'failed' and state['updated_at_epoch'] >= requested:
                raise RuntimeError('Independent launcher failed: ' + state['error'])
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(.25)
    # Do not terminate a potentially running game just because a client timed out.
    raise RuntimeError('Startup confirmation timed out; inspect launch-state.json before retrying.')


def check_original(manifest: dict) -> dict:
    # Original play is independent: historical save/preferences drift is diagnostic.
    # Resolve junctions too; neither save root may contain the other.
    original = Path(manifest['original_save_root']).resolve()
    isolated = Path(manifest['isolated_save_path']).resolve()
    separate = original != isolated and original not in isolated.parents and isolated not in original.parents
    current = inventory(original)
    baseline = manifest['original_save_hashes']
    changed = sorted(k for k in set(current) | set(baseline) if current.get(k) != baseline.get(k))
    metadata_ok = digest(Path(manifest['source']) / 'LobotomyCorp_Data/globalgamemanagers') == manifest['original_metadata_sha256']
    preferences_ok = prefs_snapshot() == manifest['original_preferences']
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'original_files': len(baseline),
        'changed_original_files': changed, 'original_preferences_unchanged': preferences_ok,
        'original_metadata_unchanged': metadata_ok, 'save_paths_separate': separate,
        'original_changes_policy': 'diagnostic_only', 'ok': separate and metadata_ok}
    (PRIVATE / 'live/integrity-latest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--scheduled-worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    manifest = json.loads((PRIVATE / 'live/isolation.json').read_text(encoding='utf-8'))
    report = check_original(manifest)
    print(json.dumps(report, ensure_ascii=False), flush=True)
    if not report['ok']:
        raise RuntimeError('Save isolation or original game metadata check failed. Stop and review before launching.')
    if args.verify_only:
        return
    if not args.scheduled_worker:
        request_independent_launch()
        return
    launch_state('starting')
    assert_game_stopped()
    runtime = Path(manifest['runtime']).resolve()
    if runtime != (PRIVATE / 'runtime/LobotomyCorp').resolve() or not manifest.get('prepared'):
        raise RuntimeError('Unrecognized or incomplete runtime.')
    verified = {runtime / 'LobotomyCorp.exe': manifest['runtime_exe_sha256'],
        runtime / 'LobotomyCorp_Data/globalgamemanagers': manifest['runtime_metadata_sha256'],
        runtime / 'LobotomyCorp_Data/BaseMods/RobotomyObserver/RobotomyObserver.dll': manifest['observer_sha256']}
    for path, expected in verified.items():
        if digest(path) != expected:
            raise RuntimeError(f'Runtime integrity mismatch: {path}')
    if (runtime / 'steam_appid.txt').read_text().strip() != '568220':
        raise RuntimeError('Missing expected Steam local launch context.')
    env = os.environ.copy()
    env['ROBOTOMY_OBSERVATION_DIR'] = str(PRIVATE / 'live')
    env['ROBOTOMY_EXPECTED_SAVE_PATH'] = manifest['isolated_save_path']
    process = subprocess.Popen([str(runtime / 'LobotomyCorp.exe'), '-screen-fullscreen', '0',
        '-screen-width', '1280', '-screen-height', '720', '-logFile', str(PRIVATE / 'live/player.log')],
        cwd=runtime, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    sys.path.insert(0, str(ROOT))
    from robotomy.live import LiveReader
    reader = LiveReader(ROOT)
    deadline = time.monotonic() + 90
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f'Game exited before observer connected: {process.returncode}')
            snapshot_path = PRIVATE / 'live/latest.json'
            if snapshot_path.exists():
                try:
                    snapshot = json.loads(snapshot_path.read_text(encoding='utf-8'))
                except PermissionError:
                    # Mono atomic replacement can briefly deny Windows sharing.
                    time.sleep(.02)
                    continue
                if snapshot.get('process_id') == process.pid:
                    # The observer can initialize before the game's title load. A
                    # live Intro sample alone does not prove the game is ready.
                    if snapshot.get('scene') == 'Intro':
                        time.sleep(.1)
                        continue
                    status = reader.status()
                    if status['status'] == 'stale':
                        # Asset loading can exceed the subsecond observation TTL. Wait for a
                        # fresh handshake within the existing deadline; do not accept stale data.
                        time.sleep(.1)
                        continue
                    if status['status'] != 'live':
                        raise RuntimeError(f'Live handshake rejected: {status}')
                    if Path(snapshot['isolation']['persistent_data_path']).resolve() != Path(manifest['isolated_save_path']).resolve():
                        raise RuntimeError('Runtime save path mismatch.')
                    from robotomy.observer_window import ensure_aspect_guard
                    ensure_aspect_guard(ROOT)
                    report = check_original(manifest)
                    if not report['ok']:
                        raise RuntimeError(f'Original integrity changed: {report}')
                    (PRIVATE / 'live/process.json').write_text(json.dumps({'pid': process.pid, 'executable': str(runtime / 'LobotomyCorp.exe'),
                        'owner': 'windows_task_scheduler', 'worker_pid': os.getpid(),
                        'started_at_utc': datetime.now(timezone.utc).isoformat()}, indent=2), encoding='utf-8')
                    print(f'LIVE: PID {process.pid}, scene {snapshot["scene"]}, separate save {snapshot["isolation"]["persistent_data_path"]}', flush=True)
                    launch_state('ready', game_pid=process.pid, scene=snapshot['scene'])
                    # Keep the scheduled action alive for the whole game lifetime.
                    # Client disconnects cannot enter this worker's cleanup path.
                    code = process.wait()
                    launch_state('exited', game_pid=process.pid, exit_code=code)
                    return
            time.sleep(1)
        raise RuntimeError('Observer did not connect within 90 seconds. Check the isolated save folder/LobotomyBaseMod/Log.txt and any .robotomy/live/player.log.')
    except Exception:
        if process.poll() is None:
            process.terminate()  # Only this newly created copy, never an existing user process.
            process.wait(timeout=15)
        raise


if __name__ == '__main__':
    if '--scheduled-worker' in sys.argv:
        with (PRIVATE / 'live/independent-startup.log').open('a', encoding='utf-8', buffering=1) as log:
            with redirect_stdout(log), redirect_stderr(log):
                try:
                    main()
                except Exception as exc:
                    launch_state('failed', error=str(exc))
                    traceback.print_exc()
                    raise SystemExit(1)
    else:
        main()
