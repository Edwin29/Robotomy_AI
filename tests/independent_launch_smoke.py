"""Windows lifecycle integration fixture. No game, saves, MCP memory or OS input."""
import ctypes
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def wait_for(predicate, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(.1)
    raise TimeoutError('Fixture did not reach expected state')


def main():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
    kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    kernel.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    with tempfile.TemporaryDirectory(prefix='robotomy-lifecycle-') as tmp:
        root = Path(tmp)
        name = 'RobotomyAI-Game-' + hashlib.sha256(str(root).lower().encode()).hexdigest()[:12].upper()
        (root/'.venv/Scripts').mkdir(parents=True)
        (root/'scripts').mkdir()
        shutil.copy2(ROOT/'.venv/Scripts/pythonw.exe', root/'.venv/Scripts/pythonw.exe')
        shutil.copy2(ROOT/'.venv/pyvenv.cfg', root/'.venv/pyvenv.cfg')
        (root/'scripts/launch_live.py').write_text('''import json, os, time, subprocess, sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
if '--child' not in sys.argv:
    child=subprocess.Popen([sys.executable, __file__, '--child'])
    (root/'worker.json').write_text(json.dumps({'worker':os.getpid(),'child':child.pid}))
    child.wait()
else:
    while not (root/'stop').exists():
        (root/'heartbeat').write_text(str(time.time()))
        time.sleep(.1)
''', encoding='utf-8')
        caller_code = '''import subprocess, sys, time
from pathlib import Path
root=Path(sys.argv[1])
while not (root/'go').exists(): time.sleep(.05)
r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-File',sys.argv[2],'-Root',str(root)],capture_output=True)
(root/'request.txt').write_bytes(r.stdout+b'\\n'+r.stderr)
(root/'result').write_text(str(r.returncode))
while True: time.sleep(1)
'''
        caller = None
        try:
            caller = subprocess.Popen([sys.executable, '-c', caller_code, str(root),
                str(ROOT/'scripts/start_game_task.ps1')], creationflags=subprocess.CREATE_NO_WINDOW)
            if not kernel.AssignProcessToJobObject(job, w.HANDLE(caller._handle)):
                raise ctypes.WinError(ctypes.get_last_error())
            (root/'go').touch()
            wait_for(lambda: (root/'result').exists())
            if (root/'result').read_text() != '0':
                raise RuntimeError((root/'request.txt').read_bytes().decode('utf-8', errors='replace'))
            wait_for(lambda: (root/'worker.json').exists() and (root/'heartbeat').exists())
            before = (root/'heartbeat').stat().st_mtime_ns
            identities = json.loads((root/'worker.json').read_text())
            repeated = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive',
                '-WindowStyle','Hidden','-File',str(ROOT/'scripts/start_game_task.ps1'),
                '-Root',str(root)], capture_output=True)
            assert repeated.returncode == 0, repeated.stderr
            assert b'already_running' in repeated.stdout, repeated.stdout
            if not kernel.TerminateJobObject(job, 91):
                raise ctypes.WinError(ctypes.get_last_error())
            caller.wait(timeout=10)
            wait_for(lambda: (root/'heartbeat').stat().st_mtime_ns > before)
            time.sleep(1)
            assert (root/'heartbeat').stat().st_mtime_ns > before
            print(json.dumps(dict(result='passed', caller_exit=caller.returncode,
                worker_and_child_survived_caller_job_termination=True, duplicate_ignored=True, **identities)))
        finally:
            (root/'stop').touch()
            if caller is not None and caller.poll() is None:
                kernel.TerminateJobObject(job, 92)
                caller.wait(timeout=10)
            kernel.CloseHandle(job)
            time.sleep(1)
            subprocess.run(['schtasks.exe','/Delete','/TN',name,'/F'], capture_output=True)


if __name__ == '__main__':
    main()
