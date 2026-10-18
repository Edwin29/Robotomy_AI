"""Bounded local Windows input. No Codex, sky, model API or browser dependency."""
import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone

from .live_control import LiveControl, atomic


KEYS = {'space': 0x20, 'Escape': 0x1B, 'Return': 0x0D,
        **{c: ord(c.upper()) for c in 'wasdfg123'}}


class InputStopped(RuntimeError):
    pass


def run_gesture(api, decision, guard):
    """Every down has a finally-up, including cancellation and partial failure."""
    def wait(seconds):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            guard()
            time.sleep(min(.01, max(0, until - time.monotonic())))
        guard()

    kind = decision['kind']
    duration = decision.get('duration_ms', 80) / 1000
    guard()
    if kind == 'key':
        # Do not release a key that the human was already holding.
        if api.key_pressed(decision['key']):
            raise InputStopped('Requested key is already physically held.')
        try:
            api.key(decision['key'], False)
            wait(duration)
        finally:
            api.key(decision['key'], True)
        return
    api.move(decision['x'], decision['y'])
    guard()
    if kind == 'move':
        return
    if kind == 'scroll':
        api.scroll(decision['scroll_y'])
        return
    right = kind in {'right_click', 'right_drag'}
    if api.button_pressed(right):
        raise InputStopped('Mouse button is already physically held.')
    try:
        api.button(right, False)
        if kind in {'drag', 'right_drag'}:
            started = time.monotonic()
            while True:
                guard()
                ratio = min(1, (time.monotonic() - started) / duration)
                api.move(decision['x'] + (decision['to_x'] - decision['x']) * ratio,
                         decision['y'] + (decision['to_y'] - decision['y']) * ratio)
                if ratio == 1:
                    break
                time.sleep(.01)
        else:
            wait(duration)
    finally:
        api.button(right, True)


