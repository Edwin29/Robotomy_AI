import json
from pathlib import Path
import tempfile
import sqlite3
import unittest
from robotomy.chat_capture import ChatCapture, public_message, match_attempt
from robotomy.experience import Experience


class ChatCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.experience=Experience(self.root)
        self.experience.setup();self.attempt=self.experience.begin(1,'fixture',phase='tutorial')
        self.path=self.root/'transcript.jsonl';self.thread='fixture-thread'
        self.path.write_text(json.dumps({'type':'session_meta','payload':{'id':self.thread,'cwd':str(self.root)}})+'\n')
        self.append({'type':'event_msg','timestamp':'2026-10-18T05:00:00Z','payload':{'type':'task_started','turn_id':'turn'}})
        self.config=self.experience.private/'chat-sources.json'
        self.config.write_text(json.dumps({'sources':[{'thread_id':self.thread,'path':str(self.path),'cwd':str(self.root),
            'initial_size':100000,'from_at':'2026-10-18T00:00:00Z','turn_bindings':{'turn':self.attempt['id']}}]}))

    def append(self,e):
        with self.path.open('a',encoding='utf-8') as f:f.write(json.dumps(e,ensure_ascii=False)+'\n')

    def message(self,text='오해했습니다.\n次は訂正します。',identity='message'):
        return {'type':'response_item','timestamp':'2026-10-18T05:01:00Z','payload':{
            'type':'message','status':'completed','role':'assistant','phase':'commentary',
            'id':identity,'content':[{'type':'output_text','text':text}]}}

    def chats(self):
        with self.experience.connect() as db:
            return [json.loads(r[0]) for r in db.execute("select data from events where kind='public_chat_message'")]

    def test_original_text_backfill_deduplicated_and_exported(self):
        self.append(self.message());self.append(self.message())
        self.experience.finish(self.attempt['id'],'completed')
        self.assertEqual(ChatCapture(self.root).poll()['imported'],1)
        self.assertEqual(self.chats()[0]['text'],'오해했습니다.\n次は訂正します。')
        self.assertEqual(self.chats()[0]['capture_mode'],'backfill')
        # Lost cursor after DB commit is safe to replay.
        (self.experience.private/'chat-cursor.json').unlink()
        self.assertEqual(ChatCapture(self.root).poll()['imported'],0)
        self.experience.export()
        bundle=next((self.experience.private/'exports').glob('*/Bundle.json'))
        files=json.loads(bundle.read_text())['files']
        self.assertTrue(any(p.endswith('.chat.jsonl') for p in files))
        self.assertTrue(any(p.endswith('.timeline.jsonl') for p in files))

    def test_private_and_tool_content_never_imported(self):
        for role,phase in [('assistant','analysis'),('user','commentary'),('developer','commentary')]:
            e=self.message('PRIVATE');e['payload'].update(role=role,phase=phase);self.append(e)
        self.append({'type':'response_item','payload':{'type':'reasoning','text':'PRIVATE'}})
        self.append({'type':'event_msg','payload':{'type':'task_complete','last_agent_message':'duplicate'}})
        self.assertEqual(ChatCapture(self.root).poll()['imported'],0)
        self.assertNotIn('PRIVATE',(self.experience.private/'chat-cursor.json').read_text())

    def test_partial_append_is_retried_and_mismatch_rejected(self):
        raw=json.dumps(self.message(),ensure_ascii=False).encode('utf-8')
        with self.path.open('ab') as f:f.write(raw[:len(raw)//2])
        self.assertEqual(ChatCapture(self.root).poll()['imported'],0)
        with self.path.open('ab') as f:f.write(raw[len(raw)//2:]+b'\n')
        self.assertEqual(ChatCapture(self.root).poll()['imported'],1)
        cfg=json.loads(self.config.read_text());cfg['sources'][0]['cwd']=str(self.root/'other');self.config.write_text(json.dumps(cfg))
        with self.assertRaisesRegex(ValueError,'workspace'):ChatCapture(self.root).poll()

    def test_correction_does_not_replace_original(self):
        self.append(self.message('가득 찼다.','first'));self.append(self.message('최대치였다. 정정한다.','second'))
        ChatCapture(self.root).poll()
        self.assertEqual([x['text'] for x in self.chats()],['가득 찼다.','최대치였다. 정정한다.'])

    def test_ambiguous_turn_is_not_guessed(self):
        m={'turn_id':'turn','source_at':'2026-10-18T05:03:00Z','turn_started_at':'2026-10-18T05:00:00Z'}
        attempts=[dict(id=str(i),started_at=f'2026-10-18T05:0{i}:00Z',ended_at=f'2026-10-18T05:0{i}:30Z') for i in (1,2)]
        self.assertIsNone(match_attempt(m,attempts,{}))

    def test_live_append_and_locked_database_retry(self):
        cfg=json.loads(self.config.read_text());cfg['sources'][0]['initial_size']=self.path.stat().st_size
        self.config.write_text(json.dumps(cfg))
        ChatCapture(self.root).poll()
        previous=(self.experience.private/'chat-cursor.json').read_bytes()
        self.append(self.message('새 공개 발언'))
        lock=sqlite3.connect(self.experience.db_path)
        try:
            lock.execute('BEGIN IMMEDIATE')
            with self.assertRaises(sqlite3.OperationalError):ChatCapture(self.root).poll()
            self.assertEqual(previous,(self.experience.private/'chat-cursor.json').read_bytes())
        finally:lock.rollback();lock.close()
        self.assertEqual(ChatCapture(self.root).poll()['imported'],1)
        self.assertEqual(self.chats()[0]['capture_mode'],'live_tail')
