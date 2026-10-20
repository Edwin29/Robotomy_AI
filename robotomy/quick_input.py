"""Small, explicit gestures; no policy, hidden lookup or OS input."""
import time
from datetime import datetime
from .live import command_window, visible_employees, visible_entities, reading_panels, urgent_alerts
from .virtual_input import VirtualExecutor
from robotomy.input_sequence import input_lock
from .experience import record


def targets(snapshot):
    result=[]
    for b in snapshot.get('buttons',[]):
        if b.get('input_verified') and b.get('interactable') and b.get('target_id'):
            result.append({'ref':'button:'+b['target_id'],'label':b.get('text'),'kind':'button',
                           'x':b.get('hit_x',b['x']+b['width']/2),'y':b.get('hit_y',b['y']+b['height']/2)})
    for row in (command_window(snapshot) or {}).get('work_types',[]):
        if row.get('click'):result.append({'ref':'work:'+row['name'],'label':row['name'],'kind':'work',**row['click']})
    for row in (command_window(snapshot) or {}).get('employees',[]):
        if row.get('click'):result.append({'ref':'row:'+row['row_id'],'label':row['name'],'kind':'row',**row['click']})
    for row in visible_employees(snapshot):
        if row.get('click'):result.append({'ref':'employee:'+row['track_id'],'label':row.get('name'),'kind':'employee',**row['click']})
    fm=snapshot.get('console',{}).get('facility_map',{})
    known={x['id']:x for x in fm.get('known',{}).get('landmarks',[])}
    for row in fm.get('visible',[]):
        if row.get('click'):result.append({'ref':row['id'],'label':known.get(row['id'],{}).get('label'),'kind':'facility',**row['click']})
    return result


def resolve(snapshot,ref,kind=None):
    rows=targets(snapshot)
    if kind:rows=[r for r in rows if r['kind']==kind]
    exact=[r for r in rows if r['ref']==ref]
    matches=exact or [r for r in rows if r['label']==ref]
    # The same native button can have both button: and work:/row: aliases.
    unique={(r['x'],r['y']):r for r in matches}
    if len(unique)!=1:raise ValueError('Target missing or ambiguous; use one current target ref.')
    return next(iter(unique.values()))


def current(snapshot):
    window=command_window(snapshot)
    # Keep the grouped fields, omit the duplicate raw text for those groups.
    if window:
        common={'summary','window'}|{'result_'+r['result'] for r in window['work_results']}
        common|={r['row_id'] for r in window['employees']}
        window={**window,'text_groups':[g for g in window['text_groups'] if g['group'] not in common and not g['group'].startswith('work_')]}
    states=[x['text'] for x in snapshot.get('ui_texts',[]) if x.get('panel')=='playback']
    panels=reading_panels(snapshot)
    return {'alerts':urgent_alerts(snapshot),'scene':snapshot['scene'],'sequence':snapshot['sequence'],'captured_at_utc':snapshot['captured_at_utc'],
        'command_window':window,'targets':[{k:v for k,v in r.items() if k not in ('x','y','target_id','basis')} for r in targets(snapshot)],
        'visible_employees':visible_employees(snapshot),'visible_entities':visible_entities(snapshot),
        'playback':states,'hazards':snapshot.get('console',{}).get('hazards'),
        'gauges':snapshot.get('console',{}).get('gauges',[]),'dead_employees':snapshot.get('console',{}).get('dead_employees',[]),
        'other_text':[{'panel':t.get('panel'),'text':t['text']} for t in snapshot.get('ui_texts',[]) if t.get('panel') not in ('command','playback','ego','creature_record')],
        **{k:v for k,v in panels.items() if v}}


def context(s):return (s['process_id'],s['scene'],s['screen'])
def timestamp(s):return datetime.fromisoformat(s['captured_at_utc'].replace('Z','+00:00')).timestamp()


