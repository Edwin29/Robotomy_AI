"""Read-only consumer of visible UI snapshots; independent of synthetic sessions.

The producer must publish latest.json atomically. This reader never attaches to a
process, sends input, opens a game save, or interprets hidden game state.
"""
from datetime import datetime, timezone
import json
import hashlib
import math
import os
from pathlib import Path, PureWindowsPath
import threading
import time
import uuid
import copy
import re
from collections import deque


def audio_event(event):
    """Whitelist audible evidence; resource names and hidden game state never pass."""
    identity = _integer(event['event_id'], 1, 2**63-1)
    kind = event['kind']
    if kind not in ('start','stop','pause','resume','source_idle','source_destroyed','ongoing_detected'):
        raise ValueError('invalid audio kind')
    at = _string(event['at_utc'],64,True)
    instant = datetime.fromisoformat(at.replace('Z','+00:00'))
    if instant.tzinfo is None or instant.utcoffset().total_seconds() != 0:
        raise ValueError('invalid audio timestamp')
    result = dict(event_id=identity,at_utc=at,kind=kind)
    for key in ('source_token','sound_token'):
        value=event[key]
        if not (key=='sound_token' and value=='') and not (isinstance(value,str) and re.fullmatch('[0-9a-f]{32}',value)):
            raise ValueError('invalid sound token')
        result[key]=value
    known={'first_trumpet':('퍼스트 트럼펫','warning_music'),
           'second_trumpet':('세컨드 트럼펫','warning_music'),
           'third_trumpet':('서드 트럼펫','warning_music'),
           'qliphoth_meltdown':('클리포트 폭주 알림음','warning_sound')}
    sound_id=event.get('sound_id')
    if isinstance(sound_id,str) and (sound_id in known or re.fullmatch('sound_[0-9a-f]{24}',sound_id)):
        label,category=known.get(sound_id,('구분된 소리 '+sound_id[6:14],'unclassified_sound'))
        result.update(sound_id=sound_id,label=label,category=category)
    return result


class AudioJournal:
    """Bounded incremental journal reader. No Unity calls, sleep, or full-file rescans."""
    def __init__(self,directory):
        self.directory=directory
        self.session=None
        self.offset=0
        self.events=deque(maxlen=4096)
        self.highest=0

    def read(self,session,after=0,limit=100):
        _integer(after,0,2**63-1); _integer(limit,1,200)
        if not isinstance(session,str) or not re.fullmatch('[0-9a-f]{32}',session):
            return dict(status='unavailable',events=[],next_event_id=after)
        if self.session!=session:
            self.session=session; self.offset=0; self.events.clear(); self.highest=0
        result=dict(session=session,events=[],next_event_id=after,
                    boundary='Historical playback evidence, not current sound or complete final-mix recognition.')
        try:
            with (self.directory/('audio-'+session+'.jsonl')).open('rb') as stream:
                size=os.fstat(stream.fileno()).st_size
                if size<self.offset:
                    self.offset=0; self.events.clear(); self.highest=0
                    return dict(result,status='journal_reset',next_event_id=0,reset_required=True)
                stream.seek(self.offset)
                # Drain unread cached events before ingesting another bounded chunk.
                budget=256*1024 if self.highest<=after else 0
                while budget>0:
                    line=stream.readline(4097)
                    if not line: break
                    if len(line)>4096: return dict(result,status='invalid_journal')
                    if not line.endswith(b'\n'): break  # Retry incomplete append next time.
                    value=audio_event(json.loads(line))
                    if value['event_id']<=self.highest:
                        return dict(result,status='invalid_sequence')
                    self.events.append(value); self.highest=value['event_id']
                    self.offset=stream.tell(); budget-=len(line)
                catching_up=self.offset<size
        except FileNotFoundError:
            return dict(result,status='journal_pending')
        except (OSError,ValueError,KeyError,TypeError):
            return dict(result,status='invalid_journal')
        selected=[e for e in self.events if e['event_id']>after][:limit]
        gaps=[]; cursor=after
        for event in selected:
            if event['event_id']>cursor+1: gaps.append(dict(first=cursor+1,last=event['event_id']-1))
            cursor=event['event_id']
        result.update(status='ok',events=selected,next_event_id=cursor,gaps=gaps,
                      catching_up=catching_up,has_more=cursor<self.highest or catching_up)
        return result


def player_audio(result):
    """Consumer response: engineering diagnostics stay in the journal reader."""
    status=result.get('status')
    value={key:result[key] for key in ('session','events','next_event_id','has_more') if key in result}
    if status=='session_changed':
        value['notice']='새 게임 세션입니다.'
    elif status not in ('ok','journal_pending','unavailable'):
        value['notice']='소리 기록을 가져오지 못했습니다.'
    elif result.get('gaps'):
        value['notice']='일부 지난 소리 기록이 누락되었습니다.'
    return value


def command_rows(snapshot):
    """Group only this offered snapshot's admitted display items, never cached employees."""
    rows={}
    for item in snapshot.get('ui_texts',[])+snapshot.get('buttons',[]):
        if item.get('panel')!='command' or not item.get('row_id') or item['row_id'] in ('summary','window','selected_enemy') or item['row_id'].startswith(('result_','work_')): continue
        row=rows.setdefault(item['row_id'],dict(row_id=item['row_id'],name=None,hp=None,sp=None,
            status=None,action=None,action_detail=None,success_rate=None,work_time=None,work_level=None,selectable=None,click=None))
        role=item.get('role')
        if role in ('name','hp','sp','status','action','action_detail','success_rate','work_time','work_level'):
            row[role]=item['text']
        elif role=='click' and item.get('interactable'):
            if item.get('subject_ref'):row['ref']=item['subject_ref']
            row['click']={'x':item['x']+item['width']/2,'y':item['y']+item['height']/2,
                          'basis':'visible_row_click_handler_not_orderability', 'target_id':item.get('target_id')}
            row['click']['x']=item.get('hit_x',row['click']['x']);row['click']['y']=item.get('hit_y',row['click']['y'])
    # A displayed hover action is evidence only; unknown is never treated as false/true.
    return list(rows.values())


def _entity_location(track,snapshot):
    try: from .facility import entity_location
    except ModuleNotFoundError: from robotomy.facility import entity_location
    return entity_location(track,snapshot)

def visible_entities(snapshot):
    motion=snapshot.get('console',{}).get('motion',{})
    if motion.get('status')!='available':return []
    result=[]
    for t in motion.get('tracks',[]):
        entity=t.get('entity')
        if entity is None or entity['kind']=='employee':continue
        result.append({'entity_id':t.get('entity_id',t['track_id']),'track_id':t['track_id'],'facility_location':_entity_location(t,snapshot),**entity,**{k:t[k] for k in ('position','bounds','state','screen_velocity','object_velocity','camera_velocity')}})
    return result


