"""Small, explicit gestures; no policy, hidden lookup or OS input."""
import math
import json
from pathlib import Path
from .live_control import atomic
import time
from contextlib import nullcontext
from datetime import datetime
from .live import command_window, visible_employees, visible_entities, reading_panels, urgent_alerts
from .virtual_input import VirtualExecutor
from robotomy.input_sequence import input_lock
from .experience import record


def scroll_command(command):
    if not isinstance(command,list) or len(command)!=3 or command[0]!='S':
        raise ValueError('Use [S, visible target ref or [x,y], signed notches 1..5]; positive is down')
    target,amount=command[1:]
    if type(amount) is not int or not 1<=abs(amount)<=5:raise ValueError('Scroll notches must be a nonzero integer from -5 to 5')
    if not isinstance(target,str) and not (isinstance(target,list) and len(target)==2 and all(type(v) in (int,float) and math.isfinite(v) for v in target)):raise ValueError('Invalid scroll target')
    return target,amount*120


def targets(snapshot):
    result=[]
    for b in snapshot.get('buttons',[]):
        if b.get('input_verified') and b.get('interactable') and b.get('target_id'):
            result.append({'ref':'button:'+b['target_id'],'label':b.get('text'),'kind':'button',
                           'x':b.get('hit_x',b['x']+b['width']/2),'y':b.get('hit_y',b['y']+b['height']/2)})
    for b in snapshot.get('buttons',[]):
        if b.get('panel')=='gift' and b.get('input_verified') and b.get('interactable'):
            result.append({'ref':'gift:'+b['row_id']+':'+b['role'],'label':b['text'],'kind':'gift','x':b['hit_x'],'y':b['hit_y'],'target_id':b['target_id']})
    for row in (command_window(snapshot) or {}).get('work_types',[]):
        if row.get('click'):result.append({'ref':'work:'+row['name'],'label':row['name'],'kind':'work',**row['click']})
    for row in (command_window(snapshot) or {}).get('employees',[]):
        if row.get('click'):result.append({'ref':'row:'+row['row_id'],'label':row['name'],'kind':'row',**row['click']})
        if row.get('click') and row.get('ref'):result.append({'ref':row['ref'],'label':row['name'],'kind':'row',**row['click']})
    for row in visible_employees(snapshot):
        if row.get('click'):result.append({'ref':'employee:'+row['track_id'],'label':row.get('name'),'kind':'employee',**row['click']})
        if row.get('click'):result.append({'ref':'unit:'+row['entity_id'],'native_ref':'employee:'+row['track_id'],'label':row.get('name'),'kind':'employee',**row['click']})
    for row in visible_entities(snapshot):
        if row.get('click'):result.append({'ref':'entity:'+row['track_id'],'label':row.get('name'),'kind':'entity',**row['click']})
        if row.get('click'):result.append({'ref':'unit:'+row['entity_id'],'native_ref':'entity:'+row['track_id'],'label':row.get('name'),'kind':'entity',**row['click']})
    for row in snapshot.get('console',{}).get('hazards',{}).get('room_status',[]):
        if row.get('info_click'):
            result.append({'ref':'room_info:'+row['room_id'],'label':row.get('room_label'),'kind':'room_info',**row['info_click']})
    fm=snapshot.get('console',{}).get('facility_map',{})
    known={x['id']:x for x in fm.get('known',{}).get('landmarks',[])}
    for row in fm.get('visible',[]):
        if row.get('click'):result.append({'ref':row['id'],'label':known.get(row['id'],{}).get('label'),'kind':'facility',**row['click']})
    management=snapshot.get('console',{}).get('hazards',{}).get('creature_management') or {}
    tips=[d for d in management.get('details',[]) if d.get('kind')=='management_tip' and 'x' in d]
    if tips:result.append({'ref':'management:list','label':'관리법 목록','kind':'scroll','x':tips[0]['x'],'y':tips[0]['y']})
    return result


