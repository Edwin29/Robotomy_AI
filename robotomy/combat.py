"""Public transient display events; sums are displayed numbers, not net health loss."""
import math
from datetime import datetime


KINDS={'damage_display','barrier_display','motion_changed','item_effect','ammo_display','projectile_display'}

def validate_combat(value):
    if not isinstance(value,dict) or type(value.get('latest_id')) is not int:raise ValueError('invalid combat journal')
    rows=value.get('events',[])
    if not isinstance(rows,list) or len(rows)>512:raise ValueError('invalid combat capacity')
    result=[];previous=0
    for e in rows:
        if type(e.get('id')) is not int or not previous<e['id']<=value['latest_id'] or e.get('kind') not in KINDS:raise ValueError('invalid combat event')
        previous=e['id'];out={'id':e['id'],'kind':e['kind']}
        for k in ('at','scene','subject','type','display','defense','text','state','motion','previous'):
            v=e.get(k)
            if v is not None and (not isinstance(v,str) or len(v)>512):raise ValueError('invalid display string')
            if k in e:out[k]=v
        if datetime.fromisoformat(out['at'].replace('Z','+00:00')).tzinfo is None:raise ValueError('missing combat timezone')
        if 'epoch' in e:
            if type(e['epoch'])is not int:raise ValueError('invalid event epoch')
            out['epoch']=e['epoch']
        for k in ('game_time','real_time','frame'):
            v=e[k]
            if type(v) not in (int,float) or not math.isfinite(v) or v<0:raise ValueError('invalid event clock')
            out[k]=v
        for key in ('position','object_velocity'):
            p=e.get(key)
            if p is not None:
                if any(type(p.get(k)) not in (int,float) or not math.isfinite(p[k]) for k in ('x','y')):raise ValueError('invalid event point')
                out[key]={k:p[k] for k in ('x','y')}
        result.append(out)
    return {'latest_id':value['latest_id'],'events':result}


class CombatDelivery:
    def __init__(self):self.identity=None;self.cursor=0;self.recent=[]
    def offer(self,snapshot):
        c=snapshot.get('console',{});identity=(c.get('session'),c.get('signal_epoch'),snapshot.get('scene'))
        if identity!=self.identity:self.identity=identity;self.cursor=0;self.recent=[]
        journal=c.get('combat',{});rows=journal.get('events',[])
        gap=bool(rows and self.cursor and rows[0]['id']>self.cursor+1)
        new=[e for e in rows if e['id']>self.cursor]
        self.cursor=max(self.cursor,journal.get('latest_id',0))
        self.recent=(self.recent+new)[-2048:]
        groups=[]
        for e in new:
            if e['kind']!='damage_display':continue
            # Unknown targets must not be merged into one fictitious victim.
            key=(e.get('subject') or ('unknown',e['id']),e.get('type'))
            prior=next((g for g in reversed(groups) if g['_key']==key and 0<=e['real_time']-g['last_time']<=.6),None)
            if prior is None:
                prior={'_key':key,'subject':e.get('subject'),'type':e.get('type'),'count':0,'numeric_count':0,
                       'sum_displayed':0,'max_displayed':None,'first_time':e['real_time'],'last_time':e['real_time'],'event_ids':[]}
                groups.append(prior)
            prior['count']+=1;prior['last_time']=e['real_time'];prior['event_ids'].append(e['id'])
            try:v=int(e.get('display'))
            except (ValueError,TypeError):continue
            prior['numeric_count']+=1;prior['sum_displayed']+=v;prior['max_displayed']=max(v,prior['max_displayed']) if prior['max_displayed'] is not None else v
        for g in groups:
            g.pop('_key')
            if not g['numeric_count']:g['sum_displayed']=None
        projectiles={e['subject']:e for e in new if e['kind']=='projectile_display'}
        motions={}
        for e in new:
            if e['kind']!='motion_changed':continue
            row=motions.setdefault(e['subject'],{'subject':e['subject'],'changes':0,'first_time':e['real_time']})
            row.update(motion=e.get('motion'),position=e.get('position'),last_time=e['real_time'],event_id=e['id']);row['changes']+=1
        return {'scope':{'session':identity[0],'epoch':identity[1],'scene':identity[2]},'cursor':self.cursor,'gap':gap,'damage':groups,
                'effects':[e for e in new if e['kind'] not in ('damage_display','projectile_display','motion_changed')],
                'motions':list(motions.values()),'projectiles':list(projectiles.values()),
                'event_range':[new[0]['id'],new[-1]['id']] if new else None}

    def read(self,after=0,limit=100):
        if type(after)is not int or after<0 or type(limit)is not int or not 1<=limit<=256:raise ValueError('invalid event range')
        rows=[e for e in self.recent if e['id']>after]
        selected=rows[:limit]
        # A relation is a time/space observation, never an attacker or attack-count claim.
        relations=[]
        for hit in selected:
            if hit['kind']!='damage_display':continue
            candidates=[e['id'] for e in self.recent if e['kind'] in ('motion_changed','projectile_display') and 0<=hit['real_time']-e['real_time']<=1.2
                        and e.get('position') and hit.get('position') and math.dist(list(e['position'].values()),list(hit['position'].values()))<=180]
            if candidates:relations.append({'damage_event':hit['id'],'nearby_motion_events':candidates[-8:],'basis':'temporal_spatial_only'})
        return {'events':selected,'relations':relations,'next':selected[-1]['id'] if selected else after,
                'more':len(rows)>len(selected),'gap':bool(self.recent and after and after<self.recent[0]['id']-1)}


def read_journal(root,session,after=0,limit=100):
    """Explicit paged raw retrieval; producer journal contains only admitted displays."""
    from pathlib import Path
    import json,re
    if not isinstance(session,str) or not re.fullmatch('[0-9a-f]{32}',session):raise ValueError('Invalid combat session')
    if type(after)is not int or after<0 or type(limit)is not int or not 1<=limit<=256:raise ValueError('Invalid event range')
    path=Path(root)/'.robotomy/live'/('combat-'+session+'.jsonl');rows=[]
    if not path.exists():return {'session':session,'events':[],'next':after,'status':'unavailable'}
    with path.open(encoding='utf8') as stream:
        for line in stream:
            if not line.endswith('\n'):break
            e=json.loads(line)
            if e['id']<=after:continue
            rows.extend(validate_combat({'latest_id':e['id'],'events':[e]})['events'])
            if len(rows)>limit:break
    page=rows[:limit]
    return {'session':session,'events':page,'next':page[-1]['id'] if page else after,'more':len(rows)>limit,'status':'available'}