def command_window(snapshot):
    """All admitted command text, grouped without consulting hidden UI/model values."""
    texts=[x for x in snapshot.get('ui_texts',[]) if x.get('panel')=='command']
    buttons=[x for x in snapshot.get('buttons',[]) if x.get('panel')=='command']
    if not texts and not buttons:return None
    summary={};results={};groups={};works=[]
    for t in texts:
        rid=t.get('row_id') or 'window';role=t.get('role') or 'display_text'
        groups.setdefault(rid,[]).append({'field':role,'text':t['text']})
        if rid=='summary':summary[role]=t['text']
        elif rid.startswith('result_'):results.setdefault(rid[7:],{})[role]=t['text']
    for b in buttons:
        if b.get('role')!='work_type':continue
        click=None
        if b.get('interactable') and b.get('input_verified'):
            click={'x':b.get('hit_x',b['x']+b['width']/2),'y':b.get('hit_y',b['y']+b['height']/2),'target_id':b.get('target_id')}
        works.append({'name':b['text'],'click':click})
    return {'summary':summary,'work_results':[{'result':k,**v} for k,v in results.items()],
            'work_types':works,'employees':command_rows(snapshot),
            'text_groups':[{'group':k,'fields':v} for k,v in groups.items()]}


EMPLOYEE_STATUS_LABELS={'idle':'대기 중','moving':'이동 중','working':'작업 중','suppressing':'제압 중','panic':'패닉','uncontrollable':'통제 불가','dead':'사망','unknown':'미확인'}

def dead_employees(rows):
    if not isinstance(rows,list) or len(rows)>512: raise ValueError('invalid death roster')
    result=[]
    for row in rows:
        if row.get('status')!='dead': raise ValueError('non-death in death roster')
        result.append({'employee_id':_string(row['employee_id'],64,True),'name':_string(row['name'],256),
                       'status':'dead','status_label':'사망'})
    return result

def visible_employees(snapshot):
    motion=snapshot.get('console',{}).get('motion',{})
    if motion.get('status')!='available': return []
    result=[]
    for track in motion.get('tracks',[]):
        employee=track.get('employee')
        if employee is None: continue
        velocity=track.get('object_velocity')
        movement='unknown' if velocity is None else ('moving' if math.hypot(velocity['x'],velocity['y'])>1 else 'stationary')
        status=employee.get('status','unknown')
        result.append({'entity_id':track.get('entity_id',track['track_id']),'track_id':track['track_id'],**employee,'status':status,'status_label':EMPLOYEE_STATUS_LABELS[status],'position':track['position'],
                       'movement':movement,'object_velocity':velocity,'screen_velocity':track.get('screen_velocity'),
                       'camera_velocity':track.get('camera_velocity'),'facility_location':_entity_location(track,snapshot)})
    return result


def reading_panels(snapshot):
    rows, paragraphs, controls, selected = {}, {}, [], {}
    gifts, gift_window = {}, {}
    for item in snapshot.get('ui_texts', []):
        panel, token, role = item.get('panel'), item.get('row_id'), item.get('role')
        if not token: continue
        if panel == 'gift':
            row=gift_window if token=='window' else gifts.setdefault(token,{'slot_id':token})
            row[role]=({'true':True,'false':False}.get(item['text']) if role in ('locked','lock_available','open_available') else item['text'])
            continue
        if panel == 'ego' and token == 'selected':
            if role: selected[role]=item['text']
            continue
        if panel == 'ego':
            row = rows.setdefault(token, {'row_id': token, 'owners': [], 'actions': []})
            if role == 'owner': row['owners'].append(item['text'])
            elif role: row[role] = item['text']
        elif panel == 'creature_record':
            paragraphs.setdefault(token, []).append(item['text'])
    for item in snapshot.get('buttons', []):
        if item.get('panel')=='gift' and item.get('input_verified'):
            token=item.get('row_id');row=gift_window if token=='window' else gifts.get(token)
            if row is not None:
                row[item['role']+'_click']={'ref':'gift:'+token+':'+item['role'],'x':item['hit_x'],'y':item['hit_y'],'target_id':item['target_id']}
            continue
        if item.get('panel') != 'ego' or not item.get('input_verified'): continue
        action = {'role': item.get('role'), 'label': item['text'], 'target_id':item['target_id'],
                  'x':item['hit_x'], 'y':item['hit_y']}
        token = item.get('row_id')
        if token in rows: rows[token]['actions'].append(action)
        else: controls.append(action)
    return {'gifts':{'employee':gift_window.get('employee'),'open_click':gift_window.get('open_click'),'slots':gifts} if gift_window else None, 'equipment_rows':list(rows.values()), 'equipment_controls':controls, 'selected_equipment':selected or None,
            'creature_record': [{'paragraph_id':token,'text':'\n'.join(lines)} for token,lines in paragraphs.items()]}


def observation_sections(snapshot):
    """Only current, disclosed values. Lists are replaced atomically, never merged by index."""
    ignored = {'captured_at_utc', 'sequence', 'unity_frame', 'isolation'}
    sections = {}
    if 'hazards' in snapshot.get('console', {}):
        sections['/console/hazards'] = snapshot['console']['hazards']
    sections.update({('/'+k):v for k,v in snapshot.items() if k not in ignored and k != 'console'})
    sections.update({'/console/'+k:v for k,v in snapshot.get('console', {}).items() if k not in ignored})
    return sections


def urgent_alerts(snapshot):
    """Promote currently visible countdowns, without inferring unseen events."""
    hazards = snapshot.get('console', {}).get('hazards') or {}
    timers = hazards.get('room_timers') or []
    if not timers:
        return []
    rooms = sorted(({'room': t.get('room_label'), 'seconds': t['seconds']}
                    for t in timers), key=lambda t: t['seconds'])
    return [{'kind': 'qliphoth_meltdown_active', 'severity': 'warning',
             'headline': '경고: 클리포트 폭주 타이머 표시 중',
             'min_remaining_seconds': rooms[0]['seconds'], 'visible_rooms': rooms,
             'captured_at_utc': snapshot.get('captured_at_utc')}]