def resolve(snapshot,ref,kind=None):
    rows=targets(snapshot)
    if kind:rows=[r for r in rows if r['kind']==kind]
    exact=[r for r in rows if r['ref']==ref]
    matches=exact or [r for r in rows if r['label']==ref]
    if kind is None and any(r['kind']=='row' for r in matches):matches=[r for r in matches if r['kind']=='row']
    # The same native button can have both button: and work:/row: aliases.
    unique={(r['x'],r['y']):r for r in matches}
    if len(unique)!=1:raise TargetError('ambiguous' if unique else 'not_available',ref,[{'ref':r['ref'],'label':r['label']} for r in list(unique.values())[:8]])
    return next(iter(unique.values()))


class TargetError(ValueError):
    def __init__(self,code,target,candidates):
        self.detail={'code':code,'target':target,'candidates':candidates}
        super().__init__('Target missing or ambiguous; '+json.dumps(self.detail,ensure_ascii=False))


def native_ref(target):return target.get('native_ref',target['ref'])


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
        'other_text':[{'panel':t.get('panel'),'text':t['text']} for t in snapshot.get('ui_texts',[]) if t.get('panel') not in ('command','playback','ego','creature_record','gift')],
        **{k:v for k,v in panels.items() if v}}


def context(s):return (s['process_id'],s['scene'],s['screen'])
def timestamp(s):return datetime.fromisoformat(s['captured_at_utc'].replace('Z','+00:00')).timestamp()


