"""Player projection and keyed deltas. No model calls or game internals."""
import copy
import threading
import uuid


def panel_rows(snapshot,panel):
    rows={}
    for t in snapshot.get('ui_texts',[]):
        if t.get('panel')!=panel:continue
        row=rows.setdefault(t['row_id'],{})
        role=t['role'];row[role]=({'x':t['x']+t['width']/2,'y':t['y']+t['height']/2} if role in ('drag_start','drop_target','click') else t['text'])
    return rows


def screen_context(snapshot):
    state=panel_rows(snapshot,'screen').get('current',{})
    if snapshot.get('scene','').startswith('Story') and not state:state={'base':'story','story_state':'transition'}
    actions=[{'ref':'button:'+b['target_id'],'label':b['text'],'action':b.get('role','action'),
              'x':b['hit_x'],'y':b['hit_y']} for b in snapshot.get('buttons',[])
             if b.get('panel') in ('preparation','result','expansion','research','story') and b.get('input_verified') and b.get('interactable')]
    story=panel_rows(snapshot,'story')
    if story:
        state={**state,'story_state':'choice' if any(b.get('panel')=='story' and b.get('role')=='choice' for b in snapshot.get('buttons',[]) if b.get('input_verified')) else
               'revealing' if any(r.get('display_state')=='revealing' for r in story.values()) else
               'ready' if any(r.get('display_state')=='ready' for r in story.values()) else 'transition'}
    return {**state,'actions':actions}


def project(snapshot):
    from .live import command_window, reading_panels, visible_employees, visible_entities, urgent_alerts
    console=snapshot.get('console',{})
    employees=visible_employees(snapshot)
    rows=(command_window(snapshot) or {}).get('employees',[])
    # Exact values only from visible rendered employee rows; duplicate names
    # cannot be joined safely and remain in the selected command window.
    for e in employees:
        matches=[r for r in rows if r.get('name')==e.get('name')]
        if len(matches)==1 and sum(x.get('name')==e.get('name') for x in employees)==1:
            e['displayed_vitals']={k:matches[0][k] for k in ('hp','sp') if matches[0].get(k) is not None}
            if e['displayed_vitals']:e['displayed_vitals']['basis']='visible_command_text'
    def entities(rows):
        result={}
        for row in rows:
            r=copy.deepcopy(row);key=r.pop('entity_id',None) or r['track_id']
            r['ref']='unit:'+key
            loc=r.get('facility_location')
            if loc:r['facility_location']={k:loc[k] for k in ('facility_id','relative') if k in loc}
            # Input tokens remain distinct from stable observation identities.
            result[key]=r
        return result
    fm=console.get('facility_map',{})
    hazards=copy.deepcopy(console.get('hazards',{}))
    for name in ('room_status','room_timers'):
        rows=hazards.get(name)
        if isinstance(rows,list) and all('room_id' in r for r in rows):hazards[name]={r['room_id']:{k:v for k,v in r.items() if k!='room_id'} for r in rows}
    window=command_window(snapshot)
    if window:
        represented={'summary','selected_enemy'}|{r['row_id'] for r in window['employees']}|{'result_'+r['result'] for r in window['work_results']}
        window={**window,'text_groups':[g for g in window['text_groups'] if g['group'] not in represented and not g['group'].startswith('work_')]}
    texts={}
    for t in snapshot.get('ui_texts',[]):
        if t.get('panel') in ('command','playback','ego','gift','creature_record','story','research','screen','preparation','result','expansion','selection','enemy'):continue
        key=(t.get('panel',''),t.get('row_id',''),t.get('role',''))
        texts.setdefault('/'.join(key),[]).append(t['text'])
    state = {'alerts':urgent_alerts(snapshot),'scene':snapshot['scene'],'screen':snapshot['screen'],
      'motion_status':console.get('motion',{}).get('status','unavailable'),'playback':[t['text'] for t in snapshot.get('ui_texts',[]) if t.get('panel')=='playback'],
      'employees':entities(employees),'entities':entities(visible_entities(snapshot)),
      'selection':{'employees_in_view':[{'id':e.get('entity_id',e['track_id']),'name':e.get('name')} for e in employees if e.get('selected')],
                   'info_panel':panel_rows(snapshot,'selection').get('panel')},
      'screen_context':screen_context(snapshot),
      'preparation':panel_rows(snapshot,'preparation'),'result':panel_rows(snapshot,'result'),'expansion':panel_rows(snapshot,'expansion'),
      'selected_enemy':selected_enemy(snapshot),'player_orders':snapshot.get('player_orders',{}),
      'known_map':{**{k:v for k,v in fm.get('known',{}).items() if k!='landmarks'},'landmarks':{r['id']:{k:v for k,v in r.items() if k!='id'} for r in fm.get('known',{}).get('landmarks',[])}},
      'facilities':{r['id']:{k:v for k,v in r.items() if k!='id'} for r in fm.get('visible',[])},
      'command_window':window,'reading':reading_panels(snapshot),'display_text':texts,
      'story':panel_rows(snapshot,'story'),'research':panel_rows(snapshot,'research'),
      'hazards':hazards,'dead_employees':console.get('dead_employees',[]),
      'buttons':{b['target_id']:{k:b[k] for k in ('text','panel','row_id','role','hit_x','hit_y') if k in b}
                 for b in snapshot.get('buttons',[]) if b.get('input_verified') and b.get('interactable')},
      'gauges':console.get('gauges',[])}
    from .appearance import attach
    return attach(state,console.get('appearance',[]))


