"""One locally executed, recorded action from JSON stdin; never an autonomous loop.

Convenience for a local caller that has just inspected the visible game. MCP clients
should use capture_live_control / prepare_live_action / execute_live_action instead.
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
    wait = command.pop('observe_after_seconds', 2)
    if type(wait) not in (int, float) or not 1 <= wait <= 10:
        raise ValueError('Observation delay must be 1..10 seconds.')
    executor = VirtualExecutor(ROOT)
    captured = executor.capture()
    decision = executor.control.prepare(captured['view']['id'], **command)
    receipt = executor.execute(decision['id'])
    time.sleep(wait)
    observation = executor.control.reader.observe()
    print(json.dumps({'decision_id': decision['id'], 'receipt': receipt,
        'observation_id': observation.get('observation_id'), 'snapshot': observation.get('snapshot')}, ensure_ascii=False))


if __name__ == '__main__': main()