def zoom_gesture(amount):
    """A short native F/G hold; amount is input strength, not magnification."""
    if type(amount) is not int or not 1 <= abs(amount) <= 5:
        raise ValueError('Use [Z, amount]: integer +1..+5 zooms in, -1..-5 zooms out.')
    return {'key': 'f' if amount > 0 else 'g', 'duration_ms': 300 * abs(amount)}


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
        if getattr(self,'_defer_offer',False):return {**result,'result_status':readiness}
        response={**result,'result_status':readiness,'result_status_basis':'ui_readiness_not_action_completion',
                  'observation':self.reader.deliver(snapshot,include_state=True) if snapshot and not getattr(self,'record_offers',True) else self.reader.deliver(snapshot) if snapshot else None,'current':None}
        if snapshot:
            from .perception import compact_audio
            response['audio_delivery']=compact_audio(self.reader.offer_audio(snapshot))
        if getattr(self,'record_offers',True):response['experience_recording']=record(self.root,'action_result_offered',response.copy())
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
        from pathlib import Path
        if (Path(self.root)/'.robotomy/live/control/pause-pending').exists() and not getattr(self,'_pause_dispatch',False):raise ValueError('Pause reservation firing')
        c=self.executor.capture(record_observation=False,include_frame=False)
        if context(c['snapshot'])!=context(snapshot):raise ValueError('Screen context changed; no input sent.')
        if target_ref is not None:
            point=resolve(c['snapshot'],target_ref);args.update(x=point['x'],y=point['y'])
            if kind=='click' and point['kind'] in ('employee','entity'):args['employee_token']=native_ref(point).split(':',1)[1]
        d=self.executor.control.prepare(c['view']['id'],kind,**args)
        return self.executor.execute(d['id'])

    def input(self,command,_locked=False):
        if isinstance(command,list) and command and command[0]=='S':
            ref,units=scroll_command(command)
            with (nullcontext() if _locked else input_lock(self.root)):
                s=self.executor._snapshot()
                point=resolve(s,ref) if isinstance(ref,str) else {'x':ref[0],'y':ref[1]}
                receipt=self.gesture(s,'scroll',target_ref=ref if isinstance(ref,str) else None,x=point['x'],y=point['y'],scroll_y=units)
                return self.finish(receipt,s)
        if not isinstance(command,list) or len(command)!=2 or command[0] not in ('L','R','K','H','Z'):raise ValueError('Use [L/R/H, target ref or [x,y]], [K, key], or [Z, signed amount 1..5].')
        op,ref=command
        zoom=zoom_gesture(ref) if op=='Z' else None
        with (nullcontext() if _locked else input_lock(self.root)):
            s=self.executor._snapshot();predicate=None
            if op=='Z':
                receipt=self.gesture(s,'key',**zoom)
                receipt['zoom']={'direction':'in' if ref>0 else 'out','amount':abs(ref),
                                 'meaning':'native_key_hold_not_exact_magnification'}
            elif op=='K':
                if not isinstance(ref,str):raise ValueError('Key must be text')
                receipt=self.gesture(s,'key',key=ref)
            else:
                if isinstance(ref,str):
                    t=resolve(s,ref);x,y=t['x'],t['y']
                    if t['kind']=='work':predicate=lambda n:bool((command_window(n) or {}).get('employees'))
                    elif t['kind']=='facility' and ref.startswith('containment:') and op=='L':predicate=lambda n:command_window(n) is not None
                    elif t['kind']=='employee' and op=='L':
                        selected_ref=native_ref(t)
                        predicate=lambda n:any('employee:'+e['track_id']==selected_ref and e.get('selected') for e in visible_employees(n))
                    elif t['kind']=='entity' and op=='L':
                        from .perception import selected_enemy
                        predicate=lambda n:bool(selected_enemy(n))
                elif isinstance(ref,list) and len(ref)==2:x,y=ref
                else:raise ValueError('Target must be a current ref or [x,y]')
                receipt=self.gesture(s,{'L':'click','R':'right_click','H':'move'}[op],target_ref=t['ref'] if isinstance(ref,str) else None,x=x,y=y)
            return self.finish(receipt,s,predicate)

    def move(self,employee,destination,_locked=False):
        with (nullcontext() if _locked else input_lock(self.root)):
            s=self.executor._snapshot();person=resolve(s,employee,'employee');place=resolve(s,destination,'facility')
            if place.get('button')!='right':raise ValueError('Choose a corridor/lobby destination; containment rooms are work targets.')
            # Normal left selection replaces prior selection in the shipped game.
            selected_ref=native_ref(person);receipt=self.gesture(s,'click',target_ref=person['ref'],x=person['x'],y=person['y'])
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
            if sent.get('status')=='input_sent':
                remember(self.root,fresh,selected_ref,place['ref'],sent.get('at_epoch',time.time()))
            return self.finish({**sent,'selection_receipt':receipt,'movement':'order_sent_not_arrival_confirmed'},fresh)

    def intents(self,items):
        if not isinstance(items,list) or not 1<=len(items)<=5:raise ValueError('Use 1..5 explicit intents')
        # Validate the complete plan before any input, rather than partly executing bad syntax.
        for item in items:
            if not isinstance(item,dict) or item.get('kind') not in ('move','work','input'):raise ValueError('Unknown intent')
            required={'move':('employee','destination'),'work':('employee','room','work'),'input':('command',)}[item['kind']]
            if any(k not in item for k in required):raise ValueError('Missing intent field')
            if item['kind']!='input' and any(not isinstance(item[k],str) or not item[k].strip() for k in required):raise ValueError('Intent targets must be nonempty text')
            if item['kind']=='work' and item['employee'].startswith(('row:','employee:','entity:')):raise ValueError('Use stable unit: ref or displayed unique name for work')
            if item['kind']=='input':
                command=item['command']
                if isinstance(command,list) and command and command[0]=='S':
                    scroll_command(command);continue
                if not isinstance(command,list) or len(command)!=2 or command[0] not in ('L','R','H','K','Z'):raise ValueError('Invalid input command')
                if command[0]=='Z':zoom_gesture(command[1])
                elif not isinstance(command[1],str) and not (command[0]!='K' and isinstance(command[1],list) and len(command[1])==2 and all(type(x) in (int,float) and math.isfinite(x) for x in command[1])):raise ValueError('Invalid input target')
        from pathlib import Path
        marker=Path(self.root)/'.robotomy/live/control/pause-generation'
        generation=marker.read_text() if marker.exists() else None
        worker=QuickInput(self.root,self.reader,self.executor);worker._defer_offer=True
        results=[];deadline=time.monotonic()+10
        def finish_batch(**extra):
            status,snapshot=self.reader._read()
            return self.offered({'results':results,**extra},snapshot if status.get('status')=='live' else None,'batch_finished')
        initial=context(self.executor._snapshot())
        for item in items:
            steps=[]
            if time.monotonic()>=deadline or (marker.read_text() if marker.exists() else None)!=generation:
                return finish_batch(stopped='deadline_or_pause_reservation')
            try:
                with input_lock(self.root):
                    if context(self.executor._snapshot())!=initial:return finish_batch(stopped='context_changed')
                    if item['kind']=='move':result=worker.move(item['employee'],item['destination'],_locked=True)
                    elif item['kind']=='input':result=worker.input(item['command'],_locked=True)
                    else:
                        room=resolve(self.executor._snapshot(),item['room'],'facility')
                        if not room['ref'].startswith('containment:'):raise ValueError('Work requires containment room')
                        opened=worker.input(['L',room['ref']],_locked=True);steps.append(opened)
                        if opened.get('result_status')!='ready':raise ValueError('Room menu not confirmed; dependent steps stopped')
                        chosen=worker.input(['L','work:'+item['work']],_locked=True);steps.append(chosen)
                        if chosen.get('result_status')!='ready':raise ValueError('Work menu not confirmed; dependent steps stopped')
                        rows=(command_window(self.executor._snapshot()) or {}).get('employees',[])
                        staff=[r for r in rows if r.get('ref')==item['employee']] if item['employee'].startswith('unit:') else [r for r in rows if r['name']==item['employee']]
                        if len(staff)!=1 or not staff[0].get('click'):raise ValueError('Employee row missing or ambiguous')
                        result=worker.input(['L','row:'+staff[0]['row_id']],_locked=True)
                        result['meaning']='row_clicked_not_work_start_confirmed'
                    results.append({'intent':item,'steps':steps,'result':result})
            except ValueError as exc:results.append({'intent':item,'status':'not_completed','steps':steps,'reason':str(exc)})
        return finish_batch(status='finished',meaning='Receipts and displayed results only; no success inference')


