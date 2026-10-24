"""Observed presentation labels and portable player naming. No gameplay semantics."""
import copy
import json
import re
import threading
import math
from pathlib import Path
from .experience import write, encode, now, quoted

REF = re.compile(r'(form|motion|mark):[0-9a-f]{20}')
DEFAULT = {'form':'상태', 'motion':'동작', 'mark':'표식'}


def validate(rows):
    if not isinstance(rows,list) or len(rows)>128:raise ValueError('Invalid appearance rows')
    def item(x,kind):
        if not isinstance(x,dict) or not isinstance(x.get('ref'),str) or not REF.fullmatch(x['ref']) or not x['ref'].startswith(kind+':'):raise ValueError('Invalid visual ref')
        label=x.get('label')
        if label not in (DEFAULT[kind], 'YES','NO') and not (kind=='mark' and label=='검은 안개'):raise ValueError('Invalid visual label')
        return {'ref':x['ref'],'kind':kind,'label':label}
    result=[]
    for row in rows:
        subject=row.get('subject');room=row.get('room_id')
        if not isinstance(subject,str) or not subject.startswith('unit:') or len(subject)>128:raise ValueError('Invalid appearance subject')
        if room is not None and (not isinstance(room,str) or not re.fullmatch(r'-?\d{1,12}',room)):raise ValueError('Invalid appearance room')
        out={'subject':subject,'room_id':room,'form':item(row['form'],'form') if row.get('form') else None}
        point=row.get('position')
        if point is not None:
            if not isinstance(point,dict) or any(type(point.get(k)) not in (int,float) or not math.isfinite(point[k]) or abs(point[k])>1e6 for k in ('x','y')):raise ValueError('Invalid appearance position')
            out['position']={k:point[k] for k in ('x','y')}
        for name,kind in (('motions','motion'),('marks','mark')):
            values=row.get(name,[])
            if not isinstance(values,list) or len(values)>64:raise ValueError('Invalid visual list')
            out[name]=[item(x,kind) for x in values]
        result.append(out)
    return result


def attach(state,rows):
    """Join only to currently visible units/rooms. Empty lists clear old marks."""
    state['creature_appearances']={}
    for row in rows:
        key=row['subject'][5:]
        visual={k:copy.deepcopy(row[k]) for k in ('form','motions','marks')}
        target=state.get('employees',{}).get(key) or state.get('entities',{}).get(key)
        if target is not None:target['appearance']=visual
        room=state.get('hazards',{}).get('room_status',{}).get(row.get('room_id'))
        if room is not None and row.get('form') is not None:room['appearance']=visual
        if target is None and room is None and row.get('form') is not None and row.get('position'):
            state['creature_appearances'][key]={'ref':row['subject'],'position':row['position'],'appearance':visual,'input_target':False}
    return state


def visual_items(value):
    if isinstance(value,dict):
        if isinstance(value.get('ref'),str) and REF.fullmatch(value['ref']) and value.get('kind') in DEFAULT:
            yield value
        else:
            for child in value.values():yield from visual_items(child)
    elif isinstance(value,list):
        for child in value:yield from visual_items(child)


class VisualNames:
    def __init__(self,root):
        self.root=Path(root);self.path=self.root/'vault/Lobotomy-Experience/Playbook/Visual-Labels.json'
        self.lock=threading.RLock();self.stamp=None;self.data={'schema':1,'labels':{}}

    def load(self):
        stamp=(self.path.stat().st_mtime_ns,self.path.stat().st_size) if self.path.exists() else None
        if stamp!=self.stamp:
            self.data=json.loads(self.path.read_text(encoding='utf8')) if stamp else {'schema':1,'labels':{}}
            self.stamp=stamp
        return self.data

    def save(self):
        write(self.path,encode(self.data)+'\n');self.stamp=(self.path.stat().st_mtime_ns,self.path.stat().st_size)

    def decorate(self,value,offered=True):
        with self.lock:
            data=self.load();items=list(visual_items(value));unknown={x['ref']:x for x in items if x['ref'] not in data['labels']}
            if offered and unknown:
                # Cross-process lock is needed only for new observations/edits, never ordinary reads.
                from .playbook import Playbook
                with Playbook(self.root,None).lock():
                    self.stamp=None;data=self.load()
                    for ref,x in unknown.items():
                        if ref in data['labels']:continue
                        count=sum(v['kind']==x['kind'] for v in data['labels'].values())+1
                        data['labels'][ref]={'ref':ref,'kind':x['kind'],'default_name':x['label'] if x['label'] in ('YES','NO','검은 안개') else DEFAULT[x['kind']]+str(count),'first_observed_at':now(),'revisions':[]}
                    self.save()
            for x in items:
                row=data['labels'].get(x['ref'])
                if row:
                    x['label']=row['default_name'];latest=row['revisions'][-1] if row['revisions'] else None
                    if latest and latest['name']:
                        x['alias']=latest['name']
                        if latest['description']:x['note']=latest['description']
                        x['alias_source']='player'
        return value

    def name(self,ref,name,description=''):
        if not isinstance(ref,str) or not REF.fullmatch(ref):raise ValueError('Use an observed visual ref')
        if not isinstance(name,str) or len(name)>80 or not isinstance(description,str) or len(description)>1000:raise ValueError('Name <=80, description <=1000 characters')
        from .playbook import Playbook
        with self.lock,Playbook(self.root,None).lock():
            self.stamp=None;data=self.load();row=data['labels'].get(ref)
            if row is None:raise ValueError('Visual ref has not been offered to this player')
            row['revisions'].append({'name':name.strip(),'description':description.strip(),'at':now()})
            self.save()
            write(self.path.with_suffix('.md'),'# 관찰한 외형·동작·표식의 별칭\n\n별칭과 설명은 플레이어의 해석이며 게임이 확인한 효과가 아닙니다.\n\n'+quoted(encode(data))+'\n')
            return copy.deepcopy(row)

    def read(self,query='',limit=20,offset=0):
        if not isinstance(query,str) or len(query)>200 or type(limit)is not int or not 1<=limit<=50 or type(offset)is not int or offset<0:raise ValueError('Invalid page/query')
        with self.lock:
            rows=[copy.deepcopy(x) for x in self.load()['labels'].values() if query.casefold() in encode(x).casefold()]
            for row in rows:
                revisions=row.pop('revisions');row['alias']=revisions[-1] if revisions else None
            return {'labels':rows[offset:offset+limit],'total':len(rows),'next_offset':offset+limit if offset+limit<len(rows) else None}
