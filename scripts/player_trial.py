"""Manual model-driven trial: one console action or observation per invocation.

No game internals, scripted policy, native input, or automatic action retry.
Optional previous_result assesses the last action against this new observation.
"""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from robotomy.virtual_input import VirtualExecutor


def main():
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    command = json.load(sys.stdin)
    executor = VirtualExecutor(ROOT)
    folder = ROOT / '.robotomy/live/player-trial'
    folder.mkdir(exist_ok=True)
    wait = command.pop('observe_after_seconds', 2)
    if type(wait) not in (int, float) or not 0 <= wait <= 10:
        raise ValueError('Wait must be 0..10 seconds.')
    assessment = command.pop('previous_result', None)
    if assessment:
        previous = json.loads((folder / 'last-action.json').read_text(encoding='utf-8'))
        observed = executor.control.reader.observe()
        executor.control.outcome(previous['decision_id'], observed['observation_id'], assessment)
    result = {}
    if command:
        captured = executor.capture()
        decision = executor.control.prepare(captured['view']['id'], **command)
        receipt = executor.execute(decision['id'])
        result.update(decision_id=decision['id'], receipt=receipt)
        (folder / 'last-action.json').write_text(json.dumps(result), encoding='utf-8')
    time.sleep(wait)
    observed = executor.control.reader.observe()
    status, image = executor.control.reader.frame()
    if image is None:
        raise RuntimeError(status)
    frame_path = folder / (observed['observation_id'] + '.png')
    frame_path.write_bytes(image)
    result.update(observation=observed, frame_status=status, frame_path=str(frame_path))
    with (folder / 'steps.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(result, ensure_ascii=False) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
