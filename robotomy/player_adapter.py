"""AI-oriented view over the existing UI executor. No game policy or hidden lookup."""
import copy
import io
import json
import re
import threading
import time
import uuid
from pathlib import Path
from .experience import record
from .appearance import VisualNames
from .live_control import atomic
from .quick_input import QuickInput, TargetError, targets, context
from .live import command_window, reading_panels


def compact_row(row):
    row=copy.deepcopy(row)
    for key in ('track_id','click','screen_velocity','camera_velocity','interval_ms','bounds'):
        row.pop(key,None)
    for key in ('position','object_velocity'):
        if isinstance(row.get(key),dict):row[key]={k:round(v,1) for k,v in row[key].items()}
    for key in ('hp_bar','sp_bar'):
        if row.get(key):row[key]={'ratio':round(row[key]['ratio'],2)}
    return row


def model_state(state):
    result=copy.deepcopy(state)
    for key in ('employees','entities'):
        result[key]={k:compact_row(v) for k,v in state.get(key,{}).items()}
    result['facilities']={k:{'ref':k,**v} for k,v in state.get('facilities',{}).items()}
    window=result.get('command_window')
    if window:
        for row in window.get('work_types',[]):
            if row.get('click'):row['action']=['L','work:'+row['name']];row.pop('click')
        for row in window.get('employees',[]):
            if row.get('click'):row['action']=['L',row.get('ref','row:'+row['row_id'])];row.pop('click')
    # Native button IDs are carried as directly callable refs, not separate coordinate tables.
    result['actions']=[{'ref':'button:'+k,'label':v['text'],'panel':v.get('panel'),'role':v.get('role')}
                       for k,v in state.get('buttons',{}).items()]
    management=result.get('hazards',{}).get('creature_management')
    if management:
        result['management_tips']={'visible_only':True,'items':[r for r in management.get('details',[]) if r.get('kind')=='management_tip'],'unlock_options':[{**r,'action':['L',[r['x'],r['y']]]} for r in management.get('costs',[]) if r.get('kind')=='unlock'],'scroll_up':['S','management:list',-3] if any(r.get('kind')=='management_tip' and 'x' in r for r in management.get('details',[])) else None,'scroll_down':['S','management:list',3] if any(r.get('kind')=='management_tip' and 'x' in r for r in management.get('details',[])) else None}
    else:result['management_tips']=None
    result.pop('buttons',None);result.pop('motion_status',None)
    if 'screen_context' in result:result['screen_context'].pop('actions',None)
    return result


