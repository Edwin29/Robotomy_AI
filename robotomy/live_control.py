"""Durable, bounded UI decisions. VirtualExecutor performs game-local input."""
import json
from pathlib import Path
import time
import uuid
from datetime import datetime, timezone
from .live import LiveReader


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


class LiveControl:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.directory = self.root / '.robotomy/live/control'
        self.reader = LiveReader(root)

    def _read(self, name):
        return json.loads((self.directory / name).read_text(encoding='utf-8'))

    def _event(self, kind, **data):
        event = {'id': uuid.uuid4().hex, 'kind': kind,
                 'at': datetime.now(timezone.utc).isoformat(), **data}
        atomic(self.directory / 'events' / (str(time.time_ns()) + '_' + event['id'] + '.json'), event)
        from .experience import record
        event['experience_recording'] = record(self.root, 'control_' + kind, event)
        return event

    def _note(self):
        events = self.timeline()
        note = self.root / 'vault/Live/Current-control.md'
        note.parent.mkdir(parents=True, exist_ok=True)
        # A projection only. Original immutable events remain under control/events.
        note.write_text('# 실제 UI 조작 관찰\n\n선언된 선택 이유이며 내부 사고 과정의 증명이 아닙니다.\n\n'
            + '\n\n'.join('    ' + json.dumps(e, ensure_ascii=False) for e in events), encoding='utf-8')

    def timeline(self):
        return [json.loads(p.read_text(encoding='utf-8'))
                for p in sorted((self.directory / 'events').glob('*.json'))[-100:]]

    def view(self):
        status = self.reader.status()
        if status['status'] != 'live':
            raise ValueError('Live exporter is not fresh: ' + status['status'])
        view = self._read('view.json')
        if time.time() - view['captured_epoch'] > 30 or view['captured_epoch'] > time.time() + 5:
            raise ValueError('Control screenshot expired; capture a fresh control view.')
        if view['process_id'] != status['process_id']:
            raise ValueError('Process changed; capture again.')
        return view

    def prepare(self, view_id, kind, rationale='', expected='', x=None, y=None, key=None, scroll_y=None,
                duration_ms=80, to_x=None, to_y=None, employee_token=None):
        view = self.view()
        if view['id'] != view_id:
            raise ValueError('View changed; inspect the new screenshot first.')
        native = view.get('backend') in {'native_win32', 'virtual_unity'}
        kinds = {'click', 'right_click', 'key', 'scroll', 'move', 'drag', 'right_drag'} if native else {'click', 'right_click', 'key', 'scroll'}
        if isinstance(kind, str):
            kind = kind.strip().lower()
        if not isinstance(kind, str) or kind not in kinds:
            raise ValueError('Unsupported input kind. Use: ' + ', '.join(sorted(kinds)))
        if type(duration_ms) is not int or not 20 <= duration_ms <= (3000 if native else 80):
            raise ValueError('Input duration must be 20..3000 ms (local executor).')
        if not all(isinstance(v, str) and len(v) <= 1000 for v in (rationale, expected)):
            raise ValueError('Rationale and expected result must be strings up to 1000 characters; empty means unrecorded.')
        if kind == 'key':
            # UI key labels use capitals; virtual input uses canonical game key names.
            if isinstance(key, str):
                key = key.strip().lower()
                key = {'esc': 'Escape', 'escape': 'Escape', 'return': 'Return',
                       'enter': 'Return', 'spacebar': 'space'}.get(key, key)
            if not isinstance(key, str) or key not in {'space', 'pause_only', 'Escape', 'Return', '1', '2', '3', 'w', 'a', 's', 'd', 'f', 'g'}:
                raise ValueError('Unsupported key. Use W/A/S/D/F/G, Space, Escape, Enter/Return, 1/2/3 (case-insensitive).')
        elif any(type(v) not in (int, float) for v in (x, y)) or not (0 <= x < view['width'] and (0 if native else 24) <= y < view['height']):
            raise ValueError('Pointer must be inside the captured game client.')
        if kind in {'drag', 'right_drag'} and (any(type(v) not in (int, float) for v in (to_x, to_y)) or not (0 <= to_x < view['width'] and 0 <= to_y < view['height'])):
            raise ValueError('Drag endpoint must be inside the captured game client.')
        if kind == 'scroll' and (type(scroll_y) is not int or not 1 <= abs(scroll_y) <= 600):
            raise ValueError('Scroll must be a nonzero integer within 600 units.')
        # Do not let irrelevant arguments reach the stricter Unity parser. For example,
        # to_x on a click used to be accepted here and rejected only after dispatch.
        extras = {}
        if kind == 'key': extras.update(x=x, y=y)
        else: extras['key'] = key
        if kind not in {'drag', 'right_drag'}: extras.update(to_x=to_x, to_y=to_y)
        if kind != 'scroll': extras['scroll_y'] = scroll_y
        supplied = [name for name, value in extras.items() if value is not None]
        if supplied:
            raise ValueError('Arguments not used by ' + kind + ': ' + ', '.join(supplied) + '. Omit these arguments.')
        if employee_token is not None:
            if kind != 'click' or view.get('backend') != 'virtual_unity':raise ValueError('Employee target requires virtual left click')
            self._id(employee_token)
        now = time.time()
        expires = min(now + 25, view['captured_epoch'] + 30)
        if native and expires - now < duration_ms / 1000 + .25:
            raise ValueError('Control view has insufficient time for this gesture; capture a fresh view.')
        decision = {'id': uuid.uuid4().hex, 'view_id': view_id, 'kind': kind, 'x': x, 'y': y, 'key': key, 'scroll_y':scroll_y,
            'duration_ms': duration_ms, 'to_x': to_x, 'to_y': to_y,
            'rationale': rationale, 'expected': expected, 'created_epoch': now,
            'expires_epoch': expires,
            'process_id': view['process_id'], 'scene': view['scene'], 'bridge_id': view['bridge_id'],
            'screenshot_id': view['screenshot_id'], 'window_id': view['window_id']}
        if employee_token is not None:decision['employee_token']=employee_token
        if kind == 'scroll' and view.get('backend') == 'virtual_unity':
            decision['scroll_info'] = {
                'units_per_notch': 120, 'notches': scroll_y / 120,
                'direction': 'down' if scroll_y > 0 else 'up',
                'note': ('Wheel delta, not notch count: -120=one notch up, -240=two up; '
                         '+120=one down. Small values such as -2 may barely move the UI. '
                         'duration_ms does not repeat the wheel. Inspect the resulting frame.')}
        atomic(self.directory / 'decisions' / (decision['id'] + '.json'), decision)
        self._event('decision', decision=decision)
        return decision

    @staticmethod
    def _id(value):
        if not isinstance(value, str) or len(value) != 32 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Invalid decision id.')
        return value

    def execute(self, decision_id):
        decision_id = self._id(decision_id)
        receipt_path = self.directory / 'receipts' / (decision_id + '.json')
        if receipt_path.exists():
            return json.loads(receipt_path.read_text(encoding='utf-8'))
        if (self.directory / 'claims' / (decision_id + '.json')).exists():
            return {'id': decision_id, 'status': 'unknown', 'reason': 'Already claimed; never automatically replay.'}
        decision = self._read('decisions/' + decision_id + '.json')
        view = self.view()
        if (self.directory / 'PAUSED').exists():
            raise ValueError('Operator paused live input.')
        if time.time() > decision['expires_epoch'] or view['id'] != decision['view_id']:
            raise ValueError('Decision expired or view changed; observe again.')
        barrier = self.directory / 'not-before.json'
        if barrier.exists() and decision['created_epoch'] <= json.loads(barrier.read_text())['epoch']:
            raise ValueError('Decision predates operator control change; observe again.')
        request = self.directory / 'request.json'
        if request.exists():
            current = self._read('request.json')
            if current['id'] == decision_id:
                return {'id': decision_id, 'status': 'queued'}
            raise ValueError('Another command is pending; resolve it before queuing another.')
        # Exclusive creation prevents concurrent clients from overwriting the pending command.
        self.directory.mkdir(parents=True, exist_ok=True)
        with request.open('x', encoding='utf-8') as stream:
            json.dump(decision, stream, ensure_ascii=False)
        self._event('queued', decision_id=decision_id)
        return {'id': decision_id, 'status': 'queued', 'next': 'VirtualExecutor.execute_one; then verify fresh screen.'}

    def receipt(self, decision_id):
        decision_id = self._id(decision_id)
        path = self.directory / 'receipts' / (decision_id + '.json')
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
        return {'id': decision_id, 'status': 'unknown' if (self.directory / 'claims' / (decision_id + '.json')).exists() else 'pending'}

    def outcome(self, decision_id, observation_id, result):
        decision_id = self._id(decision_id)
        receipt = self.receipt(decision_id)
        if receipt['status'] not in {'input_sent', 'unknown'}:
            raise ValueError('No input attempt to assess.')
        if not isinstance(result, str) or not 1 <= len(result) <= 2000:
            raise ValueError('A concise observed result is required.')
        records = self.root / '.robotomy/live/observations.jsonl'
        observation = next((json.loads(line) for line in reversed(records.read_text(encoding='utf-8').splitlines())
                            if json.loads(line)['id'] == observation_id), None)
        if observation is None:
            raise ValueError('Unknown actual-game observation id.')
        decision = self._read('decisions/' + decision_id + '.json')
        snapshot = observation['snapshot']
        captured = datetime.fromisoformat(snapshot['captured_at_utc'].replace('Z', '+00:00')).timestamp()
        attempt_time = datetime.fromisoformat(receipt['at'].replace('Z', '+00:00')).timestamp() if receipt.get('at') else decision['created_epoch']
        if captured < attempt_time or snapshot['process_id'] != decision['process_id']:
            raise ValueError('Outcome observation must follow this input in the same process.')
        return self._event('outcome', decision_id=decision_id, observation_id=observation_id, result=result,
            boundary='Human/model assessment of screen evidence; input_sent alone is not task success.')

    def pause(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / 'PAUSED').write_text('operator stop', encoding='utf-8')
        atomic(self.directory / 'not-before.json', {'epoch':time.time()})
        return self._event('operator_pause')

    def resume(self):
        # Operator-only: invalidate all older decisions, including a pending request.
        atomic(self.directory / 'not-before.json', {'epoch':time.time()})
        (self.directory / 'PAUSED').unlink(missing_ok=True)
        return self._event('operator_resume', requires='New screenshot and decision')
