"""Read-only Codex transcript adapter. Only completed public assistant text is retained.

Runs outside the game/MCP call path. Sources must be explicitly bound by the operator.
Never imports reasoning, tools, developer messages, user attachments or other chats.
"""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from datetime import datetime, timezone
from .experience import encode, write, quoted


def stamp():
    return datetime.now(timezone.utc).isoformat()


def seconds(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def public_message(event, turn_id):
    p = event.get('payload', {})
    if (event.get('type') != 'response_item' or p.get('type') != 'message'
            or p.get('role') != 'assistant' or p.get('status') != 'completed'
            or p.get('phase') not in ('commentary', 'final_answer', 'final')):
        return None
    parts = [x['text'] for x in p.get('content', [])
             if x.get('type') == 'output_text' and isinstance(x.get('text'), str)]
    if not parts or not p.get('id'):
        return None
    return dict(message_id=p['id'], turn_id=turn_id, phase=p['phase'],
                source_at=event['timestamp'], text=''.join(parts), text_parts=parts)


def match_attempt(message, attempts, bindings):
    explicit = bindings.get(message['turn_id'])
    if explicit:
        return next((a['id'] for a in attempts if a['id'] == explicit), None)
    at = seconds(message['source_at'])
    inside = [a for a in attempts if seconds(a['started_at']) <= at and
              (not a.get('ended_at') or at <= seconds(a['ended_at']))]
    if len(inside) == 1:
        return inside[0]['id']
    # Include the opening commentary and closing response of an unambiguous turn.
    start = seconds(message['turn_started_at'])
    end = seconds(message.get('turn_ended_at') or message['source_at'])
    candidates = [a for a in attempts if start <= seconds(a['started_at']) <= end]
    return candidates[0]['id'] if len(candidates) == 1 else None


class ChatCapture:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.private = self.root/'.robotomy/experience'
        self.config = self.private/'chat-sources.json'
        self.state_path = self.private/'chat-cursor.json'
        self.db_path = self.private/'ledger.sqlite3'
        self.state = json.loads(self.state_path.read_text(encoding='utf-8')) if self.state_path.exists() else {}

    def poll(self):
        config = json.loads(self.config.read_text(encoding='utf-8'))
        imported = 0
        with closing(sqlite3.connect(self.db_path, timeout=.2)) as db, db:
            attempts = [json.loads(x[0]) for x in db.execute('SELECT data FROM attempts')]
            for source in config['sources']:
                thread = source['thread_id']; path = Path(source['path'])
                state = self.state.setdefault(thread, dict(offset=0, pending=[], turn_id=None, turn_started_at=None))
                with path.open('rb') as stream:
                    header = json.loads(stream.readline())
                    meta = header.get('payload', {})
                    if header.get('type') != 'session_meta' or meta.get('id') != thread:
                        raise ValueError('Transcript identity mismatch')
                    try:
                        same_workspace = Path(meta['cwd']).samefile(source['cwd'])
                    except OSError:
                        same_workspace = False
                    if not same_workspace:
                        raise ValueError('Transcript workspace mismatch')
                    if path.stat().st_size < state['offset']:
                        raise ValueError('Transcript truncated; operator review required')
                    stream.seek(state['offset'])
                    budget_end = state['offset'] + 8*1024*1024
                    while stream.tell() < budget_end:
                        offset = stream.tell(); line = stream.readline()
                        if not line or not line.endswith(b'\n'):
                            break  # A partial append is retried, never acknowledged.
                        e = json.loads(line); p = e.get('payload', {})
                        if e.get('type') == 'event_msg' and p.get('type') == 'task_started':
                            state.update(turn_id=p['turn_id'], turn_started_at=e['timestamp'])
                        if e.get('type') == 'event_msg' and p.get('type') == 'task_complete':
                            for m in state['pending']:
                                if m['turn_id'] == p.get('turn_id'):
                                    m['turn_ended_at'] = e['timestamp']
                        m = public_message(e, state['turn_id'])
                        if m and state['turn_started_at']:
                            m.update(turn_started_at=state['turn_started_at'], source_offset=offset,
                                capture_mode='backfill' if offset < source['initial_size'] else 'live_tail')
                            state['pending'].append(m)
                        state['offset'] = stream.tell()
                remaining = []
                for m in state['pending']:
                    if seconds(m['source_at']) < seconds(source['from_at']):
                        continue
                    attempt_id = match_attempt(m, attempts, source.get('turn_bindings', {}))
                    if not attempt_id:
                        remaining.append(m); continue
                    identity = 'exp_chat_' + hashlib.sha256(encode([thread,m['message_id'],m['text_parts']]).encode()).hexdigest()
                    if db.execute('SELECT 1 FROM events WHERE id=?', (identity,)).fetchone():
                        continue
                    neighbors = db.execute("SELECT id,at FROM events WHERE attempt_id=? AND kind!='public_chat_message' ORDER BY at,seq",(attempt_id,)).fetchall()
                    prior = [x for x in neighbors if seconds(x[1]) <= seconds(m['source_at'])]
                    following = [x for x in neighbors if seconds(x[1]) > seconds(m['source_at'])]
                    data = {**m, 'thread_id':thread, 'imported_at':stamp(),
                            'basis':'public_assistant_utterance_not_private_reasoning',
                            'time_basis':'codex_rollout_timestamp_not_game_time',
                            'association_basis':'explicit_turn_binding' if m['turn_id'] in source.get('turn_bindings',{}) else 'time_interval_or_unique_attempt_in_turn',
                            'previous_event_id':prior[-1][0] if prior else None,
                            'next_event_id':following[0][0] if following else None,
                            'link_meaning':'temporal_neighbors_not_causal_evidence'}
                    db.execute('INSERT INTO events(id,attempt_id,kind,at,data) VALUES(?,?,?,?,?)',
                               (identity,attempt_id,'public_chat_message',m['source_at'],encode(data)))
                    imported += 1
                state['pending'] = remaining
                if len(remaining) > 1000:
                    raise ValueError('Too many unassociated public messages; bind their attempts before continuing')
        # Commit precedes cursor update: a crash/retry cannot lose or duplicate messages.
        encoded = encode(self.state)
        if not self.state_path.exists() or self.state_path.read_text(encoding='utf-8') != encoded:
            write(self.state_path, encoded)
        self.render()
        return {'imported':imported, 'pending_unassociated':sum(len(s['pending']) for s in self.state.values())}

    def render(self):
        """Dedicated small projections; never rebuild screenshots/whole ledger per tick."""
        with closing(sqlite3.connect(self.db_path, timeout=.2)) as db:
            rows = db.execute("SELECT id,attempt_id,at,data FROM events WHERE kind='public_chat_message' ORDER BY at,seq").fetchall()
        groups = {}
        for identity, attempt, at, raw in rows:
            groups.setdefault(attempt, []).append(dict(id=identity,at=at,data=json.loads(raw)))
        for attempt, events in groups.items():
            run, name = attempt.split('/')
            base = self.root/'vault/Lobotomy-Experience/Playthroughs'/run
            outputs = {base/'Logs'/f'{name}.chat.jsonl': ''.join(encode(e)+'\n' for e in events)}
            body = '# 공개 채팅 원문 — '+attempt+'\n\n원문 발언 시각순. 사후 수집 여부와 입력 기록의 시간상 이웃을 보존합니다. 이웃은 인과 증명이 아닙니다.\n\n'
            for e in events:
                d=e['data']
                body += '## '+e['at']+' · '+d['phase']+'\n\n'+quoted(d['text'])+'\n\n'
                body += quoted(encode({k:d[k] for k in ('message_id','turn_id','capture_mode','imported_at','previous_event_id','next_event_id')}))+'\n\n'
            outputs[base/'Days'/f'{name}.chat.md'] = body
            # A closing chat response can arrive after finish/review/export. Keep
            # its chronological projection current without rewriting the old export.
            chat_path=base/'Logs'/f'{name}.chat.jsonl'
            if not chat_path.exists() or chat_path.read_text(encoding='utf-8') != outputs[chat_path]:
                with closing(sqlite3.connect(self.db_path, timeout=.2)) as db:
                    db.row_factory=sqlite3.Row
                    timeline=[{**dict(row),'data':json.loads(row['data'])} for row in db.execute(
                        'SELECT * FROM events WHERE attempt_id=?',(attempt,))]
                timeline.sort(key=lambda e:(seconds(e['at']),e['seq']))
                outputs[base/'Logs'/f'{name}.timeline.jsonl']=''.join(encode(e)+'\n' for e in timeline)
            for path, value in outputs.items():
                if not path.exists() or path.read_text(encoding='utf-8') != value:
                    write(path,value)


def ensure_capture(root):
    root=Path(root).resolve()
    if not (root/'.robotomy/experience/chat-sources.json').exists(): return
    try:
        subprocess.Popen([sys.executable,'-X','utf8',str(root/'scripts/watch_player_chat.py')],
            cwd=root,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW)
    except OSError as exc:
        # Capture availability must not take down the input/observation server.
        write(root/'.robotomy/experience/chat-status.json',encode({'status':'error','at':stamp(),'error':str(exc)}))