class PlayerAdapter:
    def __init__(self,root,reader,quick):
        self.root=Path(root);self.reader=reader;self.quick=quick;self.previous=None;self.identity=None
        self.quick.record_offers=False
        self.lock=threading.RLock();self.jobs={};self.visual_names=VisualNames(root)

    def pack(self,raw,action=None,full=False,record_view=True):
        observation=raw.get('observation') or raw
        state=observation.get('_adapter_state',getattr(getattr(self.reader,'_delivery',None),'state',None))
        if state is None or not observation.get('id'):
            return {'schema':'player_view_v1','status':raw.get('status','unavailable'),'action':action,'reason':raw.get('reason')}
        current=self.visual_names.decorate(model_state(state),offered=record_view)
        identity=observation.get('_adapter_identity',getattr(self.reader._delivery,'identity',None))
        reset=full or self.previous is None or identity!=self.identity
        before={} if reset else self.previous
        updated={};removed={}
        keyed={'employees','entities','facilities','creature_appearances'}
        for key,value in current.items():
            if key in keyed:
                old=before.get(key,{})
                changed=[v for k,v in value.items() if old.get(k)!=v]
                if changed:updated[key]=changed
                gone=[{'ref':v.get('ref',k),'name':v.get('name'),'reason':'no_longer_observed'} for k,v in old.items() if k not in value]
                if gone:removed[key]=gone
            elif before.get(key)!=value or reset:updated[key]=value
        response={'schema':'player_view_v1','view':observation['id'],'mode':'full' if reset else 'update',
                  'at':observation['captured_at_utc'],'action':action,'alerts':observation.get('alerts',[]),
                  'events':observation.get('event_delivery',{}),'combat':observation.get('combat',{}),
                  'updated':updated,'left_view':removed,'audio':raw.get('audio',raw.get('audio_delivery',{}))}
        pending=[{'id':j['id'],'status':j['status'],'completed':j['next']} for j in self.jobs.values() if j['status']=='running' or len(j['results'])>j.get('delivered',0)]
        if pending:response['schedules']=pending
        # A scheduled step is not yet offered to the player. Keep the public
        # baseline until a direct read, so polling observation cannot skip it.
        if record_view:self.previous=copy.deepcopy(current);self.identity=identity
        if record_view:response['record']=record(self.root,'player_view_offered',response.copy())
        return response

    def observe(self,full=False):
        with self.lock:return self.pack(self.reader.brief(wait_ms=0,record_offer=False),full=full)

    def validate(self,item):
        if not isinstance(item,dict) or item.get('kind') not in ('input','move','work','state'):raise ValueError('kind must be input, move, work or state')
        kind=item['kind'];required={'input':('command',),'move':('employee','destination'),'work':('employee','room','work'),'state':('setting','value')}[kind]
        if any(k not in item for k in required):raise ValueError('Missing action field')
        if kind=='input':
            c=item['command']
            if isinstance(c,list) and c and c[0]=='S':
                from .quick_input import scroll_command
                scroll_command(c);return
            if not isinstance(c,list) or len(c)!=2 or c[0] not in ('L','R','H','K','Z'):raise ValueError('Invalid gesture')
            if c[0]=='Z':
                from .quick_input import zoom_gesture
                zoom_gesture(c[1])
            elif not isinstance(c[1],str) and not (c[0]!='K' and isinstance(c[1],list) and len(c[1])==2 and all(type(v) in (int,float) for v in c[1])):raise ValueError('Invalid target')
        if kind in ('work','move') and any(not isinstance(item[k],str) or not item[k] for k in required):raise ValueError('Targets must be nonempty refs or names')
        if kind=='state':
            s,v=item['setting'],item['value']
            if s=='paused' and v is not True:raise ValueError('Resume by explicitly choosing speed')
            if s=='speed' and (type(v) not in (int,float) or v not in (1,1.5,2)):raise ValueError('Speed must be 1, 1.5 or 2')
            if s=='gift_locked' and (type(v)is not bool or not isinstance(item.get('target'),str)):raise ValueError('Gift needs target and boolean value')
            if s not in ('paused','speed','gift_locked'):raise ValueError('Unknown state setting')

    def set_state(self,item):
        from robotomy.input_sequence import input_lock
        with input_lock(self.root):
            s=self.quick.executor._snapshot();setting=item['setting'];value=item['value'];ref=None
            if setting in ('paused','speed'):
                wanted='paused' if setting=='paused' else {1:'1x',1.5:'1.5x',2:'2x'}[value]
                shown=[t['text'] for t in s.get('ui_texts',[]) if t.get('panel')=='playback']
                if wanted in shown:return self.quick.offered({'status':'already_set','setting':setting,'value':value},s,'ready')
                matches=[t for t in targets(s) if t.get('label')==wanted]
                if not matches and shown:
                    # Moving our pointer clears the speed tooltip, which can cover
                    # neighbouring buttons. This is a hover only, never a blind click.
                    deferred=getattr(self.quick,'_defer_offer',False);self.quick._defer_offer=True
                    try:self.quick.input(['H',[s['screen']['width']/2,s['screen']['height']/2]],_locked=True)
                    finally:self.quick._defer_offer=deferred
                    s=self.quick.executor._snapshot()
                    matches=[t for t in targets(s) if t.get('label')==wanted]
                if len(matches)!=1:raise TargetError('state_control_unavailable',wanted,[])
                ref=matches[0]['ref']
            else:
                gifts=reading_panels(s).get('gifts') or {};slots=gifts.get('slots',{})
                row=next((r for r in slots.values() if (r.get('lock_click') or {}).get('ref')==item['target']),None)
                if row is None:raise TargetError('gift_not_available',item['target'],[])
                if row.get('locked')==value:return self.quick.offered({'status':'already_set'},s,'ready')
                ref=item['target']
            result=self.quick.input(['L',ref],_locked=True)
            _,after=self.reader._read();observed=None
            if after is not None:
                if setting in ('paused','speed'):
                    shown=[t['text'] for t in after.get('ui_texts',[]) if t.get('panel')=='playback']
                    observed=wanted in shown
                else:
                    slots=(reading_panels(after).get('gifts') or {}).get('slots',{})
                    row=next((r for r in slots.values() if (r.get('lock_click') or {}).get('ref')==item['target']),None)
                    if row is not None:observed=row.get('locked')==value
            result['requested_state']={'setting':setting,'value':value,'confirmed':observed}
            return result

    def action(self,item,request_id=None,record_view=True):
        self.validate(item)
        if request_id is None:request_id=uuid.uuid4().hex
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',request_id):raise ValueError('Invalid request_id')
        with self.lock:
            path=self.root/'.robotomy/live/control/adapter-requests'/f'{request_id}.json'
            if path.exists():
                prior=json.loads(path.read_text(encoding='utf8'))
                if prior['request']!=item:raise ValueError('request_id reused for different action')
                return self.pack(self.reader.brief(wait_ms=0,record_offer=False),{'request_id':request_id,'dispatch':'not_repeated','previous':prior['result']},record_view=record_view)
            atomic(path,{'request':item,'result':{'dispatch':'started_outcome_unconfirmed'}})
            try:
                if item['kind']=='input':raw=self.quick.input(item['command'])
                elif item['kind']=='move':raw=self.quick.move(item['employee'],item['destination'])
                elif item['kind']=='work':raw=self.quick.intents([item])
                else:raw=self.set_state(item)
                outcome={'request_id':request_id,'dispatch':raw.get('status',raw.get('stopped','unknown')),
                         'ui':raw.get('result_status'),'movement':raw.get('movement')}
                if raw.get('results'):outcome['steps']=[{'status':r.get('status',r.get('result',{}).get('status')),'reason':r.get('reason')} for r in raw['results']]
                if any(r.get('status') in ('not_completed','stopped','unknown') for r in outcome.get('steps',[])):outcome['dispatch']='stopped'
                if raw.get('reason'):outcome['reason']=raw['reason']
                if raw.get('requested_state'):outcome['state']=raw['requested_state']
                atomic(self.root/'.robotomy/live/adapter-traces'/f'{request_id}.json',raw)
                outcome['trace']=request_id
            except ValueError as exc:
                raw=self.reader.brief(wait_ms=0,record_offer=False)
                outcome={'request_id':request_id,'dispatch':'not_completed','error':getattr(exc,'detail',{'code':'input_unavailable','message':str(exc)})}
            atomic(path,{'request':item,'result':outcome})
            return self.pack(raw,outcome,record_view=record_view)

    def schedule(self,items):
        if not isinstance(items,list) or not 1<=len(items)<=5:raise ValueError('Use 1..5 actions')
        for item in items:self.validate(item)
        with self.lock:
            if any(j['status']=='running' for j in self.jobs.values()):raise ValueError('A schedule is already running')
            initial=context(self.quick.executor._snapshot());key=uuid.uuid4().hex
            if len(self.jobs)>=32:self.jobs.pop(next(iter(self.jobs)))
            job={'id':key,'status':'running','next':0,'results':[],'cancel':False};self.jobs[key]=job
            marker=self.root/'.robotomy/live/control/pause-generation'
            generation=marker.read_text() if marker.exists() else None
        def run():
            deadline=time.monotonic()+10
            for i,item in enumerate(items):
                if job['cancel'] or time.monotonic()>deadline:job['status']='cancelled' if job['cancel'] else 'deadline';break
                try:
                    if (marker.read_text() if marker.exists() else None)!=generation:job['status']='pause_barrier';break
                    if context(self.quick.executor._snapshot())!=initial:job['status']='context_changed';break
                    value=self.action(item,key+'_'+str(i),record_view=False);job['results'].append(value);job['next']=i+1
                    if value.get('action',{}).get('dispatch') in ('not_completed','stopped','unknown'):job['status']='stopped';break
                except Exception as exc:job['status']='stopped';job['reason']=str(exc);break
            else:job['status']='finished'
        threading.Thread(target=run,name='player-input-schedule',daemon=True).start()
        return {'id':key,'status':'accepted'}

    def schedule_status(self,key,cancel=False):
        if key not in self.jobs:raise ValueError('Unknown schedule')
        job=self.jobs[key]
        if cancel:job['cancel']=True
        # Return exact offered views: inspecting status must not discard intervening events.
        response=copy.deepcopy(job)
        job['delivered']=len(response['results'])
        response['record']=record(self.root,'player_schedule_offered',response.copy())
        return response

    def images(self,target,count=1):
        from .history import HistoryReader
        from .live import validate_snapshot
        import hashlib
        from PIL import Image
        if type(count)is not int or not 1<=count<=6:raise ValueError('Use 1..6 frames')
        h=HistoryReader(self.root);pairs=[]
        if count>1:
            try:
                index=h._index();records=[r for r in index['records'] if r['has_frame']][-(count-1):]
                for entry in records:
                    snap=h._sample(index,entry);meta,data=h.frame(index['session'],entry['sequence'])
                    if data:pairs.append((snap,meta,data))
            except (OSError,ValueError,KeyError):pass
        status,snapshot=self.reader._read()
        if snapshot is not None:
            meta,data=self.reader.frame_after(snapshot['captured_at_utc'])
            try:
                paired=json.loads((self.root/'.robotomy/live/frame-motion.json').read_text(encoding='utf8'))
                if data and paired['sha256']==hashlib.sha256(data).hexdigest() and paired['session']==snapshot.get('console',{}).get('session'):
                    pairs.append((validate_snapshot(paired['snapshot'])[0],meta,data))
            except (OSError,ValueError,KeyError):pass
        output=[]
        for snapshot,meta,data in pairs:
            bounds=None
            for t in snapshot.get('console',{}).get('motion',{}).get('tracks',[]):
                if target=='unit:'+t.get('entity_id',''):bounds=t['bounds'];break
            if bounds is None:
                from .quick_input import resolve
                try:p=resolve(snapshot,target)
                except ValueError:continue
                bounds={'x':p['x']-100,'y':p['y']-80,'width':200,'height':160}
            im=Image.open(io.BytesIO(data));x,y,w,ht=(bounds[k] for k in ('x','y','width','height'))
            box=(max(0,int(x-40)),max(0,int(y-40)),min(im.width,int(x+w+40)),min(im.height,int(y+ht+40)))
            if box[0]>=box[2] or box[1]>=box[3]:continue
            buf=io.BytesIO();im.crop(box).save(buf,format='PNG');meta.update(target=target,crop=list(box),at=snapshot['captured_at_utc'])
            record(self.root,'target_frame_offered',meta,buf.getvalue());output.append((meta,buf.getvalue()))
        return output