def observation_diff(previous, current, observation_id, selection, identity):
    sections = observation_sections(current)
    reason = ('first_observation' if previous is None else
              'context_changed' if previous['identity'] != identity else
              'selection_changed' if previous['selection'] != selection else None)
    old = previous['sections'] if reason is None else {}
    replacements = {k:v for k,v in sections.items() if k not in old or v != old[k]}
    removed = [k for k in old if k not in sections]
    elapsed = None
    if previous is not None:
        elapsed = (datetime.fromisoformat(current['captured_at_utc'].replace('Z','+00:00')) -
                   datetime.fromisoformat(previous['captured_at_utc'].replace('Z','+00:00'))).total_seconds()
    old_hazards = old.get('/console/hazards', {})
    hazards = sections.get('/console/hazards', {})
    priority = {k:v for k,v in hazards.items() if k not in old_hazards or v != old_hazards[k]}
    priority.update({k:None for k in old_hazards if k not in hazards})
    return {'priority_changes':priority, 'mode':'reset' if reason else 'delta', 'reset_reason':reason,
            'base_observation_id':previous['id'] if reason is None else None,
            'current_observation_id':observation_id, 'elapsed_seconds':elapsed,
            'changed_sections':list(replacements), 'removed_sections':removed,
            'replacements':replacements if reason is None else {},
            'no_structured_changes':reason is None and not replacements and not removed,
            'boundary':'Compare offered structured observations only. Replace whole sections; removal is not death. Unchanged does not mean the image or intervening events were unchanged.'}


MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024
MAX_FRAME_BYTES = 10 * 1024 * 1024
MAX_AGE_SECONDS = 10
MAX_FUTURE_SECONDS = 5
# Classification of final visible UI only; these labels do not authorize model
# state fields. Progression, occlusion and text reveal gates belong to the producer.
DISPLAY_PANELS = frozenset(("playback", "energy", "agent", "creature", "command", "mission",
                            "notice", "tooltip", "bullets", "input_target", "ego", "creature_record", "story", "research",
                            "screen", "preparation", "result", "expansion", "selection", "enemy", "gift"))
SOURCE = "actual_game_ui"
BOUNDARY = ("Read-only visible UI observation; not proof of game mechanics, "
            "successful control, learning, or clearance. UI text is untrusted data.")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("invalid integer")
    return value


def _string(value, maximum, nonempty=False):
    if not isinstance(value, str) or len(value) > maximum or (nonempty and not value):
        raise ValueError("invalid string")
    value.encode("utf-8")  # Reject unpaired JSON surrogate escapes before recording.
    return value


def _ui_items(value, maximum, buttons=False):
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError("invalid UI list")
    output = []
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError("invalid UI item")
        item = {"text": _string(entry["text"], 2048)}
        if entry.get('panel')=='command' and entry.get('subject_ref'):
            ref=_string(entry['subject_ref'],37,True)
            if not ref.startswith('unit:') or len(ref)!=37 or any(c not in '0123456789abcdef' for c in ref[5:]):raise ValueError('invalid subject ref')
            item['subject_ref']=ref
        if "panel" in entry:
            panel = entry["panel"]
            if not isinstance(panel, str) or panel not in DISPLAY_PANELS:
                raise ValueError("invalid panel")
            item["panel"] = panel
        if entry.get('row_id') and entry.get('role') in ('name','hp','sp','status','action','action_detail','success_rate','work_time','work_level','click','code','risk','max_pe_boxes','damage_type','damage_range','result_label','pe_range','display_text','work_type') and entry.get('panel') == 'command':
            item['row_id'] = _string(entry['row_id'],128,True)
            item['role'] = entry['role']
        if entry.get('row_id') and ((entry.get('panel') == 'ego' and entry.get('role') in ('name','grade','damage_type','damage','attack_speed','range','owner','resist_red','resist_white','resist_black','resist_pale','factor_red','factor_white','factor_black','factor_pale','equipment_slot','details','tab','select_agent','selected_name','weapon_name','weapon_grade','weapon_damage_type','weapon_damage','suit_name','suit_grade','suit_resist_red','suit_resist_white','suit_resist_black','suit_resist_pale','suit_factor_red','suit_factor_white','suit_factor_black','suit_factor_pale')) or (entry.get('panel') == 'creature_record' and entry.get('role') == 'line')):
            item['row_id'] = _string(entry['row_id'],128,True)
            item['role'] = entry['role']
        if entry.get('row_id') and entry.get('panel') in ('story','research','screen','preparation','result','expansion','selection','enemy') and entry.get('role') in ('speaker','dialogue','letter','narration','extra','choice','department','title','help','name','effect','description','drag_start','drop_target','confirmation','action','click','display_state','base','modal','display_text','day','lob','ordeal','energy','rank','reward','promoted','dead','alive','displayed_name','retry','next_day','confirm','cancel','attack_unknown','attack_red','attack_white','attack_black','attack_pale'):
            item['row_id']=_string(entry['row_id'],128,True)
            item['role']=entry['role']
        if entry.get('panel')=='gift' and entry.get('row_id') and entry.get('role') in ('employee','name','region','description','locked','lock_available','open_available','open','lock'):
            item.update(row_id=_string(entry['row_id'],128,True),role=entry['role'])
        if entry.get('panel')=='command' and entry.get('row_id')=='selected_enemy' and entry.get('role') in ('resist_red','resist_white','resist_black','resist_pale','factor_red','factor_white','factor_black','factor_pale'):
            item.update(row_id='selected_enemy',role=entry['role'])
        for key in ("x", "y", "width", "height"):
            number = entry[key]
            if type(number) not in (int, float) or not math.isfinite(number) or abs(number) > 100000:
                raise ValueError("invalid UI coordinate")
            if key in ("width", "height") and number < 0:
                raise ValueError("invalid UI dimensions")
            item[key] = number
        if buttons:
            if type(entry["interactable"]) is not bool:
                raise ValueError("invalid button state")
            item["interactable"] = entry["interactable"]
            if entry.get('input_verified') is True:
                item['target_id'] = _string(entry['target_id'], 128, True)
                item['input_verified'] = True
                for key in ('hit_x','hit_y'):
                    number = entry[key]
                    if type(number) not in (int,float) or not math.isfinite(number):
                        raise ValueError('invalid target point')
                    item[key] = number
                if not (item['x'] <= item['hit_x'] <= item['x']+item['width'] and
                        item['y'] <= item['hit_y'] <= item['y']+item['height']):
                    raise ValueError('target point outside button')
        output.append(item)
    return output