class Win32Input:
    def __init__(self, root, snapshot):
        if os.name != 'nt':
            raise RuntimeError('The local input executor requires Windows.')
        self.root = Path(root)
        self.snapshot = snapshot
        self.user = C.WinDLL('user32', use_last_error=True)
        self.kernel = C.WinDLL('kernel32', use_last_error=True)
        self._declare()
        # Apply per-thread DPI awareness, including when called from an MCP worker thread.
        self.previous_dpi = self.user.SetThreadDpiAwarenessContext(C.c_void_p(-4))
        try:
            self._connect(snapshot)
        except Exception:
            self.close()
            raise

    def _connect(self, snapshot):
        self.pid = snapshot['process_id']
        manifest = json.loads((self.root / '.robotomy/live/isolation.json').read_text(encoding='utf-8'))
        expected = self.root / '.robotomy/runtime/LobotomyCorp/LobotomyCorp.exe'
        if not manifest.get('prepared') or Path(manifest['runtime']).resolve() != expected.parent.resolve():
            raise InputStopped('Runtime is not the prepared private copy.')
        if Path(snapshot['isolation']['persistent_data_path']).resolve() != Path(manifest['isolated_save_path']).resolve():
            raise InputStopped('Save identity does not match the isolation manifest.')
        handle = self.kernel.OpenProcess(0x1000, False, self.pid)
        if not handle:
            raise C.WinError(C.get_last_error())
        try:
            size = W.DWORD(32768)
            buf = C.create_unicode_buffer(size.value)
            if not self.kernel.QueryFullProcessImageNameW(handle, 0, buf, C.byref(size)):
                raise C.WinError(C.get_last_error())
            if Path(buf.value).resolve() != expected.resolve():
                raise InputStopped('PID does not belong to the private game executable.')
        finally:
            self.kernel.CloseHandle(handle)
        windows = []
        @self.enum_proc
        def visit(hwnd, unused):
            pid = W.DWORD()
            self.user.GetWindowThreadProcessId(hwnd, C.byref(pid))
            if pid.value == self.pid and self.user.IsWindowVisible(hwnd) and not self.user.GetWindow(hwnd, 4):
                windows.append(hwnd)
            return True
        self.user.EnumWindows(visit, 0)
        if len(windows) != 1:
            raise InputStopped('Expected exactly one visible private game window.')
        self.hwnd = windows[0]
        self.geometry = self.get_geometry()

    def _declare(self):
        def sig(dll, name, result, *args):
            fn = getattr(dll, name); fn.restype = result; fn.argtypes = list(args)
        self.enum_proc = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
        sig(self.kernel, 'OpenProcess', W.HANDLE, W.DWORD, W.BOOL, W.DWORD)
        sig(self.kernel, 'QueryFullProcessImageNameW', W.BOOL, W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD))
        sig(self.kernel, 'CloseHandle', W.BOOL, W.HANDLE)
        sig(self.kernel, 'CreateMutexW', W.HANDLE, C.c_void_p, W.BOOL, W.LPCWSTR)
        sig(self.kernel, 'WaitForSingleObject', W.DWORD, W.HANDLE, W.DWORD)
        sig(self.kernel, 'ReleaseMutex', W.BOOL, W.HANDLE)
        sig(self.kernel, 'GetCurrentThreadId', W.DWORD)
        sig(self.user, 'EnumWindows', W.BOOL, self.enum_proc, W.LPARAM)
        sig(self.user, 'GetWindowThreadProcessId', W.DWORD, W.HWND, C.POINTER(W.DWORD))
        for name in ('IsWindowVisible', 'IsIconic', 'SetForegroundWindow'):
            sig(self.user, name, W.BOOL, W.HWND)
        sig(self.user, 'GetWindow', W.HWND, W.HWND, W.UINT)
        sig(self.user, 'GetForegroundWindow', W.HWND)
        sig(self.user, 'AttachThreadInput', W.BOOL, W.DWORD, W.DWORD, W.BOOL)
        sig(self.user, 'BringWindowToTop', W.BOOL, W.HWND)
        sig(self.user, 'GetClientRect', W.BOOL, W.HWND, C.POINTER(W.RECT))
        sig(self.user, 'ClientToScreen', W.BOOL, W.HWND, C.POINTER(W.POINT))
        sig(self.user, 'WindowFromPoint', W.HWND, W.POINT)
        sig(self.user, 'GetAncestor', W.HWND, W.HWND, W.UINT)
        sig(self.user, 'SetCursorPos', W.BOOL, C.c_int, C.c_int)
        sig(self.user, 'GetCursorPos', W.BOOL, C.POINTER(W.POINT))
        sig(self.user, 'GetAsyncKeyState', C.c_short, C.c_int)
        sig(self.user, 'MapVirtualKeyW', W.UINT, W.UINT, W.UINT)
        sig(self.user, 'SetThreadDpiAwarenessContext', C.c_void_p, C.c_void_p)
        class Mouse(C.Structure):
            _fields_ = [('dx', W.LONG), ('dy', W.LONG), ('mouseData', W.DWORD),
                        ('dwFlags', W.DWORD), ('time', W.DWORD), ('dwExtraInfo', C.c_size_t)]
        class Key(C.Structure):
            _fields_ = [('wVk', W.WORD), ('wScan', W.WORD), ('dwFlags', W.DWORD),
                        ('time', W.DWORD), ('dwExtraInfo', C.c_size_t)]
        class Hardware(C.Structure):
            _fields_ = [('uMsg', W.DWORD), ('wParamL', W.WORD), ('wParamH', W.WORD)]
        class Payload(C.Union):
            _fields_ = [('mi', Mouse), ('ki', Key), ('hi', Hardware)]
        class Input(C.Structure):
            _anonymous_ = ('data',)
            _fields_ = [('type', W.DWORD), ('data', Payload)]
        self.Input, self.Key, self.Mouse = Input, Key, Mouse
        sig(self.user, 'SendInput', W.UINT, W.UINT, C.POINTER(Input), C.c_int)

    def close(self):
        if self.previous_dpi:
            self.user.SetThreadDpiAwarenessContext(self.previous_dpi)
            self.previous_dpi = None

    def get_geometry(self):
        if self.user.IsIconic(self.hwnd):
            raise InputStopped('Game window is minimized.')
        rect, point = W.RECT(), W.POINT(0, 0)
        if not self.user.GetClientRect(self.hwnd, C.byref(rect)) or not self.user.ClientToScreen(self.hwnd, C.byref(point)):
            raise InputStopped('Cannot read client geometry.')
        if rect.right <= 0 or rect.bottom <= 0:
            raise InputStopped('Empty game client.')
        return [point.x, point.y, rect.right, rect.bottom]

    def activate(self):
        current = self.kernel.GetCurrentThreadId()
        foreground = self.user.GetWindowThreadProcessId(self.user.GetForegroundWindow(), None)
        attached = current != foreground and self.user.AttachThreadInput(current, foreground, True)
        try:
            self.user.BringWindowToTop(self.hwnd)
            self.user.SetForegroundWindow(self.hwnd)
        finally:
            if attached:
                self.user.AttachThreadInput(current, foreground, False)
        until = time.monotonic() + .5
        while self.user.GetForegroundWindow() != self.hwnd and time.monotonic() < until:
            time.sleep(.01)
        self.guard()

    def guard(self):
        pid = W.DWORD()
        self.user.GetWindowThreadProcessId(self.hwnd, C.byref(pid))
        if pid.value != self.pid or self.user.GetForegroundWindow() != self.hwnd:
            raise InputStopped('Game lost focus or PID changed; released held inputs.')
        if self.geometry != self.get_geometry():
            raise InputStopped('Window moved or resized; recapture before input.')
        if self.user.GetAsyncKeyState(0x77) & 0x8000:  # F8
            raise InputStopped('F8 emergency stop.')
        if any(self.user.GetAsyncKeyState(k) & 0x8000 for k in (0x10, 0x11, 0x12, 0x5B, 0x5C)):
            raise InputStopped('Human modifier key held; refusing combined OS shortcuts.')

    def key_pressed(self, key):
        return bool(self.user.GetAsyncKeyState(KEYS[key]) & 0x8000)

    def button_pressed(self, right):
        return bool(self.user.GetAsyncKeyState(2 if right else 1) & 0x8000)

    def move(self, x, y):
        self.guard()
        left, top, width, height = self.geometry
        screen = self.snapshot['screen']
        px = left + min(width - 1, int(x * width / screen['width']))
        py = top + min(height - 1, int(y * height / screen['height']))
        hit = self.user.WindowFromPoint(W.POINT(px, py))
        if self.user.GetAncestor(hit, 2) != self.hwnd:
            raise InputStopped('Target point is covered by another window.')
        if not self.user.SetCursorPos(px, py):
            raise C.WinError(C.get_last_error())

    def _send(self, value):
        if self.user.SendInput(1, C.byref(value), C.sizeof(self.Input)) != 1:
            raise C.WinError(C.get_last_error())

    def key(self, key, up):
        value = self.Input(type=1)
        value.ki = self.Key(0, self.user.MapVirtualKeyW(KEYS[key], 0), 8 | (2 if up else 0), 0, 0)
        self._send(value)

    def button(self, right, up):
        flag = (0x10 if up else 8) if right else (4 if up else 2)
        value = self.Input(type=0); value.mi = self.Mouse(0, 0, 0, flag, 0, 0)
        self._send(value)

    def scroll(self, amount):
        # Positive API amount scrolls down, matching the earlier project contract.
        value = self.Input(type=0); value.mi = self.Mouse(0, 0, (-amount) & 0xFFFFFFFF, 0x800, 0, 0)
        self._send(value)