def register(server,root,live,quick):
    import asyncio
    from mcp.server.fastmcp import Image
    adapter=PlayerAdapter(root,live,QuickInput(root,live,quick.executor));server._player_adapter=adapter
    @server.tool()
    async def observe_player(full:bool=False)->dict:
        """Compact current rows + priority events + damage groups. full=true restores the current public view after reconnect/compaction. Reuse unit: refs in every action. Missing from view is not death."""
        return await asyncio.to_thread(adapter.observe,full)
    @server.tool()
    async def player_action(action:dict,request_id:str|None=None)->dict:
        """Explicit input {kind:input,command:[L/R/H,target] or [K,key] or [Z,amount] or [S,target,signed_notches_1_to_5] (positive down)}, move {kind:move,employee,destination}, work {kind:work,employee,room,work}, state {kind:state,setting:paused/value:true or setting:speed/value:1|1.5|2 or setting:gift_locked/value:boolean/target:gift ref}. Same view response as observe_player. Optional request_id prevents duplicate execution, never reuse for a new action. Sent/ready is not arrival or work completion."""
        return await asyncio.to_thread(adapter.action,action,request_id)
    @server.tool()
    async def schedule_player_actions(actions:list[dict])->dict:
        """Schedule 1..5 explicit player_action dictionaries, bounded to 10 seconds. No policy/repetition. Re-resolves each visible target; stops on failure/scene change. Returns immediately."""
        return await asyncio.to_thread(adapter.schedule,actions)
    @server.tool()
    def player_schedule_status(schedule_id:str,cancel:bool=False)->dict:
        """Read scheduled outcomes or cancel remaining steps. Current bounded input may finish. Never reverses already sent inputs."""
        return adapter.schedule_status(schedule_id,cancel)
    @server.tool()
    async def view_target(target:str,frames:int=1):
        """Crop a visible target from 1..6 retained exact frames, older to newer, with timestamps. Historical images are not input coordinates. Unavailable target/frame is skipped; no hidden/off-camera lookup."""
        rows=await asyncio.to_thread(adapter.images,target,frames)
        return [v for meta,data in rows for v in (meta,Image(data=data,format='png'))] or {'status':'no_retained_target_frame'}
    @server.tool()
    def read_combat_events(after:int=0,limit:int=100)->dict:
        """Read retained public damage/motion/effect events in the current producer session. Values are display numbers, not HP deltas. Nearby motion links are correlations, not attacker attribution. No hidden timers."""
        from .combat import CombatDelivery,read_journal
        status,s=live._read()
        if s is None:return status
        result=read_journal(root,s['console']['session'],after,limit)
        recent=getattr(live,'_combat_delivery',CombatDelivery()).read(after,limit)
        ids={e['id'] for e in result.get('events',[])}
        result['relations']=[r for r in recent['relations'] if r['damage_event'] in ids]
        result['record']=record(root,'combat_events_offered',result.copy());return result

    @server.tool()
    def name_visual(ref:str,name:str,description:str='')->dict:
        """Name an already observed form/motion/mark ref. Empty name clears alias. Optional description is your interpretation, never a verified game effect. Persists across reconnects in the experience Playbook. Does not input to game."""
        result=adapter.visual_names.name(ref,name,description)
        record(root,'visual_alias_changed',result)
        return result
    @server.tool()
    def read_visual_names(query:str='',limit:int=20,offset:int=0)->dict:
        """Search your observed visual labels and player-authored aliases/notes. This is memory, not current visibility; use observe_player for current marks/forms."""
        result=adapter.visual_names.read(query,limit,offset)
        record(root,'visual_aliases_read',result)
        return result