# Player command memory; never reads game destinations.
def order_identity(s):
    return [s['process_id'],s['scene'],s.get('console',{}).get('session'),s.get('console',{}).get('signal_epoch',0)]

def read_orders(root,s):
    try:
        p=Path(root)/'.robotomy/live/control/movement-orders.json'
        if p.stat().st_size>131072:return {}
        data=json.loads(p.read_text(encoding='utf8'))
        return data['orders'] if data.get('identity')==order_identity(s) else {}
    except (OSError,ValueError,KeyError):return {}

def remember(root,s,employee_ref,destination,at):
    from .live import visible_employees
    matches=[e for e in visible_employees(s) if 'employee:'+e['track_id']==employee_ref]
    if len(matches)!=1:return
    e=matches[0];key=e.get('entity_id',e['track_id'])
    orders=read_orders(root,s);orders.pop(key,None)
    orders[key]={'employee_name':e.get('name'),'destination':destination,'issued_at_epoch':at,
                 'basis':'player_command','receipt':'input_sent_not_completion'}
    orders=dict(list(orders.items())[-128:])
    atomic(Path(root)/'.robotomy/live/control/movement-orders.json',{'identity':order_identity(s),'orders':orders})

def movement_orders(root,s):
    from .live import visible_employees
    visible={e.get('entity_id',e['track_id']):e for e in visible_employees(s)}
    result={}
    for key,order in read_orders(root,s).items():
        e=visible.get(key)
        state='not_in_view'
        if e:
            loc=(e.get('facility_location') or {}).get('facility_id')
            # Being inside a destination facility is not exact path arrival.
            state='observed_in_destination_facility' if loc==order['destination'] else 'moving' if e.get('status')=='moving' else 'not_yet_confirmed'
        result[key]={**order,'observed_status':state}
    return result