def selected_enemy(snapshot):
    result={t['role']:t['text'] for t in snapshot.get('ui_texts',[]) if t.get('panel')=='command' and t.get('row_id')=='selected_enemy'}
    if result:
        result['attack_types']=[t['text'] for t in snapshot.get('ui_texts',[]) if t.get('panel')=='enemy']
        from .live import visible_entities
        matches=[e for e in visible_entities(snapshot) if e.get('name') and e.get('name')==result.get('name')]
        if matches:result['same_name_in_view']=[{'id':e['entity_id'],'target':('entity:'+e['track_id']) if e.get('click') else None,
            'position':e['position'],'display_bar':e.get('display_bar')} for e in matches]
    return result or None


def changes(old,new,path=()):
    """Leaf set/remove operations; arrays atomic, keyed entities are objects."""
    out=[]
    if isinstance(old,dict) and isinstance(new,dict):
        for k in sorted(old.keys()-new.keys()):out.append({'remove':list(path+(k,))})
        for k,v in new.items():
            if k not in old:out.append({'set':list(path+(k,)),'value':v})
            else:out.extend(changes(old[k],v,path+(k,)))
    elif old!=new:out.append({'set':list(path),'value':new})
    return out


def compact_audio(delivery):
    groups=[]
    previous=None
    for e in delivery.get('events',[]):
        if e.get('kind') in ('source_idle','source_destroyed'):continue
        key=(e.get('kind'),e.get('sound_id') or e.get('sound_token'),e.get('label'))
        if key!=previous:groups.append({'kind':key[0],'sound':key[1],'label':key[2], 'first_at':e.get('at_utc'),'last_at':e.get('at_utc'),'count':0})
        groups[-1]['count']+=1;groups[-1]['last_at']=e.get('at_utc');previous=key
    return {**{k:v for k,v in delivery.items() if k!='events'},'events':groups}


class Delivery:
    def __init__(self):self.lock=threading.RLock();self.state=None;self.identity=None;self.id=None;self.sequence=-1
    def offer(self,snapshot):
        with self.lock:
            identity=(snapshot['process_id'],snapshot['scene'],snapshot['screen']['width'],snapshot['screen']['height'],snapshot.get('console',{}).get('session'),snapshot.get('console',{}).get('signal_epoch',0))
            current=project(snapshot);reset=self.identity!=identity or snapshot['sequence']<self.sequence or self.state is None
            token=uuid.uuid4().hex
            value={'schema':'player_delta_v2','id':token,'base':None if reset else self.id,
                   'captured_at_utc':snapshot['captured_at_utc'],'sequence':snapshot['sequence'],
                   'mode':'full' if reset else 'delta','alerts':current.pop('alerts')}
            if reset:value['state']=current
            else:
                delta=changes(self.state,current)
                lost=self.state.get('entities',{}).keys()-current.get('entities',{}).keys()
                if lost:
                    value['entity_visibility_changes']=[{'id':k,'name':self.state['entities'][k].get('name'),
                        'event':'no_longer_observed','outcome':'unconfirmed'} for k in sorted(lost)]
                priority={'hazards','dead_employees','playback','command_window','selection','screen_context','selected_enemy','player_orders','story'}
                def important(x):
                    path=x.get('set') or x.get('remove') or ['']
                    return path[0] in priority or (path[0]=='employees' and len(path)>2 and path[2] in ('hp_bar','sp_bar','displayed_vitals','selected','appearance'))
                value['priority_changes']=[x for x in delta if important(x)]
                value['changes']=[x for x in delta if x not in value['priority_changes']]
            self.state=copy.deepcopy(current);self.identity=identity;self.id=token;self.sequence=snapshot['sequence']
            return value
