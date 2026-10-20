"""Remembered facility geometry and fresh, game-local fixed-ID input."""
import json
import math
from pathlib import Path

KINDS={'corridor','elevator','main_room','junction','passage','containment'}
APPEARANCES={'static_noise':'흑백 노이즈','flames_embers':'불꽃·불티','rainbow_waves':'무지개색 물결','green_mist_particles':'녹색 안개·빛 입자','unclassified':'미분류 표면 효과'}
LABELS={'corridor':'복도','elevator':'엘리베이터','main_room':'부서 중앙실','junction':'연결 통로','passage':'통로','containment':'격리실'}

def _number(v,limit=100000):
    if type(v) not in (int,float) or not math.isfinite(v) or abs(v)>limit:raise ValueError('invalid facility coordinate')
    return v

def atlas(value):
    if not isinstance(value,dict) or value.get('version')!=1:raise ValueError('invalid facility atlas')
    rows=value.get('landmarks',[])
    if not isinstance(rows,list) or len(rows)>2048:raise ValueError('invalid facility landmarks')
    out=[];seen=set()
    for row in rows:
        key=row.get('id');kind=row.get('kind')
        if not isinstance(key,str) or not 1<=len(key)<=128 or key in seen or kind not in KINDS:raise ValueError('invalid facility landmark')
        seen.add(key);x,y=_number(row['x']),_number(row['y'])
        department=row.get('department');department=department if isinstance(department,str) and len(department)<=80 else None
        out.append({'department':department,'id':key,'kind':kind,'label':f'{department + chr(32) if department else str()}{LABELS[kind]} ({x:.2f}, {y:.2f})','map_position':{'x':x,'y':y}})
    by_id={r['id']:r for r in out}; connections=[]; edge_seen=set()
    edges=value.get('connections',[])
    if not isinstance(edges,list) or len(edges)>8192:raise ValueError('invalid facility connections')
    for e in edges:
        a,b=e.get('a'),e.get('b')
        if a not in by_id or b not in by_id or a==b:raise ValueError('invalid facility connection')
        pair=tuple(sorted((a,b)))
        if pair in edge_seen:continue
        edge_seen.add(pair);connections.append({'a':a,'b':b,'kind':'observed_direct_connection'})
    for r in out:
        r['connections']=[]
        for e in connections:
            target=e['b'] if e['a']==r['id'] else e['a'] if e['b']==r['id'] else None
            if target is None:continue
            q=by_id[target];dx=q['map_position']['x']-r['map_position']['x'];dy=q['map_position']['y']-r['map_position']['y']
            horizontal='right' if dx>1 else 'left' if dx<-1 else None
            vertical='up' if dy>1 else 'down' if dy<-1 else None
            direction='_'.join(v for v in (vertical,horizontal) if v) or 'same_position'
            r['connections'].append({'id':target,'label':q['label'],'direction':direction,'delta':{'x':round(dx,2),'y':round(dy,2)}})
    lobbies={r['department']:r for r in out if r['kind']=='main_room' and r.get('department')}
    for r in out:
        lobby=lobbies.get(r.get('department'))
        if lobby and lobby['id']!=r['id']:
            dx=round(r['map_position']['x']-lobby['map_position']['x'],2);dy=round(r['map_position']['y']-lobby['map_position']['y'],2)
            r['relative_to_lobby']={'id':lobby['id'],'horizontal':'right' if dx>1 else 'left' if dx<-1 else 'aligned','vertical':'above' if dy>1 else 'below' if dy<-1 else 'aligned'}
    # Map bands describe position, not official floors, and never imply a connection.
    bands=[]
    for r in sorted(out,key=lambda r:-r['map_position']['y']):
        y=r['map_position']['y']
        if not bands or abs(bands[-1]['map_y']-y)>1:bands.append({'map_y':y,'spaces':[]})
        bands[-1]['spaces'].append(r['id'])
    for band in bands:band['spaces'].sort(key=lambda k:by_id[k]['map_position']['x'])
    return {'version':1,'coordinate_space':'facility_fixed_xy','axes':{'x':'right','y':'up'},
            'basis':'previously_observed_geometry','landmarks':out,'connections':connections,
            'layout_top_to_bottom':bands,'layout_order':'Each band lists spaces left to right; proximity is not connectivity.'}