def _motion(value, screen):
    if (not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1
            or value.get("basis") != "display_projection_v1"
            or value.get("coordinates") != "top_left_pixels"
            or value.get("units") != "pixels_per_real_second"
            or value.get("status") not in ("available", "withheld")):
        raise ValueError("invalid motion contract")
    tracks = value["tracks"]
    if not isinstance(tracks, list) or len(tracks) > 128 or (value["status"] == "withheld" and tracks):
        raise ValueError("invalid motion tracks")
    def number(v, low, high):
        if type(v) not in (float, int) or not math.isfinite(v) or not low <= v <= high:
            raise ValueError("invalid motion number")
        return v
    def vector(v, position=False):
        return {axis: number(v[axis], 0 if position else -10000000,
                            screen[dim] if position else 10000000)
                for axis, dim in (("x", "width"), ("y", "height"))}
    result, seen = [], set()
    for track in tracks:
        token = track["track_id"]
        if (not isinstance(token, str) or len(token) != 32 or any(c not in "0123456789abcdef" for c in token)
                or token in seen or track["state"] not in ("acquiring", "tracking", "discontinuity")):
            raise ValueError("invalid motion identity/state")
        seen.add(token)
        stable=track.get("entity_id")
        if stable is not None and (not isinstance(stable,str) or len(stable)!=32 or any(c not in "0123456789abcdef" for c in stable)):raise ValueError("invalid stable identity")
        bbox = track["bounds"]
        rect = {k: number(bbox[k], 0, screen["width" if k in ("x", "width") else "height"])
                for k in ("x", "y", "width", "height")}
        if rect["x"] + rect["width"] > screen["width"] + .02 or rect["y"] + rect["height"] > screen["height"] + .02:
            raise ValueError("motion bounds outside screen")
        interval = number(track["interval_ms"], 0, 60000)
        item = {"track_id": token, "state": track["state"], "position": vector(track["position"], True),
                "bounds": rect, "interval_ms": interval}
        if stable is not None:item["entity_id"]=stable
        for key in ("screen_velocity", "object_velocity", "camera_velocity"):
            if track["state"] == "tracking":
                if not 10 <= interval <= 300:
                    raise ValueError("motion interval invalid")
                item[key] = vector(track[key])
            elif track[key] is not None:
                raise ValueError("unobserved motion must be unknown")
            else:
                item[key] = None
        if track["state"] == "tracking":
            for axis in ("x", "y"):
                if abs(item["screen_velocity"][axis] - item["object_velocity"][axis] - item["camera_velocity"][axis]) > .031:
                    raise ValueError("motion decomposition mismatch")
        loc=track.get('facility_location')
        if isinstance(loc,dict):
            item['facility_location']={'facility_id':_string(loc['facility_id'],128),
                'map_position':vector(loc['map_position']),
                'relative':{k:number(loc['relative'][k],-100,100) for k in ('u','v')},
                'extent':{k:number(loc['extent'][k],.001,100000) for k in ('width','height')},
                'basis':'visible_anchor_in_display_bounds'}
        entity=track.get('entity')
        if entity is not None:
            kind=entity.get('kind')
            if kind not in ('employee','worker','creature','projectile'):raise ValueError('invalid entity kind')
            item['entity']={'kind':kind,'name':None if entity.get('name') is None else _string(entity['name'],256)}
            if entity.get('click') is not None:item['entity']['click']=vector(entity['click'],True)
            bar=entity.get('display_bar')
            if bar is not None:
                item['entity']['display_bar']={'ratio':number(bar['ratio'],0,1),
                    'color':{k:number(bar['color'][k],0,1) for k in ('r','g','b')}}
        employee=track.get('employee')
        if employee is not None:
            condition=employee.get('condition','unknown')
            if condition not in ('normal','panic','dead','uncontrollable','unknown'): raise ValueError('invalid visible employee condition')
            click=employee.get('click')
            item['employee']={'name':None if employee.get('name') is None else _string(employee['name'],256),
                              'condition':condition,'click':None if click is None else vector(click,True)}
            for bar in ('hp_bar','sp_bar'):
                b=employee.get(bar)
                if b is None:item['employee'][bar]=None;continue
                total=_integer(b['total_pixels'],1,32768)
                filled=_integer(b['filled_pixels'],0,total)
                ratio=number(b['ratio'],0,1)
                if abs(ratio-filled/total)>.00001:raise ValueError('invalid displayed bar ratio')
                item['employee'][bar]={'ratio':ratio,'filled_pixels':filled,'total_pixels':total}
            if type(employee.get('selected')) is bool:item['employee']['selected']=employee['selected']
            if 'status' in employee:
                status=employee['status']
                if status not in EMPLOYEE_STATUS_LABELS: raise ValueError('invalid employee status')
                item['employee']['status']=status
                item['employee'].pop('condition',None)
        result.append(item)
    return {"version": 1, "basis": "display_projection_v1", "coordinates": "top_left_pixels",
            "units": "pixels_per_real_second", "status": value["status"], "tracks": result}