class NativeExecutor:
    def __init__(self, root):
        self.control = LiveControl(root)
        self.root = self.control.root

    def _snapshot(self):
        status, snapshot = self.control.reader._read()
        if snapshot is None:
            raise InputStopped('Fresh isolated game observation required: ' + status['status'])
        return snapshot

    def capture(self):
        snapshot = self._snapshot()
        status, frame = self.control.reader.frame()
        if frame is None:
            raise InputStopped('Fresh game frame required: ' + str(status))
        api = Win32Input(self.root, snapshot)
        try:
            view_id = uuid.uuid4().hex
            view = {'id': view_id, 'backend': 'native_win32', 'coordinate_space': 'unity_client_pixels',
                    'captured_epoch': time.time(), 'process_id': snapshot['process_id'],
                    'scene': snapshot['scene'], **snapshot['screen'], 'window_id': api.hwnd,
                    'geometry': api.geometry, 'bridge_id': 'native_win32_v1',
                    'screenshot_id': view_id, 'sequence': snapshot['sequence']}
            directory = self.control.directory / 'views'
            directory.mkdir(parents=True, exist_ok=True)
            (directory / (view_id + '.png')).write_bytes(frame)
            atomic(directory / (view_id + '.json'), view)
            atomic(self.control.directory / 'view.json', view)
            return {'view': view, 'frame_path': str(directory / (view_id + '.png')), 'snapshot': snapshot}
        finally:
            api.close()

    def execute(self, decision_id):
        queued = self.control.execute(decision_id)
        if queued['status'] != 'queued':
            return queued
        return self.execute_one()

    def execute_one(self):
        control = self.control
        request = control.directory / 'request.json'
        if not request.exists():
            return {'status': 'idle'}
        decision = json.loads(request.read_text(encoding='utf-8'))
        identity = control._id(decision['id'])
        claim = control.directory / 'claims' / (identity + '.json')
        claim.parent.mkdir(parents=True, exist_ok=True)
        try:
            with claim.open('x', encoding='utf-8') as stream:
                json.dump({'executor_pid': os.getpid(), 'claimed_epoch': time.time()}, stream)
        except FileExistsError:
            return control.receipt(identity)
        attempted, api, mutex, acquired = False, None, None, False
        started = time.monotonic()
        try:
            view = control.view()
            if view.get('backend') != 'native_win32' or view['id'] != decision['view_id']:
                raise InputStopped('A fresh native control view is required.')
            if time.time() > decision['expires_epoch']:
                raise InputStopped('Decision expired.')
            snapshot = self._snapshot()
            if snapshot['scene'] != decision['scene']:
                raise InputStopped('Scene changed; observe again.')
            api = Win32Input(self.root, snapshot)
            if api.hwnd != decision['window_id'] or api.geometry != view['geometry']:
                raise InputStopped('Target window or geometry changed.')
            mutex = api.kernel.CreateMutexW(None, False, 'Local\\RobotomyNativeInput')
            if not mutex:
                raise C.WinError(C.get_last_error())
            acquired = api.kernel.WaitForSingleObject(mutex, 0) in (0, 0x80)
            if not acquired:
                raise InputStopped('Another executor owns the input device.')
            def guard():
                if (control.directory / 'PAUSED').exists():
                    raise InputStopped('Operator paused input.')
                barrier = control.directory / 'not-before.json'
                if barrier.exists() and decision['created_epoch'] < json.loads(barrier.read_text())['epoch']:
                    raise InputStopped('Decision predates operator control change.')
                if time.monotonic() - started > 8:
                    raise InputStopped('Input execution time limit reached.')
                api.guard()
            # Original-save verification is independent of the input backend.
            checked = subprocess.run([sys.executable, str(self.root / 'scripts/launch_live.py'), '--verify-only'],
                cwd=self.root, stdin=subprocess.DEVNULL, capture_output=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW)
            if checked.returncode:
                raise InputStopped('Original save integrity verification failed; input blocked.')
            if (control.directory / 'PAUSED').exists():
                raise InputStopped('Operator paused input.')
            api.activate()
            guard()
            attempted = True
            run_gesture(api, decision, guard)
            point = W.POINT()
            api.user.GetCursorPos(C.byref(point))
            result = {'status': 'input_sent', 'pointer_screen': [point.x, point.y],
                      'key_released': not api.key_pressed(decision['key']) if decision['kind'] == 'key' else None}
        except Exception as exc:
            result = {'status': 'unknown' if attempted else 'rejected', 'reason': str(exc)}
            if isinstance(exc, InputStopped) and 'F8' in str(exc):
                control.pause()
        finally:
            if api:
                if acquired: api.kernel.ReleaseMutex(mutex)
                if mutex: api.kernel.CloseHandle(mutex)
                api.close()
        receipt = {'id': identity, **result, 'backend': 'native_win32',
                   'at': datetime.now(timezone.utc).isoformat(),
                   'elapsed_ms': round((time.monotonic() - started) * 1000),
                   'boundary': 'Input delivery only; inspect a subsequent observation for success.'}
        atomic(control.directory / 'receipts' / (identity + '.json'), receipt)
        control._event('input_receipt', receipt=receipt, status=receipt['status'], decision_id=identity)
        request.unlink(missing_ok=True)
        return receipt
