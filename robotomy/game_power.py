"""Player power controls: fixed private runtime, graceful close, no force kill or resume."""
import ctypes
from ctypes import wintypes as w
from pathlib import Path
import subprocess
import sys
import threading
import time
from .live import LiveReader
from .live_control import LiveControl, atomic
from .observer_window import configure
from .virtual_input import verify_process


class GamePower:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.lock = threading.Lock()
        self.launcher = None

    def start(self):
        with self.lock:
            if self.launcher is not None:
                code = self.launcher.poll()
                if code is None:
                    return {'status': 'starting', 'next': 'Call start_game again later; do not send input yet.'}
                self.launcher = None
                if code != 0:
                    return {'status': 'failed', 'reason': 'Verified launcher failed; ask operator to inspect startup log.'}
            status = LiveReader(self.root).status()
            try:
                verify_process(status.get('process_id', 0), self.root/'.robotomy/runtime/LobotomyCorp/LobotomyCorp.exe')
            except (ValueError, OSError):
                pass
            else:
                return {'status': 'running', 'observation': status,
                        'input_enabled': not (self.root/'.robotomy/live/control/PAUSED').exists()}
            directory = self.root/'.robotomy/live'
            directory.mkdir(parents=True, exist_ok=True)
            # Official launcher verifies all protected saves and runtime hashes, and refuses existing games.
            with (directory/'player-startup.log').open('ab') as log:
                self.launcher = subprocess.Popen(
                    [sys.executable, '-X', 'utf8', str(self.root/'scripts/launch_live.py')],
                    cwd=self.root, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                    creationflags=subprocess.CREATE_NO_WINDOW)
            return {'status': 'starting', 'next': 'Call start_game again later to confirm readiness. Operator stop is preserved.'}

    def close(self):
        with self.lock:
            if self.launcher is not None and self.launcher.poll() is None:
                return {'status': 'starting', 'reason': 'Wait for startup to finish before closing.'}
            directory = self.root/'.robotomy/live/control'
            if any((directory/name).exists() for name in ('request.json', 'virtual-command.txt')):
                raise ValueError('Input still pending; resolve its receipt before closing.')
            # configure verifies exact executable, isolated save identity and unique titled HWND.
            window = configure(self.root)
            pid, hwnd = window['process_id'], window['window']
            verify_process(pid, self.root/'.robotomy/runtime/LobotomyCorp/LobotomyCorp.exe')
            user = ctypes.WinDLL('user32', use_last_error=True)
            user.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
            actual = w.DWORD()
            user.GetWindowThreadProcessId(hwnd, ctypes.byref(actual))
            if actual.value != pid:
                raise ValueError('Window identity changed; close rejected.')
            control = LiveControl(self.root)
            atomic(control.directory/'not-before.json', {'epoch': time.time()})
            user.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
            user.PostMessageW.restype = w.BOOL
            if not user.PostMessageW(hwnd, 0x0010, 0, 0):
                raise ctypes.WinError(ctypes.get_last_error())
            return {'status': 'close_requested', 'process_id': pid,
                    'note': 'Normal window close requested, not proof of exit or save. No force kill. Recheck game_power_status.'}

    def status(self):
        with self.lock:
            observation = LiveReader(self.root).status()
            try:
                verify_process(observation.get('process_id', 0), self.root/'.robotomy/runtime/LobotomyCorp/LobotomyCorp.exe')
                state = 'running'
            except (ValueError, OSError):
                state = 'starting' if self.launcher and self.launcher.poll() is None else 'stopped'
            return {'status': state, 'observation': observation,
                    'input_enabled': not (self.root/'.robotomy/live/control/PAUSED').exists()}
