"""Bounded game-local input. Never calls SendInput, SetCursorPos or foreground APIs."""
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from .live_control import LiveControl, atomic


def read_json(path):
    # Mono File.Replace briefly denies sharing on Windows; retry reads only.
    for attempt in range(5):
        try: return json.loads(path.read_text(encoding='utf-8-sig'))
        except PermissionError:
            if attempt == 4: raise
            time.sleep(.02)


def verify_process(pid, expected):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle: raise ValueError('Target process unavailable.')
    try:
        text = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(text))
        if not kernel.QueryFullProcessImageNameW(handle, 0, text, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        if Path(text.value).resolve() != expected.resolve():
            raise ValueError('Target is not the isolated game executable.')
    finally: kernel.CloseHandle(handle)


def encode_command(decision, view):
    values = [decision['id'], decision['process_id'], decision['scene'], view['width'], view['height'],
              decision['expires_epoch'], decision['kind'], decision.get('key') or '',
              decision.get('x') or 0, decision.get('y') or 0, decision.get('to_x') or 0,
              decision.get('to_y') or 0, 'v1', decision['duration_ms'], decision.get('scroll_y') or 0,
              decision['created_epoch']]
    if any('\n' in str(v) or '\r' in str(v) for v in values):
        raise ValueError('Invalid protocol field.')
    return '\n'.join(map(str, values))


class VirtualExecutor:
    def __init__(self, root):
        self.control = LiveControl(root)
        self.root = self.control.root

    def _snapshot(self):
        status, snapshot = self.control.reader._read()
        if snapshot is None: raise ValueError('Fresh isolated observation required: ' + status['status'])
        manifest = json.loads((self.root / '.robotomy/live/isolation.json').read_text(encoding='utf-8'))
        runtime = self.root / '.robotomy/runtime/LobotomyCorp'
        if not manifest.get('prepared') or Path(manifest['runtime']).resolve() != runtime.resolve():
            raise ValueError('Unrecognized private runtime.')
        if Path(snapshot['isolation']['persistent_data_path']).resolve() != Path(manifest['isolated_save_path']).resolve():
            raise ValueError('Save path mismatch.')
        verify_process(snapshot['process_id'], runtime / 'LobotomyCorp.exe')
        state = read_json(self.control.directory / 'virtual-status.json')
        if state['backend'] != 'virtual_unity' or state['process_id'] != snapshot['process_id'] or not 0 <= time.time()-state['at_epoch'] <= 5 or state['patched_methods'] < 1:
            raise ValueError('Virtual game input is unavailable or stale. No OS fallback.')
        return snapshot

    def capture(self):
        snapshot = self._snapshot()
        status, frame = self.control.reader.frame()
        for _ in range(4):
            if frame is not None or status.get('reason') != 'frame_unreadable': break
            time.sleep(.02)
            status, frame = self.control.reader.frame()
        if frame is None: raise ValueError('Fresh game frame required: ' + str(status))
        if status.get('process_id') != snapshot['process_id'] or status.get('scene') != snapshot['scene']:
            raise ValueError('Scene or process changed while capturing; observe again.')
        # frame() reads its own fresh snapshot. A resize between those two reads
        # must not associate new PNG coordinates with an older control view.
        dimensions = {'width':int.from_bytes(frame[16:20], 'big'),
                      'height':int.from_bytes(frame[20:24], 'big')}
        if dimensions != snapshot['screen']:
            raise ValueError('Resolution changed while capturing; observe again.')
        identity = uuid.uuid4().hex
        view = {'id': identity, 'backend': 'virtual_unity', 'coordinate_space': 'unity_client_pixels',
                'captured_epoch': time.time(), 'process_id': snapshot['process_id'], 'scene': snapshot['scene'],
                **snapshot['screen'], 'window_id': snapshot['process_id'], 'bridge_id': 'virtual_unity_v1',
                'screenshot_id': identity, 'sequence': snapshot['sequence']}
        directory = self.control.directory / 'views'
        directory.mkdir(parents=True, exist_ok=True)
        (directory / (identity+'.png')).write_bytes(frame)
        atomic(directory / (identity+'.json'), view)
        atomic(self.control.directory / 'view.json', view)
        from .experience import record
        response = {'view': view, 'frame_path': str(directory / (identity+'.png')), 'snapshot': snapshot}
        response['experience_recording'] = record(self.root, 'control_view_offered',
            {**response, 'image_delivery':'reference_only_not_proof_of_viewing'}, frame)
        return response

    def execute(self, decision_id):
        queued = self.control.execute(decision_id)
        return self.execute_one() if queued['status'] == 'queued' else queued

    def hover(self, view_id, x, y, settle_ms=500):
        """Move only, then return a post-settle frame. Never choose a target or click.

        A successful transport receipt is not a claim that a tooltip appeared.
        Keep the input lease until observation so another sequence cannot move the
        pointer between the gesture and its evidence. No Unity internals are read.
        """
        from robotomy.input_sequence import input_lock
        from .experience import record
        if type(settle_ms) is not int or not 200 <= settle_ms <= 1500:
            raise ValueError('settle_ms must be 200..1500.')
        with input_lock(self.root):
            view = self.control.view()
            decision = self.control.prepare(view_id, 'move', x=x, y=y, duration_ms=20)
            receipt = self.execute(decision['id'])
            result = {'decision_id': decision['id'], 'receipt': receipt,
                      'status': 'input_not_confirmed', 'clicked': False,
                      'boundary': 'Pointer stays at the requested coordinate. Inspect the returned image for hover feedback; no tooltip is guaranteed.'}
            if receipt['status'] != 'input_sent':
                return result, None
            # Host time after acknowledgement avoids relying on a cached frame
            # from before the move. A bounded read wait never retries the input.
            earliest = time.time() + settle_ms / 1000
            deadline = time.monotonic() + settle_ms / 1000 + 3
            data = None
            result['status'] = 'observation_unavailable'
            while time.monotonic() < deadline:
                if (self.control.directory/'PAUSED').exists():
                    result['status'] = 'operator_paused'
                    break
                try:
                    status, candidate = self.control.reader.frame()
                except (OSError, ValueError) as exc:
                    result['observation_error'] = str(exc)
                    break
                if status.get('status') == 'live':
                    if (status.get('process_id') != view['process_id'] or
                            status.get('scene') != view['scene'] or
                            (candidate is not None and
                             (int.from_bytes(candidate[16:20], 'big'), int.from_bytes(candidate[20:24], 'big')) !=
                             (view['width'], view['height']))):
                        result['status'] = 'context_changed'
                        break
                    captured = status.get('frame_captured_at_utc')
                    try:
                        captured_epoch = datetime.fromisoformat(captured.replace('Z', '+00:00')).timestamp() if captured else 0
                    except (ValueError, AttributeError):
                        captured_epoch = 0
                    if candidate is not None and captured_epoch >= earliest:
                        result.update(status='frame_returned', frame=status)
                        data = candidate
                        break
                time.sleep(.05)
            # This is the actual offered frame, not a lookup of hidden tooltip text.
            result['experience_recording'] = record(self.root, 'hover_frame_offered', result.copy(), data)
            return result, data

    def execute_one(self):
        control = self.control
        request = control.directory / 'request.json'
        if not request.exists(): return {'status': 'idle'}
        decision = json.loads(request.read_text(encoding='utf-8'))
        identity = control._id(decision['id'])
        claim = control.directory / 'claims' / (identity+'.json')
        claim.parent.mkdir(parents=True, exist_ok=True)
        try:
            with claim.open('x', encoding='utf-8') as stream:
                json.dump({'executor_pid': os.getpid(), 'claimed_epoch': time.time()}, stream)
        except FileExistsError: return control.receipt(identity)
        started, attempted = time.monotonic(), False
        try:
            view = control.view()
            if view.get('backend') != 'virtual_unity' or view['id'] != decision['view_id']:
                raise ValueError('A fresh virtual control view is required.')
            snapshot = self._snapshot()
            if snapshot['scene'] != decision['scene'] or snapshot['screen'] != {k:view[k] for k in ('width','height')}:
                raise ValueError('Scene or resolution changed; observe again.')
            checked = subprocess.run([sys.executable, str(self.root/'scripts/launch_live.py'), '--verify-only'],
                cwd=self.root, stdin=subprocess.DEVNULL, capture_output=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW)
            if checked.returncode: raise ValueError('Original save integrity failed; input blocked.')
            if (control.directory/'PAUSED').exists(): raise ValueError('Operator paused input.')
            barrier = control.directory/'not-before.json'
            if barrier.exists() and decision['created_epoch'] <= json.loads(barrier.read_text())['epoch']:
                raise ValueError('Decision predates operator control change.')
            if time.time() + decision['duration_ms']/1000 + .25 > decision['expires_epoch']:
                raise ValueError('Insufficient time for gesture before expiry; capture and prepare again.')
            command = control.directory/'virtual-command.txt'
            if command.exists(): raise ValueError('Unresolved virtual command; never overwrite.')
            temp = command.with_suffix('.'+identity+'.tmp')
            temp.write_text(encode_command(decision, view), encoding='ascii', newline='\n')
            temp.rename(command)  # Windows rename refuses to overwrite a concurrent command.
            attempted = True
            ack = control.directory/'virtual-acks'/(identity+'.json')
            deadline = time.monotonic()+6
            while time.monotonic()<deadline:
                if ack.exists():
                    result = read_json(ack)
                    if result['id'] != identity or result['process_id'] != decision['process_id'] or not result.get('released'):
                        raise ValueError('Invalid game acknowledgement.')
                    break
                time.sleep(.03)
            else:
                control.pause()
                raise TimeoutError('Game acknowledgement timed out; input paused, never replay automatically.')
        except Exception as exc:
            result = {'status': 'unknown' if attempted else 'rejected', 'reason': str(exc)}
        receipt = {**result, 'id':identity, 'backend':'virtual_unity', 'at':datetime.now(timezone.utc).isoformat(),
                   'elapsed_ms':round((time.monotonic()-started)*1000),
                   'boundary':'Virtual input delivery only; inspect subsequent actual screen for success.'}
        atomic(control.directory/'receipts'/(identity+'.json'), receipt)
        control._event('input_receipt',receipt=receipt,status=receipt['status'],decision_id=identity)
        request.unlink(missing_ok=True)
        return receipt
