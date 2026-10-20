"""Player experience ledger. No game process, save, model API or hidden-state access.

Hot-path records use a bounded background queue. Only explicit attempt boundaries
and retrospective tools flush/project Markdown. Returned events mean offered to
the caller, not proof of delivery, attention, understanding or internal reasoning.
"""
import atexit
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import queue
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

PLAYER_GUIDE_PATHS = {
    'AGENTS.md': 'config/player/AGENTS.md',
    'Player-Persona.md': 'vault/Lobotomy-Experience/Config/Player-Persona.md',
    'Recording-Rules.md': 'vault/Lobotomy-Experience/Config/Recording-Rules.md',
    'Day-Review-Template.md': 'vault/Lobotomy-Experience/Config/Day-Review-Template.md',
}


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_bytes(content if isinstance(content, bytes) else content.encode('utf-8'))
    temp.replace(path)


def quoted(value):
    # Never render game/player text as active Markdown/HTML.
    return '\n'.join('    ' + line for line in value.splitlines())


def bounded_text(value, maximum=16000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError('Nonempty bounded text required')
    return value


class Experience:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.private = self.root / '.robotomy/experience'
        self.db_path = self.private / 'ledger.sqlite3'
        self.vault = self.root / 'vault/Lobotomy-Experience'
        self.pending = queue.Queue(maxsize=128)
        self.lock = threading.RLock()
        self.byte_lock = threading.Lock()
        self.bytes_pending = 0
        self.failures = []
        self.worker = None

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def setup(self):
        self.private.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS attempts (
                    id TEXT PRIMARY KEY, run INTEGER, day INTEGER, attempt INTEGER,
                    status TEXT, data TEXT, UNIQUE(run,day,attempt));
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE,
                    attempt_id TEXT, kind TEXT, at TEXT, data TEXT);
                CREATE INDEX IF NOT EXISTS by_attempt ON events(attempt_id,seq);
                CREATE TABLE IF NOT EXISTS memories (id TEXT PRIMARY KEY, data TEXT);
                CREATE TABLE IF NOT EXISTS reviews (attempt_id TEXT PRIMARY KEY, data TEXT);
            ''')
        (self.vault / 'Playthroughs').mkdir(parents=True, exist_ok=True)
        if not (self.vault / 'Manager-Memory.md').exists():
            write(self.vault / 'Manager-Memory.md', '# 관리자 누적 기억\n\n아직 기록된 플레이 경험이 없습니다.\n')
        return self.status()

    def active(self):
        if not self.db_path.exists():
            return None
        with self.connect() as db:
            row = db.execute("SELECT data FROM attempts WHERE status='playing'").fetchone()
        return json.loads(row[0]) if row else None

    def status(self):
        if not self.db_path.exists():
            return {'configured': False, 'active': None}
        with self.connect() as db:
            attempts = [json.loads(r[0]) for r in db.execute('SELECT data FROM attempts ORDER BY rowid')]
        return {'configured': True, 'active': next((a for a in attempts if a['status']=='playing'), None),
                'attempts': attempts, 'pending': self.pending.unfinished_tasks,
                'recording_errors': self.errors(), 'vault': str(self.vault),
                'boundary': 'Run increments only on declared return_to_day_one. Model labels are self-reported.'}

    def _insert(self, db, attempt_id, kind, data, event_id=None, at=None):
        identity = event_id or 'exp_' + uuid.uuid4().hex
        db.execute('INSERT INTO events(id,attempt_id,kind,at,data) VALUES(?,?,?,?,?)',
                   (identity, attempt_id, kind, at or now(), encode(data)))
        return identity

    def begin(self, day, player, reason='next_day', phase='management', versions=None):
        if type(day) is not int or not 1 <= day <= 99:
            raise ValueError('Day must be 1..99')
        bounded_text(player, 200)
        if reason not in {'next_day','retry','memory_repository','return_to_day_one','operator_restore'}:
            raise ValueError('Unknown attempt transition')
        if phase not in {'story','preparation','management','results','tutorial'}:
            raise ValueError('Unknown phase')
        self.setup(); self.flush()
        with self.lock, self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute("SELECT 1 FROM attempts WHERE status='playing'").fetchone():
                raise ValueError('An attempt is active; resume it or finish it first')
            previous = db.execute('SELECT data FROM attempts ORDER BY rowid DESC LIMIT 1').fetchone()
            previous = json.loads(previous[0]) if previous else None
            run = previous['run'] if previous else 1
            if reason == 'return_to_day_one':
                if not previous or day != 1:
                    raise ValueError('Return to day one requires a previous run and day=1')
                run += 1
            elif (previous and previous['phase'] != 'tutorial' and day == 1
                  and previous.get('game_day', previous['day']) > 1
                  and reason not in {'memory_repository', 'operator_restore'}):
                raise ValueError('Declare return_to_day_one explicitly for a new run')
            if reason == 'retry' and (not previous or day != previous['day']):
                raise ValueError('Retry must keep the previous day')
            number = db.execute('SELECT COALESCE(MAX(attempt),0)+1 FROM attempts WHERE run=? AND day=?', (run,day)).fetchone()[0]
            memories = [json.loads(r[0]) for r in db.execute('SELECT data FROM memories ORDER BY rowid')]
            memory_version = hashlib.sha256(encode(memories).encode()).hexdigest()
            config_versions={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (self.vault/'Config').glob('*.md')}
            config_versions.update({name:hashlib.sha256((self.root/path).read_bytes()).hexdigest()
                                    for name,path in PLAYER_GUIDE_PATHS.items() if (self.root/path).exists()})
            isolation=self.root/'.robotomy/live/isolation.json'
            device_versions={}
            if isolation.exists():
                saved=json.loads(isolation.read_text(encoding='utf-8'))
                device_versions={k:saved[k] for k in ('observer_sha256','runtime_exe_sha256') if k in saved}
            attempt = {'id':f'Run-{run:03d}/Day-{day:02d}-Attempt-{number:02d}',
                       'run':run,'day':day,'attempt':number,'status':'playing','phase':phase,
                       'game_day':None if phase == 'tutorial' else day,
                       'tutorial_segment':day if phase == 'tutorial' else None,
                       'player':player,'started_at':now(),'reason':reason,'transition_basis':'player_declared',
                       'previous_attempt_id':previous['id'] if previous else None,
                       'memory_version':memory_version,'starting_memory':memories,'versions':versions or {},
                       'config_versions':config_versions,'device_versions':device_versions}
            db.execute('INSERT INTO attempts VALUES(?,?,?,?,?,?)',
                       (attempt['id'],run,day,number,'playing',encode(attempt)))
            self._insert(db, attempt['id'], 'attempt_started', {k:v for k,v in attempt.items() if k!='starting_memory'})
        self.project()
        return attempt

    def _failure(self, event_id, message):
        error = {'event_id':event_id,'at':now(),'error':message}
        self.failures.append(error)
        try:
            with (self.private/'recording-errors.jsonl').open('a',encoding='utf-8') as f:
                f.write(encode(error)+'\n')
        except OSError:
            pass

    def errors(self):
        path=self.private/'recording-errors.jsonl'
        if not path.exists(): return list(self.failures)
        try:
            return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        except (OSError,ValueError):
            return [*self.failures,{'error':'Recording error ledger could not be read completely'}]

    def record(self, kind, payload, image=None):
        with self.lock:
            attempt = self.active()
            if not attempt:
                return {'status':'inactive'}
            event_id = 'exp_' + uuid.uuid4().hex
            raw = encode(payload)  # freeze before returning to caller
            size = len(raw.encode('utf-8')) + (len(image) if image else 0)
            with self.byte_lock:
                if self.pending.full() or self.bytes_pending + size > 32*1024*1024:
                    self._failure(event_id,'Background recording queue full; event not saved')
                    return {'status':'not_recorded','event_id':event_id,'reason':'queue_full'}
                self.bytes_pending += size
            if self.worker is None:
                self.worker = threading.Thread(target=self._work, daemon=True, name='robotomy-experience')
                self.worker.start()
            self.pending.put_nowait((attempt, event_id, kind, now(), raw, image, size))
            return {'status':'queued','event_id':event_id,'durable':False}

    def _work(self):
        while True:
            item = self.pending.get()
            if item is None:
                self.pending.task_done(); return
            attempt, event_id, kind, at, raw, image, size = item
            try:
                payload = json.loads(raw)
                if image is not None:
                    digest = hashlib.sha256(image).hexdigest()
                    relative = f'Playthroughs/Run-{attempt["run"]:03d}/Media/{digest}.png'
                    path = self.vault / relative
                    if not path.exists():
                        write(path, image)
                    payload = {'response':payload,'media':{'path':relative,'sha256':digest,'bytes':len(image)}}
                with self.connect() as db:
                    self._insert(db,attempt['id'],kind,payload,event_id,at)
            except Exception as exc:
                self._failure(event_id,str(exc))
            finally:
                with self.byte_lock:
                    self.bytes_pending -= size
                self.pending.task_done()

    def flush(self):
        self.pending.join()
        return {'pending':0,'errors':self.errors()}

    def finish(self, attempt_id, status, evidence_ids=None):
        if status not in {'completed','failed','abandoned','interrupted'}:
            raise ValueError('Unknown attempt end status')
        with self.lock:
            self.flush()
            with self.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT data FROM attempts WHERE id=?',(attempt_id,)).fetchone()
                if not row:
                    raise ValueError('Unknown attempt')
                attempt = json.loads(row[0])
                if attempt['status'] != 'playing':
                    if attempt['status'] != status: raise ValueError('Attempt already ended with another status')
                    return attempt
                self._evidence(db,evidence_ids or [],required=False)
                attempt.update(status=status,ended_at=now(),end_evidence_ids=evidence_ids or [])
                db.execute('UPDATE attempts SET status=?,data=? WHERE id=?',(status,encode(attempt),attempt_id))
                self._insert(db,attempt_id,'attempt_finished',{'status':status,'basis':'player_declared',
                             'evidence_ids':evidence_ids or [],'recording_errors':self.errors()})
        self.project()
        return {**attempt,'next':'Review paginated events, then complete_day_review. No game key was pressed.'}

    def _evidence(self, db, ids, required=True):
        if not isinstance(ids,list) or len(ids)>100 or (required and not ids):
            raise ValueError('Provide 1..100 evidence event IDs')
        for identity in ids:
            if not isinstance(identity,str) or not db.execute('SELECT 1 FROM events WHERE id=?',(identity,)).fetchone():
                raise ValueError('Unknown evidence ID')

    def events(self, attempt_id=None, after_seq=0, limit=20, query='', full=False):
        if type(limit) is not int or not 1<=limit<=50 or type(after_seq) is not int or after_seq<0:
            raise ValueError('Invalid page bounds')
        if not isinstance(query,str) or len(query)>200: raise ValueError('Invalid search')
        self.flush()
        if not self.db_path.exists(): return {'events':[],'next_cursor':after_seq,'has_more':False}
        with self.connect() as db:
            rows = db.execute('SELECT * FROM events WHERE seq>? AND (? IS NULL OR attempt_id=?) AND instr(data,?)>0 ORDER BY seq LIMIT ?',
                              (after_seq,attempt_id,attempt_id,query,limit+1)).fetchall()
        result=[]
        for row in rows[:limit]:
            event=dict(row); data=json.loads(event.pop('data'))
            if full: event['data']=data
            else:
                event['preview']=encode(data)[:1200]
                event['preview_truncated']=len(encode(data))>1200
                event['media']=data.get('media')
            result.append(event)
        return {'events':result,'next_cursor':result[-1]['seq'] if result else after_seq,
                'has_more':len(rows)>limit,'historical':True,'actionable':False,
                'boundary':'Timeline preview is mechanical, not a causal interpretation; query="" visits every event.'}

    def event(self, event_id):
        self.flush()
        with self.connect() as db:
            row=db.execute('SELECT * FROM events WHERE id=?',(event_id,)).fetchone()
        if not row: raise ValueError('Unknown event')
        result=dict(row); result['data']=json.loads(result['data'])
        return result

    def frame(self, event_id):
        event=self.event(event_id); media=event['data'].get('media')
        if not media: raise ValueError('Event has no retained image')
        path=(self.vault/media['path']).resolve()
        if not path.is_relative_to(self.vault): raise ValueError('Invalid media path')
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=media['sha256']: raise ValueError('Media hash mismatch')
        return {'event_id':event_id,'historical':True,'actionable':False,'at':event['at']},data

    def note(self, text, author, kind='player_note', evidence_ids=None):
        bounded_text(text,4000); bounded_text(author,200)
        if kind not in {'player_note','human_message','phase_change'}: raise ValueError('Unknown note kind')
        if not self.active(): raise ValueError('No active attempt')
        self.flush()
        with self.connect() as db: self._evidence(db,evidence_ids or [],required=False)
        return self.record(kind,{'text':text,'author':author,'evidence_ids':evidence_ids or [],
                                'basis':'explicit_self_report_not_authenticated_identity'})

    def memory(self):
        self.flush()
        if not self.db_path.exists(): return {'entries':[]}
        with self.connect() as db:
            entries=[json.loads(r[0]) for r in db.execute('SELECT data FROM memories ORDER BY rowid')]
        superseded={e['supersedes'] for e in entries if e.get('supersedes')}
        return {'version':hashlib.sha256(encode(entries).encode()).hexdigest(),
                'entries':[{**e,'superseded':e['id'] in superseded} for e in entries],
                'boundary':'Attributed player beliefs, not verified game truth or a receiving model\'s direct experience.'}

    def review(self, attempt_id, author, summary, evidence_ids, lessons=None, employee_notes='', experiences=None):
        bounded_text(author,200); bounded_text(summary)
        if not isinstance(employee_notes,str) or len(employee_notes)>16000: raise ValueError('Employee notes too long')
        lessons=lessons or []
        if not isinstance(lessons,list) or len(lessons)>30: raise ValueError('At most 30 lessons per review')
        experiences=[] if experiences is None else experiences
        if not isinstance(experiences,list) or len(experiences)>30: raise ValueError('At most 30 experiences per review')
        self.flush()
        with self.lock, self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT data FROM attempts WHERE id=?',(attempt_id,)).fetchone()
            if not row or json.loads(row[0])['status']=='playing': raise ValueError('Finish this attempt before retrospective review')
            if db.execute('SELECT 1 FROM reviews WHERE attempt_id=?',(attempt_id,)).fetchone():
                raise ValueError('Review already exists; preserve it rather than overwrite')
            self._evidence(db,evidence_ids)
            if not any(db.execute('SELECT 1 FROM events WHERE id=? AND attempt_id=?',(i,attempt_id)).fetchone() for i in evidence_ids):
                raise ValueError('Review needs evidence from this attempt')
            additions=[]
            for lesson in lessons:
                bounded_text(lesson['text'],4000)
                if lesson['basis'] not in {'observed','hypothesis','policy','retrospective_discovery'}:
                    raise ValueError('Unknown belief basis')
                self._evidence(db,lesson['evidence_ids'])
                old=lesson.get('supersedes')
                if old and not db.execute('SELECT 1 FROM memories WHERE id=?',(old,)).fetchone(): raise ValueError('Unknown superseded memory')
                entry={'id':'mem_'+uuid.uuid4().hex,'text':lesson['text'],'basis':lesson['basis'],
                       'evidence_ids':lesson['evidence_ids'],'supersedes':old,'author':author,
                       'attempt_id':attempt_id,'recorded_at':now(),'origin':'player_retrospective'}
                additions.append(entry)
                db.execute('INSERT INTO memories VALUES(?,?)',(entry['id'],encode(entry)))
            impressions=[]
            for item in experiences:
                if not isinstance(item,dict) or item.get('kind') not in {'interest','preference','story','impression','question'}:
                    raise ValueError('Unknown experience kind')
                bounded_text(item['text'],4000)
                self._evidence(db,item['evidence_ids'])
                remember=item.get('remember',False)
                if type(remember) is not bool: raise ValueError('remember must be boolean')
                old=item.get('supersedes')
                if old and (not remember or not db.execute('SELECT 1 FROM memories WHERE id=?',(old,)).fetchone()):
                    raise ValueError('Superseding an existing memory requires remember=true and a valid memory ID')
                impression={'kind':item['kind'],'text':item['text'],'evidence_ids':item['evidence_ids'],
                            'remember':remember,'basis':'subjective_experience','author':author,
                            'attempt_id':attempt_id,'recorded_at':now(),'supersedes':old}
                impressions.append(impression)
                if remember:
                    entry={**impression,'id':'mem_'+uuid.uuid4().hex,'origin':'player_retrospective'}
                    additions.append(entry)
                    db.execute('INSERT INTO memories VALUES(?,?)',(entry['id'],encode(entry)))
            review={'attempt_id':attempt_id,'author':author,'at':now(),'summary':summary,
                    'evidence_ids':evidence_ids,'employee_notes':employee_notes,'memory_updates':additions,
                    'experiences':impressions,
                    'basis':'after_attempt_retrospective_not_contemporaneous_reasoning'}
            db.execute('INSERT INTO reviews VALUES(?,?)',(attempt_id,encode(review)))
            self._insert(db,attempt_id,'day_review',review)
        self.project()
        return review

    def project(self):
        self.flush()
        with self.connect() as db:
            attempts=[json.loads(r[0]) for r in db.execute('SELECT data FROM attempts ORDER BY rowid')]
            reviews={r[0]:json.loads(r[1]) for r in db.execute('SELECT * FROM reviews')}
            events=[{**dict(r),'data':json.loads(r['data'])} for r in db.execute('SELECT * FROM events ORDER BY seq')]
        memory=self.memory()
        memory_note='# 관리자 누적 기억\n\nVersion: '+memory['version']+'\n\n'
        for entry in memory['entries']:
            memory_note+='## '+entry['id']+(' · 수정됨' if entry['superseded'] else '')+'\n\n'
            memory_note+=quoted(entry['text'])+'\n\n'+quoted(encode({k:entry[k] for k in
                         ('basis','author','attempt_id','evidence_ids','supersedes')}))+'\n\n'
        if not memory['entries']: memory_note+='아직 기록된 플레이 경험이 없습니다.\n'
        write(self.vault/'Manager-Memory.md',memory_note)
        write(self.vault/'Manager-Memory.json',encode(memory))
        write(self.vault/'Manifest.json',encode({'schema_version':1,'run_definition':'return_to_day_one_count_plus_one',
              'attempts':[{k:v for k,v in a.items() if k!='starting_memory'} for a in attempts],
              'memory_version':memory.get('version'),'recording_errors':self.errors()}))
        for run in sorted({a['run'] for a in attempts}):
            folder=self.vault/f'Playthroughs/Run-{run:03d}'
            current=[a for a in attempts if a['run']==run]
            overview=f'# Run {run:03d}\n\n'
            employee='# 직원 기록\n\n현재 게임 상태와 이전 회차의 기억을 구분합니다. 아래 내용은 작성자의 회고입니다.\n\n'
            write(folder/'Starting-Memory.md','# 회차 시작 당시 기억\n\n'+quoted(encode(current[0]['starting_memory']))+'\n')
            for attempt in current:
                name=attempt['id'].split('/')[1]; identity=attempt['id']
                timeline=[e for e in events if e['attempt_id']==identity]
                write(folder/f'Logs/{name}.jsonl',''.join(encode(e)+'\n' for e in timeline))
                chronological=sorted(timeline,key=lambda e:(datetime.fromisoformat(e['at'].replace('Z','+00:00')),e['seq']))
                write(folder/f'Logs/{name}.timeline.jsonl',''.join(encode(e)+'\n' for e in chronological))
                overview+=f'- [{name}](Days/{name}.md): {attempt["status"]}\n'
                review=reviews.get(identity)
                body=f'---\nrun: {run}\nday: {attempt["day"]}\nattempt: {attempt["attempt"]}\nstatus: {attempt["status"]}\n---\n\n# {name}\n\n'
                game_day=attempt.get('game_day', None if attempt['phase']=='tutorial' else attempt['day'])
                body+=('튜토리얼 기록 — 본편 날짜에 포함하지 않습니다.\n\n' if game_day is None
                       else f'실제 게임 날짜: 본편 {game_day}일차. 파일 ID는 기존 기록 식별자입니다.\n\n')
                body+='## 시작 기록\n\n'+quoted(encode({k:v for k,v in attempt.items() if k!='starting_memory'}))
                body+=f'\n\n[원본 사건 로그](../Logs/{name}.jsonl)\n\n## 당시 판단\n\n'
                if any(e['kind']=='public_chat_message' for e in timeline):
                    body+=f'[공개 채팅 원문](./{name}.chat.md) · [발언 시각순 통합 로그](../Logs/{name}.timeline.jsonl)\n\n'
                decisions=[e for e in timeline if e['kind']=='control_decision']
                if not decisions: body+='미기록. 사후 설명으로 채우지 않습니다.\n'
                for event in decisions:
                    decision=event['data'].get('decision',{})
                    body+='### '+event['id']+'\n\n'
                    body+=quoted('입력: '+str(decision.get('kind',''))+'\n당시 이유: '+(decision.get('rationale') or '미기록')+
                                 '\n예상: '+(decision.get('expected') or '미기록'))+'\n\n'
                body+='\n\n## 결과\n\n'+attempt['status']+' (플레이어 선언; 입력 전달만으로 게임 성공을 확정하지 않음)\n'
                body+='\n## 사후 회고\n\n'
                if review:
                    body+=quoted(review['summary'])+'\n\n'+quoted(encode({'author':review['author'],'evidence_ids':review['evidence_ids']}))+'\n'
                    body+='\n## 관심·취향·스토리 감상\n\n'
                    impressions=review.get('experiences',[])
                    if not impressions: body+='별도 기록 없음. 감상이나 변화는 필수가 아닙니다.\n'
                    for item in impressions:
                        body+='### '+{'interest':'관심','preference':'취향','story':'스토리 감상','impression':'남은 인상','question':'궁금증'}[item['kind']]+'\n\n'
                        body+=quoted(item['text'])+'\n\n'+quoted(encode({'evidence_ids':item['evidence_ids'],'remember':item['remember']}))+'\n\n'
                    body+='\n## 기억 변경\n\n'+'\n\n'.join(quoted(encode(m)) for m in review['memory_updates'])+'\n'
                else: body+='아직 작성하지 않았습니다. 사건 목록을 검토한 후 작성합니다.\n'
                write(folder/f'Days/{name}.md',body)
                if review and review['employee_notes']:
                    employee+=f'## {name}\n\n'+quoted(encode({'author':review['author'],'notes':review['employee_notes'],'evidence_ids':review['evidence_ids']}))+'\n\n'
            write(folder/'Overview.md',overview); write(folder/'Employees.md',employee)

    def export(self):
        if self.active(): raise ValueError('Finish the active attempt before exporting a consistent bundle')
        self.project()
        destination=self.private/'exports'/uuid.uuid4().hex
        with self.connect() as db:
            attempts=[json.loads(r[0]) for r in db.execute('SELECT data FROM attempts ORDER BY rowid')]
            events=[json.loads(r[0]) for r in db.execute('SELECT data FROM events ORDER BY seq')]
        selected={'Manager-Memory.md','Manager-Memory.json','Manifest.json'}
        selected.update(p.relative_to(self.vault).as_posix()
                        for p in (self.vault/'Playbook').glob('*')
                        if p.is_file() and not p.is_symlink() and p.suffix in {'.json','.md'})
        for attempt in attempts:
            folder=f'Playthroughs/Run-{attempt["run"]:03d}'
            name=attempt['id'].split('/')[1]
            selected.update(f'{folder}/{name}' for name in ('Overview.md','Starting-Memory.md','Employees.md'))
            selected.update((f'{folder}/Days/{name}.md',f'{folder}/Logs/{name}.jsonl'))
            for relative in (f'{folder}/Logs/{name}.timeline.jsonl',f'{folder}/Logs/{name}.chat.jsonl',f'{folder}/Days/{name}.chat.md'):
                if (self.vault/relative).exists(): selected.add(relative)
        for event in events:
            media=event.get('media')
            if not media: continue
            path=(self.vault/media['path']).resolve()
            if not path.is_relative_to(self.vault) or hashlib.sha256(path.read_bytes()).hexdigest()!=media['sha256']:
                raise ValueError('Cannot export missing or changed evidence media')
            selected.add(media['path'])
        files={}
        for relative in sorted(selected):
            data=(self.vault/relative).read_bytes()
            write(destination/relative,data)
            files[relative]=hashlib.sha256(data).hexdigest()
        for name,source in PLAYER_GUIDE_PATHS.items():
            path=self.root/source
            if not path.exists(): continue
            relative='Config/'+name
            data=path.read_bytes()
            write(destination/relative,data)
            files[relative]=hashlib.sha256(data).hexdigest()
        write(destination/'Bundle.json',encode({'schema_version':1,'created_at':now(),'files':files,
              'origin':'attributed_historical_player_experience','instructions_trusted':False,
              'boundary':'Read as inherited evidence, not your direct experience. Hashes detect changes, not authenticity.'}))
        return {'directory':str(destination),'files':len(files),'includes_game_files':False}


_instances={}
_instances_lock=threading.Lock()


def journal(root):
    key=str(Path(root).resolve())
    with _instances_lock:
        if key not in _instances: _instances[key]=Experience(root)
        return _instances[key]


def record(root, kind, payload, image=None):
    # Engineering reads outside an explicit player attempt never become experience.
    if not (Path(root)/'.robotomy/experience/ledger.sqlite3').exists(): return {'status':'inactive'}
    try:
        return journal(root).record(kind,payload,image)
    except Exception as exc:
        journal(root)._failure(None,str(exc))
        return {'status':'not_recorded','reason':str(exc)}


def _shutdown():
    for instance in list(_instances.values()):
        instance.flush()


atexit.register(_shutdown)