def decode(value,screen):
    known=atlas(value['known']);ids={r['id'] for r in known['landmarks']};visible=[]
    rows=value['visible']
    if not isinstance(rows,list) or len(rows)>2048:raise ValueError('invalid visible facility list')
    def point(p):
        x,y=_number(p['x']),_number(p['y'])
        if not 0<=x<=screen['width'] or not 0<=y<=screen['height']:raise ValueError('facility point outside screen')
        return {'x':x,'y':y}
    for r in rows:
        if r['id'] not in ids or r['kind'] not in KINDS:raise ValueError('unknown facility landmark')
        click=r.get('click')
        if click is not None:
            click={**point(click),'button':click.get('button','left')}
            if click['button'] not in ('left','right'):raise ValueError('invalid facility button')
        row={'id':r['id'],'kind':r['kind'],'position':point(r['position']),'click':click}
        state=r.get('status')
        if isinstance(state,dict):
            warning=state.get('warning_light')
            if warning not in (None,'off','red'):raise ValueError('invalid facility warning')
            effects=[]
            for effect in state.get('surface_effects',[]):
                key=effect.get('visual_id')
                if not isinstance(key,str) or len(key)!=16 or not key.startswith('surface-') or any(c not in '0123456789abcdef' for c in key[8:]):raise ValueError('invalid surface identity')
                appearance=effect.get('appearance','unclassified')
                if appearance not in APPEARANCES:appearance='unclassified'
                effects.append({'visual_id':key,'appearance':appearance,'label':APPEARANCES[appearance]})
            row['status']={'warning_light':warning,'surface_effects':effects}
        visible.append(row)
    return {'known':known,'visible':visible}

def read_map(root):
    path=Path(root)/'.robotomy/live/facility-map.json'
    if not path.exists():return {'status':'not_observed','landmarks':[]}
    if path.stat().st_size>1024*1024:raise ValueError('facility atlas too large')
    return {'status':'remembered',**atlas(json.loads(path.read_text(encoding='utf-8-sig')))}

def resolve(snapshot,identity):
    rows=snapshot.get('console',{}).get('facility_map',{}).get('visible',[])
    candidates=[r for r in rows if r['id']==identity and r.get('click')]
    if len(candidates)!=1:raise ValueError('Facility is not currently visible, unlocked and clickable. No input sent.')
    return candidates[0]['click']

def click_facility(root,identity,rationale=''):
    from .virtual_input import VirtualExecutor
    from robotomy.input_sequence import input_lock
    executor=VirtualExecutor(root)
    with input_lock(root):
        # Resolves at call time: old map/screen coordinates supplied by the player are never accepted.
        capture=executor.capture(record_observation=False,include_frame=False)
        point=resolve(capture['snapshot'],identity)
        d=executor.control.prepare(capture['view']['id'],'right_click' if point['button']=='right' else 'click',
                                   rationale=rationale,x=point['x'],y=point['y'])
        result={'facility_id':identity,'resolved_click':point,'receipt':executor.execute(d['id'])}
        from .experience import record
        result['experience_recording']=record(root,'facility_action',result.copy())
        return result


def entity_location(track,snapshot):
    loc=track.get('facility_location')
    if not isinstance(loc,dict):return None
    fm=snapshot.get('console',{}).get('facility_map',{})
    key=loc.get('facility_id')
    if key not in {r['id'] for r in fm.get('visible',[])}:return None
    landmark=next((r for r in fm.get('known',{}).get('landmarks',[]) if r['id']==key),None)
    if landmark is None:return None
    return {**loc,'facility_label':landmark.get('label'),'department':landmark.get('department'),'kind':landmark['kind']}
