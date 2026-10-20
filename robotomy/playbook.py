"""Portable player-authored procedures. Data only: never executes stored steps."""
from contextlib import contextmanager
from pathlib import Path
import json
import msvcrt
import re
import uuid
from .experience import bounded_text, encode, now, quoted, write

class Playbook:
    def __init__(self, root, experience):
        self.root = Path(root)
        self.folder = self.root/'vault/Lobotomy-Experience/Playbook'
        self.experience = experience

    def path(self, identity):
        if not isinstance(identity, str) or not re.fullmatch(r'pb_[0-9a-f]{32}', identity):
            raise ValueError('Invalid playbook ID')
        return self.folder/(identity+'.json')

    @contextmanager
    def lock(self):
        p = self.root/'.robotomy/experience/playbook.lock'
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('a+b') as stream:
            if p.stat().st_size == 0: stream.write(b'0'); stream.flush()
            stream.seek(0)
            try: msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError: raise ValueError('Another playbook write is active; retry shortly')
            try: yield
            finally:
                stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)

    def save(self, entry, entry_id='', expected_revision=0):
        if not isinstance(entry, dict): raise ValueError('Entry must be a JSON object')
        if {'id','revision','updated_at'} & set(entry): raise ValueError('IDs/revisions/timestamps are assigned by storage; omit them from entry')
        if type(expected_revision) is not int or expected_revision < 0: raise ValueError('Invalid revision')
        data = dict(entry)
        for key, size in [('title',160),('author',200)]:
            bounded_text(data.get(key),size)
        data.setdefault('category','');data.setdefault('subject','');data.setdefault('summary','')
        data.setdefault('status','active')
        data.setdefault('startup',False);data.setdefault('tags',[]);data.setdefault('evidence_ids',[])
        if data['status'] not in {'active','archived'} or type(data['startup']) is not bool: raise ValueError('Invalid status/startup')
        for key in ('category','subject','summary'):
            if not isinstance(data[key],str) or len(data[key])>1000: raise ValueError('Invalid index field')
        for key, count, size in [('tags',20,80),('evidence_ids',40,200)]:
            if not isinstance(data[key],list) or len(data[key])>count: raise ValueError('Invalid '+key)
            for value in data[key]: bounded_text(value,size)
        # Everything else is player-defined JSON: content, tables, procedures, schemas, etc.
        if len(encode(data).encode('utf8'))>65536: raise ValueError('Entry exceeds 64 KiB; split into linked entries')
        self.experience.flush()
        if data['evidence_ids']:
            if not self.experience.db_path.exists(): raise ValueError('No experience evidence exists')
            with self.experience.connect() as db:
                for identity in data['evidence_ids']:
                    if not db.execute('SELECT 1 FROM events WHERE id=?',(identity,)).fetchone():
                        raise ValueError('Unknown evidence ID: '+identity)
        with self.lock():
            if entry_id:
                path=self.path(entry_id)
                if not path.exists(): raise ValueError('Unknown playbook entry')
                document=json.loads(path.read_text(encoding='utf8'))
                if document['revisions'][-1]['revision']!=expected_revision:
                    raise ValueError('Revision conflict; read the latest entry before updating')
            else:
                if expected_revision: raise ValueError('New entries require revision 0')
                entry_id='pb_'+uuid.uuid4().hex;path=self.path(entry_id)
                document={'schema_version':1,'id':entry_id,'revisions':[]}
            data.update(id=entry_id,revision=expected_revision+1,updated_at=now())
            document['revisions'].append(data)
            write(path,encode(document)+'\n')
            body='# '+data['title'].replace('\n',' ')+'\n\nPlayer-authored belief/procedure; not automatic input.\n\n'
            body+=quoted(json.dumps(data,ensure_ascii=False,indent=2))+'\n\n## Revision history\n\n'
            body+='\n'.join('- revision '+str(r['revision'])+' · '+r['updated_at'] for r in document['revisions'])+'\n'
            write(path.with_suffix('.md'),body)
        return data

    def read(self, query='', category='', entry_id='', startup_only=False, include_history=False,
             include_archived=False, limit=10, offset=0):
        if type(limit) is not int or not 1<=limit<=30 or type(offset) is not int or offset<0:
            raise ValueError('Invalid page')
        if not isinstance(query,str) or len(query)>300 or not isinstance(category,str):
            raise ValueError('Invalid search')
        if entry_id:
            path=self.path(entry_id)
            if not path.exists(): raise ValueError('Unknown playbook entry')
            doc=json.loads(path.read_text(encoding='utf8'))
            return doc if include_history else doc['revisions'][-1]
        matches=[]
        for path in sorted(self.folder.glob('pb_*.json')):
            doc=json.loads(path.read_text(encoding='utf8'));row=doc['revisions'][-1]
            if not include_archived and row['status']=='archived': continue
            if startup_only and not row['startup']: continue
            if category and row['category']!=category: continue
            if any(word not in encode(row).casefold() for word in query.casefold().split()): continue
            matches.append(row)
        matches.sort(key=lambda r:r['updated_at'],reverse=True)
        keys=('id','revision','title','category','subject','tags','summary','startup','status')
        return {'entries':[{k:r[k] for k in keys} for r in matches[offset:offset+limit]],
                'total':len(matches),'next_offset':offset+limit if offset+limit<len(matches) else None,
                'boundary':'Player-authored experience, not game truth. Read by ID for steps. Never executes automatically.'}
