"""Bounded engineering trial through the game console, never direct model manipulation."""
import hashlib
import json
from pathlib import Path
import sys
import time
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from robotomy.virtual_input import VirtualExecutor


def main():
    command = json.load(sys.stdin)
    folder = ROOT / '.robotomy/live/verification/motion'
    folder.mkdir(parents=True, exist_ok=True)
    ex = VirtualExecutor(ROOT)
    label = command.pop('label')
    if not label.replace('-', '').replace('_', '').isalnum():
        raise ValueError('Invalid label')
    seconds = command.pop('seconds', 2)
    if not 1 <= seconds <= 30:
        raise ValueError('Bounded sample required')
    if command.pop('resume', False):
        ex.control.resume()
    if command.pop('pause', False):
        ex.control.pause()
    result = {'label': label, 'basis': 'engineering_console_trial'}
    worker = None
    if command:
        capture = ex.capture()
        decision = ex.control.prepare(capture['view']['id'], **command)
        def execute():
            try:
                result['receipt'] = ex.execute(decision['id'])
            except Exception as error:
                result['action_error'] = str(error)
        worker = threading.Thread(target=execute)
        worker.start()
    samples, frames, metrics, failures = {}, {}, {}, {}
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        status, snapshot = ex.control.reader._read()
        if snapshot:
            samples[snapshot['sequence']] = snapshot
        else:
            reason = status.get('reason', status['status'])
            failures[reason] = failures.get(reason, 0) + 1
        try:
            d = json.loads((ex.control.reader.directory / 'console-diagnostics.json').read_text(encoding='utf-8-sig'))
            metrics[d['unity_frame']] = d
            # Keep exact end-of-frame metadata with each PNG. Reject a publication race.
            fm = json.loads((ex.control.reader.directory / 'frame-motion.json').read_text(encoding='utf-8-sig'))
            data = (ex.control.reader.directory / 'frame.png').read_bytes()
            if hashlib.sha256(data).hexdigest() == fm['sha256'] and fm['unity_frame'] not in frames:
                name = f'{label}-{fm["unity_frame"]}.png'
                (folder / name).write_bytes(data)
                frames[fm['unity_frame']] = {'file': name, **fm}
        except (OSError, ValueError):
            pass
        time.sleep(.025)
    if worker is not None:
        worker.join(timeout=12)
        if worker.is_alive():
            ex.control.pause()
            raise RuntimeError('Input worker did not finish; never replay automatically')
    payload = {**result, 'samples': list(samples.values()), 'frames': list(frames.values()),
               'metrics': list(metrics.values()), 'failures': failures}
    (folder / (label + '.json')).write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    last = list(samples.values())[-1] if samples else {}
    result.update(samples=len(samples), frames=len(frames), failures=failures,
                  scene=last.get('scene'), motion=last.get('console', {}).get('motion'),
                  diagnostics=list(metrics.values())[-1].get('motion') if metrics else None,
                  frame_path=str(folder / list(frames.values())[-1]['file']) if frames else None)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
