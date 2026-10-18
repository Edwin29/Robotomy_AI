"""Read-only operator latency report. Never invokes MCP, game input or model APIs."""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import re
import statistics


def timestamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def metrics(values):
    if not values: return {'count':0, 'total_seconds':0}
    values=sorted(values)
    return {'count':len(values), 'total_seconds':round(sum(values),3),
            'median_seconds':round(statistics.median(values),3),
            'p90_seconds':round(values[min(len(values)-1,int(len(values)*.9))],3)}


def analyze(source, start, end):
    calls={}; pairs=[]
    for line in Path(source).open(encoding='utf-8'):
        try: row=json.loads(line)
        except json.JSONDecodeError: continue  # Active last line may not be complete yet.
        if row.get('type')!='response_item': continue
        p=row.get('payload',{}); kind=p.get('type'); t=timestamp(row['timestamp'])
        if kind in ('custom_tool_call','function_call') and start<=t<end:
            calls[p['call_id']]={'start':t,'input':p.get('input',p.get('arguments',''))}
        elif kind in ('custom_tool_call_output','function_call_output') and p.get('call_id') in calls and t<=end:
            c=calls.pop(p['call_id']); c['end']=t; pairs.append(c)
    pairs.sort(key=lambda c:c['start'])
    waits=[]; names=Counter()
    for c in pairs:
        names.update(re.findall(r'tools\.mcp__robotomy_player__(\w+)',c['input']))
        waits.extend(int(v)/1000 for v in re.findall(r'setTimeout\([^,]+,\s*(\d+)\)',c['input']))
    gaps=[max(0,b['start']-a['end']) for a,b in zip(pairs,pairs[1:])]
    return {'window_seconds':round(end-start,3),'completed_roundtrips':metrics([c['end']-c['start'] for c in pairs]),
            'between_roundtrips':metrics(gaps),'gaps_at_least_60s':metrics([v for v in gaps if v>=60]),
            'explicit_literal_waits':metrics(waits),'tool_mentions':dict(names),'unfinished_calls':len(calls),
            'boundary':'Tool elapsed includes explicit waits. Gaps combine model/client/network/user pauses, not pure reasoning. Literal waits and tool names are static matches, not execution tracing. Compare similar scenes and separate long pauses; no gameplay speedup proven by this report.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rollout',required=True);p.add_argument('--start',required=True);p.add_argument('--end',required=True)
    p.add_argument('--output',required=True);p.add_argument('--baseline')
    args=p.parse_args(); start=timestamp(args.start);end=timestamp(args.end)
    if end<=start: p.error('end must be later than start')
    result=analyze(args.rollout,start,end)
    if args.baseline:
        old=json.loads(Path(args.baseline).read_text(encoding='utf-8'))
        result['comparison']={k:{'before':old[k],'after':result[k]} for k in
            ('completed_roundtrips','between_roundtrips','explicit_literal_waits','tool_mentions')}
        result['comparison']['note']='Different content/windows are not a controlled A/B test.'
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
