"""Bounded read-only observation of real history retention; never changes game/input."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from robotomy.history import HistoryReader
from robotomy.live import LiveReader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('label')
    parser.add_argument('--seconds', type=int, default=8)
    args = parser.parse_args()
    if not args.label.replace('-', '').isalnum() or not 1 <= args.seconds <= 45:
        raise ValueError('bounded label/duration required')
    directory = ROOT/'.robotomy/live'
    folder = directory/'verification/history'
    folder.mkdir(parents=True, exist_ok=True)
    reader, history = LiveReader(ROOT), HistoryReader(ROOT)
    start = history.read(limit=1)
    samples, indices, failures = {}, [], {}
    deadline = time.monotonic()+args.seconds
    while time.monotonic() < deadline:
        status, current = reader._read()
        if current:
            try:
                diag = json.loads((directory/'console-diagnostics.json').read_text(encoding='utf-8-sig'))
                if diag['process_id'] == current['process_id'] and diag['session'] == current['console']['session']:
                    samples[diag['unity_frame']] = diag
                index = history.read(limit=1, session=current['console']['session'])
                indices.append({k:index.get(k) for k in ('status','retained_count','oldest_sequence','newest_sequence','producer_dropped')})
            except (OSError, ValueError):
                failures['publication_race'] = failures.get('publication_race', 0)+1
        else:
            failures[status['status']] = failures.get(status['status'], 0)+1
        time.sleep(.05)
    end = history.read(limit=50)
    metrics = list(samples.values())
    costs = {}
    for key in ('motion_ms','capture_ms','last_disk_write_ms'):
        values=sorted(row[key] for row in metrics if row.get(key,0)>0)
        if values:
            costs[key]={'median':statistics.median(values),'p95':values[min(len(values)-1,int(len(values)*.95))],'max':max(values)}
    frames=[]
    for row in end['records']:
        if row['has_frame']:
            info,data=history.frame(end['session'],row['sequence'])
            frames.append(info)
            if data:
                (folder/f'{args.label}-{row["sequence"]}.png').write_bytes(data)
    result={'basis':'read_only_actual_runtime','label':args.label,'seconds':args.seconds,
            'start':{k:v for k,v in start.items() if k!='records'},
            'end':{k:v for k,v in end.items() if k!='records'},'observed_latest_frames':len(metrics),
            'history_active_values':sorted(set(row['history_active'] for row in metrics)),
            'retention_unchanged': bool(indices) and len({(r['retained_count'],r['oldest_sequence'],r['newest_sequence']) for r in indices})==1,
            'costs':costs,'frame_checks':frames,'failures':failures,
            'sample_files':len(list((directory/'history').glob('sample-*.json'))),
            'frame_files':len(list((directory/'history').glob('frame-*.png'))),
            'history_errors':max((row['history_errors'] for row in metrics),default=None),
            'publication_errors':max((row['publication_errors'] for row in metrics),default=None)}
    (folder/f'{args.label}.json').write_text(json.dumps({'summary':result,'metrics':metrics,'indices':indices,'history':end},ensure_ascii=False),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__': main()