def _hazards(value, screen):
    result = {}
    ordeal = value.get('ordeal')
    if ordeal is not None:
        color = _string(ordeal['color'], 32, True)
        stage = _string(ordeal['stage'], 64, True)
        ordeal = dict(color=color, stage=stage, label=color+' '+stage)
    result['ordeal'] = ordeal
    level = value.get('meltdown_level')
    result['meltdown_level'] = None if level is None else _string(level, 32, True)
    gauge = value.get('meltdown_gauge')
    if gauge is not None:
        maximum = _integer(gauge['max'], 1, 1024)
        filled = _integer(gauge['filled'], 0, maximum)
        gauge = dict(filled=filled, max=maximum, ratio=filled/maximum, label=f'{filled}/{maximum}')
    result['meltdown_gauge'] = gauge
    rooms = value.get('target_rooms')
    result['target_rooms'] = None if rooms is None else _integer(rooms, 0, 1024)
    timers = value.get('room_timers', [])
    if not isinstance(timers, list) or len(timers)>512: raise ValueError('invalid room timers')
    result['room_timers'] = []
    for t in timers:
        coords = {}
        for k,edge in (('x','width'),('y','height')):
            n = t[k]
            if type(n) not in (int,float) or not math.isfinite(n) or not 0<=n<=(screen or {}).get(edge,32768):
                raise ValueError('invalid timer position')
            coords[k] = n
        name = t.get('room_label')
        result['room_timers'].append(dict(room_label=None if name is None else _string(name,256),
            seconds=_integer(t['seconds'],0,86400), **coords))
    statuses=value.get('room_status',[])
    if not isinstance(statuses,list) or len(statuses)>512: raise ValueError('invalid room status')
    result['room_status']=[]
    def position(item):
        coords={}
        for k,edge in (('x','width'),('y','height')):
            n=item[k]
            if type(n) not in (int,float) or not math.isfinite(n) or not 0<=n<=(screen or {}).get(edge,32768): raise ValueError('invalid display position')
            coords[k]=n
        return coords
    for item in statuses:
        counter=item.get('qliphoth_counter');boxes=item.get('work_boxes')
        if counter is not None:
            state=counter['display']
            if state not in ('number','unknown','not_applicable'): raise ValueError('invalid counter display')
            counter={'display':state,'value':_integer(counter['value'],0,100000) if state=='number' else None}
        if boxes is not None:
            pe=_integer(boxes['pe_boxes'],0,1024);ne=_integer(boxes['ne_boxes'],0,1024)
            boxes={'pe_boxes':pe,'ne_boxes':ne,'generated_total':pe+ne}
        name=item.get('room_label');stored=item.get('stored_pe_boxes');penalty=item.get('work_penalty_text')
        click=item.get('click')
        if click is not None:
            if click.get('input_verified') is not True: raise ValueError('unverified room click')
            click=dict(**position(click),target_id=_string(click['target_id'],64,True),input_verified=True)
        info_click=item.get('info_click')
        if info_click is not None:
            if info_click.get('input_verified') is not True: raise ValueError('unverified room info click')
            info_click=dict(**position(info_click),target_id=_string(info_click['target_id'],64,True),input_verified=True)
        result['room_status'].append(dict(room_id=_string(item['room_id'],64,True),room_label=None if name is None else _string(name,256),
            qliphoth_counter=counter,work_boxes=boxes,stored_pe_boxes=None if stored is None else _integer(stored,0,2147483647),
            work_penalty_text=None if penalty is None else _string(penalty,128),
            work_narration=None if item.get('work_narration') is None else _string(item['work_narration'],4096),
            **position(item),**({'click':click} if 'click' in item else {}),**({'info_click':info_click} if 'info_click' in item else {})))
    management=value.get('creature_management');result['creature_management']=None
    if management is not None:
        costs=management.get('costs',[])
        if not isinstance(costs,list) or len(costs)>128: raise ValueError('invalid costs')
        clean=[]
        for item in costs:
            if item['kind'] not in ('unlock','weapon_cost_or_stock','suit_cost_or_stock'): raise ValueError('invalid cost kind')
            label=item.get('label')
            clean.append(dict(kind=item['kind'],label=None if label is None else _string(label,256),display_text=_string(item['display_text'],256),**position(item)))
        stored=management.get('stored_pe_text')
        for item, raw in zip(clean,costs):
            if item['kind']!='unlock': continue
            prerequisite=raw.get('prerequisite','not_indicated')
            if prerequisite not in ('required','not_indicated'): raise ValueError('invalid prerequisite display')
            item['prerequisite']=prerequisite
            # Derived only from visible balance/cost, never from model purchase checks.
            balance=str(stored) if stored is not None else ''
            cost=item['display_text']
            item['funds']='unknown'
            if balance.isascii() and balance.isdecimal() and cost.isascii() and cost.isdecimal():
                item['funds']='sufficient' if int(balance)>=int(cost) else 'insufficient'
        details=management.get('details',[])
        if not isinstance(details,list) or len(details)>128: raise ValueError('invalid management details')
        fields={'identity':('name','code','risk','max_pe_boxes'),'work_damage':('type','range'),
                'work_result_pe_range':('label','range'),'ego_weapon':('name','grade','damage_type','damage_range','attack_speed','attack_range'),
                'ego_suit':('name','grade'),'ego_suit_resistance':('type_and_factor','resistance'),
                'management_tip':('label','text'),'work_preference':('work','I','II','III','IV','V')}
        decoded=[]
        for detail in details:
            kind=detail.get('kind')
            if kind not in fields: raise ValueError('invalid management detail kind')
            decoded.append({'kind':kind,**{k:_string(detail[k],4096) for k in fields[kind] if k in detail}})
            if kind=='management_tip' and 'x' in detail and 'y' in detail:decoded[-1].update(position(detail))
            if kind=='management_tip' and type(detail.get('partial')) is bool:decoded[-1]['partial']=detail['partial']
        result['creature_management']={'stored_pe_text':None if stored is None else _string(stored,128),'costs':clean,'details':decoded}
    return result


def _console(value, screen=None):
    """Whitelist device data. Internal object/clip names never cross this boundary."""
    if not isinstance(value, dict) or value.get("version") != 1 or type(value.get("version")) is not int:
        raise ValueError("invalid console version")
    if value.get("policy") != "conservative_display_v1" or value.get("audio_basis") != "playback_state_approximation":
        raise ValueError("invalid console policy")
    def token(item, empty=False):
        if empty and item == "":
            return item
        if not isinstance(item, str) or len(item) != 32 or any(c not in "0123456789abcdef" for c in item):
            raise ValueError("invalid anonymous token")
        return item
    events = value["audio_events"]
    gauges = value["gauges"]
    if not isinstance(events, list) or len(events) > 128 or not isinstance(gauges, list) or len(gauges) > 512:
        raise ValueError("oversized console list")
    audio, bars = [], []
    previous = 0
    for event in events:
        identity = _integer(event["event_id"], 1, 2**63-1)
        if identity <= previous or event["kind"] not in ("start", "stop", "pause", "resume", "source_idle", "source_destroyed", "ongoing_detected"):
            raise ValueError("invalid audio sequence or kind")
        previous = identity
        at = _string(event["at_utc"], 64, True)
        instant = datetime.fromisoformat(at.replace("Z", "+00:00"))
        if instant.tzinfo is None or instant.utcoffset().total_seconds() != 0:
            raise ValueError("invalid audio timestamp")
        audio.append(audio_event(event))
    for gauge in gauges:
        if gauge["role"] not in ("energy", "agent_hp_bar", "agent_mental_bar"):
            raise ValueError("invalid gauge role")
        rectangle = _ui_items([{**gauge, "text": ""}], 1)[0]
        total = _integer(gauge["total_pixels"], 1, 32768)
        bars.append({"role": gauge["role"], **{key: rectangle[key] for key in ("x", "y", "width", "height")},
                     "filled_pixels": _integer(gauge["filled_pixels"], 0, total), "total_pixels": total})
    result = {"version": 1, "session": token(value["session"]),
            "unity_frame": _integer(value["unity_frame"], 0, 2**31-1),
            "policy": "conservative_display_v1", "valid_for_ms": _integer(value["valid_for_ms"], 1, 750),
            "audio_basis": "playback_state_approximation",
            "audio_dropped": _integer(value["audio_dropped"], 0, 2**31-1), "audio_events": audio, "gauges": bars}
    if "motion" in value:
        result["motion"] = _motion(value["motion"], screen)
    if "hazards" in value:
        result["hazards"] = _hazards(value['hazards'], screen)
    if 'facility_map' in value:
        try:
            from .facility import decode
        except ModuleNotFoundError:
            from robotomy.facility import decode
        result['facility_map']=decode(value['facility_map'],screen)
    if 'signal_epoch' in value:result['signal_epoch']=_integer(value['signal_epoch'],0,2**31-1)
    if 'signals' in value:
        signals=value['signals']
        if not isinstance(signals,list) or len(signals)>128:raise ValueError('invalid signals')
        result['signals']=[]
        previous_signal=0
        for event in signals:
            number=_integer(event['id'],1,2**63-1)
            if number<=previous_signal or event['kind'] not in ('meltdown_cycle','escape_confirmed','room_narration'):raise ValueError('invalid signal order/kind')
            at=_string(event['at'],64,True)
            if datetime.fromisoformat(at.replace('Z','+00:00')).tzinfo is None:raise ValueError('invalid signal time')
            result['signals'].append({'id':number,'kind':event['kind'],'at':at,'text':_string(event['text'],4096)})
            if event['kind']=='room_narration':
                result['signals'][-1].update(room_id=_string(event['room_id'],64,True),
                    room_label=None if event.get('room_label') is None else _string(event['room_label'],256))
            previous_signal=number
    if 'dead_employees' in value:
        result['dead_employees']=dead_employees(value['dead_employees'])
    if 'appearance' in value:
        from .appearance import validate
        result['appearance']=validate(value['appearance'])
    if 'combat' in value:
        from .combat import validate_combat
        result['combat']=validate_combat(value['combat'])
    return result


