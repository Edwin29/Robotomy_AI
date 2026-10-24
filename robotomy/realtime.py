"""Bounded observation journal and opt-in, one-shot pause reservations."""
import copy
import json
from pathlib import Path
import threading
import time
import uuid
from collections import deque
from datetime import datetime,timezone

CONDITIONS={'meltdown_cycle','employee_death','escape_confirmed'}

def now():return datetime.now(timezone.utc).isoformat()

def context(s):return (s['process_id'],s['scene'],s.get('console',{}).get('session'),s.get('console',{}).get('signal_epoch',0))

class Realtime:
    def __init__(self,root,reader,quick):
        self.root=Path(root);self.reader=reader;self.quick=quick
        self.guard=threading.RLock();self.changed=threading.Condition(self.guard);self.events=deque(maxlen=512)
        self.journal_id=uuid.uuid4().hex;self.delivery_cursor=0;self.wait_generation=0
        self.serial=0;self.sample=-1;self.signal=0;self.identity=None;self.dead=set();self.reservations={};self.thread=None;self.stop=threading.Event()
        self.pending=self.root/'.robotomy/live/control/pause-pending';self.barrier=self.root/'.robotomy/live/control/pause-generation'
    def limit(self):
        p=self.root/'.robotomy/live/operator-policy.json'
        try:n=json.loads(p.read_text(encoding='utf-8'))['pause_slots']
        except (OSError,ValueError,KeyError):n=1
        return n if type(n) is int and n in (1,2) else 1
    def start(self):
        with self.guard:
            if self.thread is None:
                self.thread=threading.Thread(target=self.run,daemon=True,name='robotomy-events');self.thread.start()
    def append(self,kind,at,**data):
        self.serial+=1;e={'journal_id':self.journal_id,'id':self.serial,'kind':kind,'observed_at':at,**data};self.events.append(e);self.changed.notify_all()
        # Engineering journal is separate from evidence actually delivered to the player.
        try:
            path=self.root/'.robotomy/live/events.jsonl';path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists() and path.stat().st_size>1048576:path.replace(path.with_suffix('.previous.jsonl'))
            with path.open('a',encoding='utf-8') as stream:stream.write(json.dumps(e,ensure_ascii=False)+'\n')
        except OSError:pass
        return e
    def arm(self,condition):
        if condition not in CONDITIONS:raise ValueError('Choose meltdown_cycle, employee_death or escape_confirmed')
        status,s=self.reader._read()
        if not s or status.get('status')!='live' or s['scene']!='Main':raise ValueError('Fresh Main scene required')
        if condition!='employee_death' and 'signals' not in s.get('console',{}):raise ValueError('Visible-event producer patch required')
        # Establish the baseline before registration. Existing incidents never trigger a new arm.
        self.ingest(s)
        with self.guard:
            active=[r for r in self.reservations.values() if r['status']=='armed']
            if any(r['condition']==condition for r in active):raise ValueError('Condition already armed')
            if len(active)>=self.limit():raise ValueError('Operator pause slot limit reached')
            token=uuid.uuid4().hex;r={'id':token,'condition':condition,'status':'armed','armed_at':now(),'after':self.serial}
            self.reservations[token]=r;answer=copy.deepcopy(r)
            for key in list(self.reservations):
                if len(self.reservations)<=128:break
                if self.reservations[key]['status']!='armed':del self.reservations[key]
        self.start();return answer
    def cancel(self,identity=None):
        with self.guard:
            for key,r in self.reservations.items():
                if (identity is None or identity==key) and r['status']=='armed':r['status']='cancelled'
            return self.status()
    def status(self):
        with self.guard:return {'journal_id':self.journal_id,'limit':self.limit(),'reservations':copy.deepcopy(list(self.reservations.values())[-32:]),'cursor':self.serial}
    def ingest(self,s):
        fired=[]
        with self.guard:
            c=s.get('console',{});identity=context(s);deaths={r['employee_id'] for r in c.get('dead_employees',[])}
            if identity!=self.identity:
                for r in self.reservations.values():
                    if r['status']=='armed':r['status']='context_changed'
                self.identity=identity;self.sample=s['sequence'];self.signal=max((e['id'] for e in c.get('signals',[])),default=0);self.dead=deaths
                self.append('context_changed',s['captured_at_utc']);return
            if s['sequence']<=self.sample:return
            self.sample=s['sequence']
            new=[];signals=[e for e in c.get('signals',[]) if e['id']>self.signal]
            if signals and signals[0]['id']>self.signal+1:self.append('event_gap',s['captured_at_utc'])
            for e in signals:
                extra={k:e[k] for k in ('room_id','room_label') if k in e} if e['kind']=='room_narration' else {}
                new.append(self.append(e['kind'],e['at'],text=e['text'],**extra));self.signal=e['id']
            for r in c.get('dead_employees',[]):
                if r['employee_id'] not in self.dead:new.append(self.append('employee_death',s['captured_at_utc'],employee=r))
            self.dead=deaths
            for e in new:
                for r in self.reservations.values():
                    if r['status']=='armed' and r['condition']==e['kind'] and e['id']>r['after']:
                        r.update(status='consumed',trigger=e['id'],fired_at=now());fired.append(r['id'])
            if fired:
                self.pending.parent.mkdir(parents=True,exist_ok=True);self.pending.write_text('one-shot',encoding='utf-8')
                self.barrier.write_text(uuid.uuid4().hex,encoding='ascii')
        if fired:
            try:result=self.pause(identity)
            except Exception as exc:result={'status':'failed','reason':type(exc).__name__}
            with self.guard:
                for key in fired:self.reservations[key]['result']=result
                self.append('pause_result',now(),reservations=fired,result=result)
    def pause(self,identity):
        from robotomy.input_sequence import input_lock
        result={'status':'not_sent'}
        try:
            deadline=time.monotonic()+4
            while True:
                if self.stop.is_set():return {'status':'cancelled'}
                try:
                    with input_lock(self.root,priority=True):
                        status,s=self.reader._read()
                        if s is None or status.get('status')!='live' or context(s)!=identity:return {'status':'context_unavailable'}
                        playback=[x['text'] for x in s.get('ui_texts',[]) if x.get('panel')=='playback']
                        if 'paused' in playback:return {'status':'already_paused'}
                        if not any(x in playback for x in ('1x','1.5x','2x')):return {'status':'playback_unknown'}
                        from .quick_input import QuickInput
                        dispatch=QuickInput(self.root,self.reader,self.quick.executor);dispatch._pause_dispatch=True
                        receipt=dispatch.gesture(s,'key',key='pause_only')
                        # No retries of the toggle; verify from later rendered playback state.
                        result={'status':'not_confirmed','receipt':receipt}
                        if receipt.get('status')=='input_sent':
                            after,ready=self.quick.wait(s,receipt,lambda n:any(t.get('panel')=='playback' and t['text']=='paused' for t in n.get('ui_texts',[])))
                            if ready=='ready':result['status']='paused'
                        return result
                except ValueError as e:
                    if 'Another input' not in str(e) or time.monotonic()>=deadline:return {'status':'not_sent','reason':str(e)}
                    time.sleep(.03)
        finally:self.pending.unlink(missing_ok=True)
    def offer(self,snapshot=None):
        with self.guard:
            if self.identity is None and snapshot is not None:self.ingest(snapshot)
        self.start()
        with self.guard:
            cursor=self.delivery_cursor;self.delivery_cursor=self.serial
            return {'journal_id':self.journal_id,'events':[copy.deepcopy(e) for e in self.events if e['id']>cursor], 'cursor':self.serial,
                    'gap':bool(self.events and cursor<self.events[0]['id']-1)}
    def cancel_wait(self):
        with self.changed:
            self.wait_generation+=1;self.changed.notify_all()
        return {'status':'waits_cancelled'}
    def run(self):
        while not self.stop.wait(.1):
            try:
                status,s=self.reader._read()
                if s is not None and status.get('status')=='live':self.ingest(s)
            except Exception as e:
                with self.guard:
                    self.cancel();self.append('monitor_error',now(),error=type(e).__name__)
    def wait(self,conditions,timeout_s=20,after=None):
        if not conditions or any(c not in CONDITIONS|{'pause_result'} for c in conditions):raise ValueError('Unsupported event condition')
        if not 0<=timeout_s<=20:raise ValueError('timeout_s must be 0..20')
        self.start();deadline=time.monotonic()+timeout_s
        with self.changed:
            generation=self.wait_generation
            cursor=self.serial if after is None else after
            if type(cursor) is not int or cursor<0 or cursor>self.serial:raise ValueError('Invalid event cursor')
            while not self.stop.is_set() and generation==self.wait_generation:
                rows=[copy.deepcopy(e) for e in self.events if e['id']>cursor]
                if any(e['kind'] in conditions for e in rows) or time.monotonic()>=deadline:
                    return {'journal_id':self.journal_id,'events':rows,'cursor':self.serial,'gap':bool(self.events and cursor<self.events[0]['id']-1),'delivered_at':now(),'timed_out':not any(e['kind'] in conditions for e in rows)}
                self.changed.wait(min(.2,max(0,deadline-time.monotonic())))
            return {'journal_id':self.journal_id,'events':[],'cursor':self.serial,'status':'cancelled'}
    def close(self):
        self.cancel();self.stop.set()
        with self.changed:self.changed.notify_all()
        if self.thread:self.thread.join(timeout=5.5)