class QuickInput:
    def __init__(self,root,reader,executor=None):
        self.root=root;self.reader=reader;self.executor=executor or VirtualExecutor(root)

    def wait(self,before,receipt,predicate=None):
        deadline=time.monotonic()+1.2;last=None;stable=None;stable_since=None;seen_sequence=None;stable_samples=0
        threshold=receipt.get('at_epoch',0)
        while True:
            status,s=self.reader._read()
            if s is not None and timestamp(s)>threshold and s['sequence']>before['sequence']:
                last=s
                if context(s)!=context(before):return s,'context_changed'
                # Stabilize only actionable UI, not moving staff, timers or scrolling text.
                sig=[(t.get('target_id'),t.get('text'),round(t.get('hit_x',0),1),round(t.get('hit_y',0),1)) for t in s.get('buttons',[]) if t.get('interactable')]
                now=time.monotonic()
                if s['sequence']!=seen_sequence:
                    if sig!=stable:stable=sig;stable_since=now;stable_samples=1
                    else:stable_samples+=1
                    seen_sequence=s['sequence']
                if predicate is not None:
                    if predicate(s) and stable_samples>=2 and now-stable_since>=.12:return s,'ready'
                elif stable_samples>=2 and now-stable_since>=.12:return s,'ready'
            if time.monotonic()>=deadline:return last,'pending' if last else 'unavailable'
            time.sleep(.025)

    def offered(self,result,snapshot,readiness):
        response={'alerts':urgent_alerts(snapshot) if snapshot else [],**result,'result_status':readiness,'current':current(snapshot) if snapshot else None}
        if snapshot:response['audio_delivery']=self.reader.offer_audio(snapshot)
        response['experience_recording']=record(self.root,'action_result_offered',response.copy())
        return response

    def finish(self,receipt,before=None,predicate=None):
        # Never replay uncertain or failed input. The result remains explicitly separate.
        if receipt.get('status')!='input_sent':return self.offered(receipt,None,'input_not_confirmed')
        if before is None:
            status,before=self.reader._read()
            if before is None:return self.offered(receipt,None,'unavailable')
            before={**before,'sequence':-1}
        try:s,state=self.wait(before,receipt,predicate)
        except (OSError,ValueError,KeyError):s,state=None,'unavailable'
        return self.offered(receipt,s,state)

    def gesture(self,snapshot,kind,target_ref=None,**args):
        c=self.executor.capture(record_observation=False,include_frame=False)
        if context(c['snapshot'])!=context(snapshot):raise ValueError('Screen context changed; no input sent.')
        if target_ref is not None:
            point=resolve(c['snapshot'],target_ref);args.update(x=point['x'],y=point['y'])
            if kind=='click' and point['kind']=='employee':args['employee_token']=point['ref'].split(':',1)[1]
        d=self.executor.control.prepare(c['view']['id'],kind,**args)
        return self.executor.execute(d['id'])

    def input(self,command):
        if not isinstance(command,list) or len(command)!=2 or command[0] not in ('L','R','K','H'):raise ValueError('Use [L/R/H, target ref or [x,y]], or [K, key].')
        op,ref=command
        with input_lock(self.root):
            s=self.executor._snapshot();predicate=None
            if op=='K':
                if not isinstance(ref,str):raise ValueError('Key must be text')
                receipt=self.gesture(s,'key',key=ref)
            else:
                if isinstance(ref,str):
                    t=resolve(s,ref);x,y=t['x'],t['y']
                    if t['kind']=='work':predicate=lambda n:bool((command_window(n) or {}).get('employees'))
                    elif t['kind']=='facility' and ref.startswith('containment:') and op=='L':predicate=lambda n:command_window(n) is not None
                elif isinstance(ref,list) and len(ref)==2:x,y=ref
                else:raise ValueError('Target must be a current ref or [x,y]')
                receipt=self.gesture(s,{'L':'click','R':'right_click','H':'move'}[op],target_ref=t['ref'] if isinstance(ref,str) else None,x=x,y=y)
            return self.finish(receipt,s,predicate)

    def move(self,employee,destination):
        with input_lock(self.root):
            s=self.executor._snapshot();person=resolve(s,employee,'employee');place=resolve(s,destination,'facility')
            if place.get('button')!='right':raise ValueError('Choose a corridor/lobby destination; containment rooms are work targets.')
            # Normal left selection replaces prior selection in the shipped game.
            selected_ref=person['ref'];receipt=self.gesture(s,'click',target_ref=person['ref'],x=person['x'],y=person['y'])
            if receipt.get('status')!='input_sent':return self.finish(receipt,s)
            def selected(n):
                return any('employee:'+r['track_id']==selected_ref and r.get('selected') is True for r in visible_employees(n))
            after,state=self.wait(s,receipt,selected)
            if state!='ready':return self.offered({'status':'stopped','reason':'Employee selection not confirmed','selection_receipt':receipt},after,state)
            try:
                # Re-resolve both after selection, never use old screen coordinates.
                fresh=self.executor._snapshot()
                if context(fresh)!=context(s) or not selected(fresh):raise ValueError('Selection or screen changed')
                place=resolve(fresh,destination,'facility')
                sent=self.gesture(fresh,'right_click',target_ref=place['ref'],x=place['x'],y=place['y'])
            except ValueError as e:return self.offered({'status':'stopped','reason':str(e),'selection_receipt':receipt},after,'stopped')
            return self.finish({**sent,'selection_receipt':receipt,'movement':'order_sent_not_arrival_confirmed'},fresh)