def validate_snapshot(obj):
    """Validate and whitelist one capture without applying live freshness policy.

    Historical readers retain original timestamps; callers decide whether the
    validated capture can be used as a current observation.
    """
    if not isinstance(obj, dict):
        raise ValueError("invalid object")
    if (type(obj["schema_version"]) is not int or obj["schema_version"] != 1
            or obj["environment"] != "lobotomy_live" or obj["read_only"] is not True):
        raise ValueError("invalid identity")
    isolation = obj["isolation"]
    if (isolation["company_name"] != "Robotomy_AI"
            or isolation["product_name"] != "Lobotomy_Observer"):
        raise ValueError("invalid isolation identity")
    persistent_path = _string(isolation["persistent_data_path"], 4096, True)
    normalized = persistent_path.replace("\\", "/").rstrip("/")
    if (not PureWindowsPath(persistent_path).is_absolute()
            or not normalized.endswith("/Robotomy_AI/Lobotomy_Observer")
            or ".." in normalized.split("/")):
        raise ValueError("invalid isolation path")
    captured = _string(obj["captured_at_utc"], 64, True)
    timestamp = datetime.fromisoformat(captured.replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp.utcoffset().total_seconds() != 0:
        raise ValueError("timestamp must be UTC")
    screen = obj["screen"]
    snapshot = {
        "schema_version": 1, "environment": "lobotomy_live", "read_only": True,
        "captured_at_utc": captured,
        "process_id": _integer(obj["process_id"], 1, 2**32 - 1),
        "sequence": _integer(obj["sequence"], 0, 2**63 - 1),
        "scene": _string(obj["scene"], 256),
        "screen": {key: _integer(screen[key], 1, 32768) for key in ("width", "height")},
        "isolation": {"company_name": "Robotomy_AI", "product_name": "Lobotomy_Observer",
                      "persistent_data_path": persistent_path},
        "ui_texts": _ui_items(obj["ui_texts"], 512),
        "buttons": _ui_items(obj.get("buttons", []), 256, buttons=True),
    }
    if "console" in obj:
        snapshot["console"] = _console(obj["console"], snapshot["screen"])
    return snapshot, timestamp


class LiveReader:
    def __init__(self, root, *, clock=None):
        self.root = Path(root).resolve()
        self.directory = self.root / ".robotomy" / "live"
        self.snapshot_path = self.directory / "latest.json"
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()
        self._offered_baseline = None
        self._audio = AudioJournal(self.directory)
        self._audio_cursor = (None,0)

    def read_audio(self,after_event_id=0,limit=100,session=None):
        with self._lock:
            summary,snapshot=self._read()
            if snapshot is None: return summary
            current=snapshot.get('console',{}).get('session')
            if session is not None and session!=current:
                return player_audio(dict(status='session_changed',session=current,events=[],next_event_id=0))
            result=self._audio.read(current,after_event_id,limit)
            result['producer_dropped']=snapshot.get('console',{}).get('audio_dropped')
            return player_audio(result)

    def _read(self):
        base = {"source": SOURCE, "read_only": True, "boundary": BOUNDARY}
        try:
            for attempt in range(4):
                try:
                    with self.snapshot_path.open("rb") as handle:
                        raw = handle.read(MAX_SNAPSHOT_BYTES + 1)
                    break
                except (PermissionError, FileNotFoundError):
                    # Mono/Windows replacement can briefly deny sharing or
                    # make the old path disappear. Retry reads only; the final
                    # absence still rejects observation and no action is sent.
                    if attempt == 3:
                        raise
                    time.sleep(.01)
        except FileNotFoundError:
            return {**base, "status": "never_connected"}, None
        except OSError:
            return {**base, "status": "invalid", "reason": "snapshot_unreadable"}, None
        if len(raw) > MAX_SNAPSHOT_BYTES:
            return {**base, "status": "invalid", "reason": "snapshot_too_large"}, None
        try:
            obj = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_object)
            snapshot, timestamp = validate_snapshot(obj)
            captured = snapshot["captured_at_utc"]
            age = (self.clock() - timestamp).total_seconds()
            if "console" in snapshot:
                motion = snapshot["console"].get("motion")
                if motion is not None and age > .25:
                    motion.update(status="expired", tracks=[])
                    snapshot["console"]["appearance"]=[]
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
            return {**base, "status": "invalid", "reason": "snapshot_contract_violation"}, None
        if age < -MAX_FUTURE_SECONDS:
            return {**base, "status": "invalid", "reason": "snapshot_from_future"}, None
        summary = {**base, "captured_at_utc": captured, "age_seconds": round(age, 3),
                   "process_id": snapshot["process_id"], "sequence": snapshot["sequence"]}
        max_age = snapshot.get("console", {}).get("valid_for_ms", MAX_AGE_SECONDS * 1000) / 1000
        if age > max_age:
            return {**summary, "status": "stale"}, None
        return {**summary, "status": "live", "scene": snapshot["scene"],
                "ui_text_count": len(snapshot["ui_texts"]),
                "button_count": len(snapshot["buttons"])}, snapshot

    def status(self):
        """Validate freshness and producer identity without creating observation records."""
        summary, _ = self._read()
        return summary

    def frame(self):
        """Retry only read-side publication races, never an input/action."""
        for attempt in range(5):
            status, data = self._frame_once()
            if data is not None or status.get("reason") not in ("frame_unreadable", "frame_missing", "frame_generation_mismatch"):
                return status, data
            if attempt < 4:
                time.sleep(.02)
        return status, None

    def _frame_once(self):
        """Return validated fixed-path PNG bytes or a status, without writing any records."""
        summary, snapshot = self._read()
        if snapshot is None:
            return summary, None
        try:
            with (self.directory / "frame.png").open("rb") as handle:
                before = os.fstat(handle.fileno())
                data = handle.read(MAX_FRAME_BYTES + 1)
                after = os.fstat(handle.fileno())
        except FileNotFoundError:
            return {**summary, "status": "invalid", "reason": "frame_missing"}, None
        except OSError:
            return {**summary, "status": "invalid", "reason": "frame_unreadable"}, None
        if len(data) > MAX_FRAME_BYTES:
            return {**summary, "status": "invalid", "reason": "frame_too_large"}, None
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            return {**summary, "status": "invalid", "reason": "frame_changed_during_read"}, None
        if (len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n"
                or data[8:16] != b"\x00\x00\x00\x0dIHDR"
                or not 1 <= int.from_bytes(data[16:20], "big") <= 32768
                or not 1 <= int.from_bytes(data[20:24], "big") <= 32768):
            return {**summary, "status": "invalid", "reason": "frame_invalid_png_header"}, None
        age = self.clock().timestamp() - after.st_mtime
        frame_meta = {}
        if "console" in snapshot:
            try:
                raw_meta = (self.directory / "frame-meta.json").read_bytes()
                if len(raw_meta) > 4096:
                    raise ValueError("oversized frame metadata")
                meta = json.loads(raw_meta, object_pairs_hook=_unique_object)
                if (meta["session"] != snapshot["console"]["session"] or meta["process_id"] != snapshot["process_id"]
                        or meta["scene"] != snapshot["scene"] or hashlib.sha256(data).hexdigest() != meta["sha256"]
                        or int.from_bytes(data[16:20], "big") != snapshot["screen"]["width"]
                        or int.from_bytes(data[20:24], "big") != snapshot["screen"]["height"]):
                    raise ValueError("frame generation mismatch")
                frame_meta = {"frame_unity_frame": _integer(meta["unity_frame"], 0, 2**31-1),
                              "frame_captured_at_utc": _string(meta["captured_at_utc"], 64, True)}
                checked_at = datetime.fromisoformat(meta["captured_at_utc"].replace("Z","+00:00"))
                if checked_at.tzinfo is None:
                    raise ValueError("frame timestamp needs timezone")
                # The producer rechecks unchanged story pixels without rewriting
                # PNG bytes. Only hash/session-verified capture metadata can renew them.
                age = self.clock().timestamp() - checked_at.timestamp()
            except (OSError, ValueError, KeyError, TypeError):
                return {**summary, "status": "invalid", "reason": "frame_generation_mismatch"}, None
        if age < -MAX_FUTURE_SECONDS:
            return {**summary, "status": "invalid", "reason": "frame_from_future"}, None
        if age > MAX_AGE_SECONDS:
            return {**summary, "status": "stale", "reason": "frame_stale",
                    "frame_age_seconds": round(age, 3)}, None
        return {**summary, "frame_age_seconds": round(age, 3), **frame_meta}, data

    def frame_after(self, after_utc=None, wait_ms=1200):
        """Wait for a post-action frame, not for dialogue completion. Never sends input."""
        _integer(wait_ms, 0, 2000)
        threshold = None
        if after_utc is not None:
            parsed = datetime.fromisoformat(after_utc.replace('Z', '+00:00'))
            if parsed.tzinfo is None: raise ValueError('after_utc needs a timezone')
            threshold = parsed.timestamp()
            # Request pixels only; no gameplay input, pause, or story advancement.
            try:
                (self.directory / 'frame-request.txt').write_text(after_utc, encoding='utf-8')
            except OSError:
                pass  # Preserve the ordinary missing/unavailable frame status.
        started = time.monotonic(); deadline = started + wait_ms/1000
        while True:
            status, data = self.frame()
            captured = status.get('frame_captured_at_utc')
            newer = threshold is None or (captured is not None and
                datetime.fromisoformat(captured.replace('Z', '+00:00')).timestamp() > threshold)
            if data is not None and newer:
                return {**status, 'waited_ms':round((time.monotonic()-started)*1000),
                        'frame_boundary':'Fresh frame only; dialogue may still be revealing.'}, data
            if status.get('status') != 'live' or time.monotonic() >= deadline:
                return {**status, 'status':status.get('status') if status.get('status') != 'live' else 'no_new_frame',
                        'waited_ms':round((time.monotonic()-started)*1000)}, None
            time.sleep(min(.03, max(0, deadline-time.monotonic())))

    def offer_audio(self,snapshot):
        with self._lock:
            session=snapshot.get('console',{}).get('session')
            if session is None:return {'events':[]}
            cursor=self._audio_cursor[1] if self._audio_cursor[0]==session else 0
            delivery=self._audio.read(session,cursor,100)
            delivery['producer_dropped']=snapshot['console'].get('audio_dropped',0)
            if delivery['status']=='ok':self._audio_cursor=(session,delivery['next_event_id'])
            elif delivery['status']=='journal_reset':self._audio_cursor=(session,0)
            return player_audio(delivery)

    def brief(self, after_sequence=None, wait_ms=350, reset_baseline=False, record_offer=True):
        from .experience import record
        from .perception import compact_audio
        with self._lock:
            status,snapshot=self._read()
            if snapshot is None or status.get('status')!='live':return status
            deadline=time.monotonic()+min(1000,max(0,wait_ms))/1000
            while after_sequence is not None and snapshot['sequence']<=after_sequence and time.monotonic()<deadline:
                time.sleep(.025);status,snapshot=self._read()
                if snapshot is None or status.get('status')!='live':return status
            if reset_baseline:self._delivery=__import__(__package__+'.perception',fromlist=['Delivery']).Delivery()
            response=self.deliver(snapshot,include_state=not record_offer)
            response['no_new_observation']=after_sequence is not None and snapshot['sequence']<=after_sequence
            response['audio']=compact_audio(self.offer_audio(snapshot))
            if record_offer:response['experience_recording']=record(self.root,'observation_offered',response.copy())
            return response

    def deliver(self,snapshot,include_state=False):
        from .perception import Delivery
        from .quick_input import movement_orders as orders
        with self._lock:
            if not hasattr(self,'_delivery'):self._delivery=Delivery()
            snapshot={**snapshot,'player_orders':orders(self.root,snapshot)}
            if not include_state:
                from .appearance import VisualNames
                import copy
                if not hasattr(self,'_visual_names'):self._visual_names=VisualNames(self.root)
                snapshot=copy.deepcopy(snapshot)
                self._visual_names.decorate(snapshot.get('console',{}).get('appearance',[]))
            response=self._delivery.offer(snapshot)
            from .combat import CombatDelivery
            if not hasattr(self,'_combat_delivery'):self._combat_delivery=CombatDelivery()
            response['combat']=self._combat_delivery.offer(snapshot)
            if include_state:
                import copy
                response['_adapter_state']=copy.deepcopy(self._delivery.state)
                response['_adapter_identity']=self._delivery.identity
            if hasattr(self,'_event_source'):
                events=self._event_source(snapshot);response['event_delivery']=events
                response['alerts'][:0]=[{'kind':e['kind'],'event_id':e['id'],'observed_at':e['observed_at'],**{k:e[k] for k in ('text','employee','result') if k in e}} for e in events['events'] if e['kind'] in ('meltdown_cycle','employee_death','escape_confirmed','pause_result')]
            return response

    def observe(self, max_items=100, motion_only=False, compact=False, after_sequence=None, wait_ms=350):
        """Record exactly the bounded response; Markdown is deferred to day review."""
        from .experience import record
        _integer(max_items, 1, 100)
        if type(motion_only) is not bool:
            raise ValueError('motion_only must be boolean')
        if type(compact) is not bool:
            raise ValueError('compact must be boolean')
        _integer(wait_ms, 0, 1000)
        if after_sequence is not None: _integer(after_sequence, 0, 2**63-1)
        started = time.monotonic(); deadline = started + wait_ms/1000
        with self._lock:
            summary, snapshot = self._read()
            reference = self._offered_baseline
            def pending(value):
                if value is None or after_sequence is None: return False
                identity = (value['process_id'], value['scene'], value['screen'], value.get('console',{}).get('session'))
                # A new scene/process must be returned even when its counter restarted.
                if reference is not None and identity != reference['identity']: return False
                return value['sequence'] <= after_sequence
            while pending(snapshot) and time.monotonic() < deadline:
                time.sleep(min(.025, max(0, deadline-time.monotonic())))
                summary, snapshot = self._read()
            if pending(snapshot):
                return {**summary, 'status':'no_new_observation', 'waited_ms':round((time.monotonic()-started)*1000),
                        'boundary':'No newer sample yet; not evidence that the game is unchanged.'}
            if snapshot is None:
                self._offered_baseline = None
                return summary
            event_id = "live_" + uuid.uuid4().hex
            now = self.clock().astimezone(timezone.utc).isoformat()
            bounded = {**snapshot, "ui_texts": snapshot["ui_texts"][:max_items],
                       "buttons": snapshot["buttons"][:max_items]}
            truncated = len(snapshot["ui_texts"]) > max_items or len(snapshot["buttons"]) > max_items
            if motion_only:
                motion = snapshot.get('console', {}).get('motion', {'status': 'unsupported', 'tracks': []})
                truncated = len(motion['tracks']) > max_items
                bounded = {key:snapshot[key] for key in ('captured_at_utc','process_id','scene','screen')}
                bounded.update(unity_frame=snapshot.get('console', {}).get('unity_frame'),
                               motion={**motion, 'tracks': motion['tracks'][:max_items]})
            if not motion_only:
                bounded['command_rows'] = command_rows(bounded)
                bounded['command_window'] = command_window(bounded)
                bounded.update(reading_panels(bounded))
                bounded['visible_employees']=visible_employees(bounded)
                bounded['visible_entities']=visible_entities(bounded)
                fm=bounded.get('console',{}).get('facility_map')
                if fm is not None:
                    import hashlib
                    revision=hashlib.sha256(json.dumps(fm['known'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:16]
                    bounded['facility_map']={'revision':revision,'visible':fm['visible']}
                    bounded['facility_map_known']={'revision':revision,**fm['known']}
                else:bounded['facility_map']=None
                bounded['dead_employees']=bounded.get('console',{}).get('dead_employees',[])
                states=[x['text'] for x in bounded.get('ui_texts',[]) if x.get('panel')=='playback' and x['text'] in ('paused','1x','1.5x','2x')]
                bounded['playback']={'state':states[0] if len(states)==1 else None,'basis':'visible_selected_control'}
                if 'console' in bounded:
                    bounded['console']={k:v for k,v in bounded['console'].items()
                                        if k not in ('audio_dropped','audio_basis','audio_events','facility_map')}
            response = {**summary, "observation_id": event_id, "recorded_at_utc": now,
                        "snapshot": bounded, "truncated": truncated}
            selection = {'max_items':max_items,'motion_only':motion_only}
            identity = (snapshot['process_id'], snapshot['scene'], snapshot['screen'],
                        snapshot.get('console',{}).get('session'))
            previous = self._offered_baseline
            if previous is not None and snapshot['sequence'] < previous['sequence']:
                previous = None
            diff = observation_diff(previous,bounded,event_id,selection,identity)
            reasons = []
            if snapshot['scene'] != 'Main': reasons.append('story_or_other_scene')
            if diff['mode'] == 'reset': reasons.append('new_context_or_baseline')
            if truncated: reasons.append('truncated_information')
            if not bounded.get('ui_texts') and not bounded.get('console'): reasons.append('limited_structured_coverage')
            response['visual_check'] = {'recommended':bool(reasons), 'reasons':reasons,
                'boundary':'Advisory only. No change cannot rule out animation, danger, story or missed events. Player must inspect significant/ambiguous changes and periodic frames.'}
            response['waited_ms'] = round((time.monotonic()-started)*1000)
            response = {'alerts':urgent_alerts(snapshot), 'change_summary':diff, **response, 'compact':compact,
                        'payload_mode':'full' if not compact or diff['mode']=='reset' else 'delta',
                        'comparison_scope':'selected structured fields only; truncated response is not full coverage'}
            if response['payload_mode']=='delta':
                response.pop('snapshot')
            event = {"id": event_id, "kind": "live_observation", "recorded_at_utc": now,
                     "source": SOURCE, "read_only": True, "boundary": BOUNDARY,
                     "snapshot": bounded, "selection": {"max_items":max_items,"motion_only":motion_only},
                     "truncated":truncated}
            event.update(alerts=response['alerts'],change_summary=diff,compact=compact,payload_mode=response['payload_mode'])
            if response['payload_mode']=='delta':
                event.pop('snapshot')
            self.directory.mkdir(parents=True, exist_ok=True)
            payload = (json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
            descriptor = os.open(self.directory / "observations.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                if os.write(descriptor, payload) != len(payload):
                    raise OSError("incomplete observation append")
            finally:
                os.close(descriptor)
            if not motion_only and snapshot.get('console'):
                response['audio_delivery']=self.offer_audio(snapshot)
            response['experience_recording'] = record(self.root, 'observation_offered', response)
            self._offered_baseline = copy.deepcopy({'id':event_id,'sections':observation_sections(bounded),
                'identity':identity,'selection':selection,'captured_at_utc':bounded['captured_at_utc'],
                'sequence':snapshot['sequence']})
            return response
