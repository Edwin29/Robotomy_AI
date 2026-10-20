"""Synthetic journal fixtures: no game, save, microphone or playback operations."""
import json
from pathlib import Path
import tempfile
import unittest
from robotomy.live import AudioJournal,audio_event,player_audio


def event(n,**extra):
    return dict(event_id=n,at_utc='2026-10-18T00:00:00Z',kind='start',
                source_token='a'*32,sound_token='b'*32,**extra)


class AudioTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root=Path(temp.name); self.session='c'*32
        self.path=self.root/('audio-'+self.session+'.jsonl')
        self.reader=AudioJournal(self.root)

    def write(self,events):
        with self.path.open('a',encoding='utf-8') as f:
            for e in events: f.write(json.dumps(e)+'\n')

    def test_more_than_snapshot_capacity_and_no_replay(self):
        self.write(event(n) for n in range(1,701))
        cursor=0; got=[]
        for _ in range(7):
            r=self.reader.read(self.session,cursor,100)
            self.assertEqual(r['status'],'ok'); self.assertEqual(r['gaps'],[])
            got.extend(e['event_id'] for e in r['events']); cursor=r['next_event_id']
        self.assertEqual(got,list(range(1,701)))
        self.assertEqual(self.reader.read(self.session,cursor)['events'],[])

    def test_partial_append_and_gap(self):
        self.write([event(1)])
        with self.path.open('ab') as f: f.write(json.dumps(event(3)).encode())
        r=self.reader.read(self.session)
        self.assertEqual(r['next_event_id'],1); self.assertTrue(r['catching_up'])
        with self.path.open('ab') as f: f.write(b'\n')
        r=self.reader.read(self.session,1)
        self.assertEqual(r['gaps'],[dict(first=2,last=2)])
        self.assertEqual(r['next_event_id'],3)

    def test_new_session_and_invalid_filename(self):
        self.write([event(1)])
        self.reader.read(self.session)
        self.assertEqual(self.reader.read('../bad')['status'],'unavailable')
        self.assertEqual(self.reader.read('d'*32)['status'],'journal_pending')
        self.assertEqual(self.reader.read(self.session)['next_event_id'],1)

    def test_long_backlog_is_drained_before_more_ingestion(self):
        self.write(event(n) for n in range(1,7001))
        cursor=0
        for _ in range(70):
            r=self.reader.read(self.session,cursor,100)
            self.assertEqual(r['gaps'],[])
            self.assertGreater(r['next_event_id'],cursor)
            cursor=r['next_event_id']
        # Chunk boundaries can yield fewer than 100 records.
        while r['has_more']:
            r=self.reader.read(self.session,cursor,100)
            self.assertEqual(r['gaps'],[]); cursor=r['next_event_id']
        self.assertEqual(cursor,7000)

    def test_invalid_and_reset_are_not_silence(self):
        self.write([event(1)])
        self.reader.read(self.session)
        self.path.write_bytes(b'')
        self.assertEqual(self.reader.read(self.session,1)['status'],'journal_reset')
        self.path.write_bytes(b'{bad}\n')
        self.assertEqual(self.reader.read(self.session)['status'],'invalid_journal')

    def test_only_known_semantics_and_opaque_unknown_identity(self):
        for name in ('first_trumpet','second_trumpet','third_trumpet','qliphoth_meltdown'):
            r=audio_event(event(1,sound_id=name,label='hidden phase 4',attack_timer=.5))
            self.assertEqual(r['sound_id'],name)
            self.assertNotIn('attack_timer',r); self.assertNotIn('hidden',r['label'])
        r=audio_event(event(1,sound_id='sound_'+'f'*24,label='boss phase'))
        self.assertEqual(r['category'],'unclassified_sound')
        self.assertNotIn('sound_id',audio_event(event(1,sound_id='boss_phase_4')))

    def test_consumer_does_not_receive_routine_engineering_caveats(self):
        value=player_audio(dict(status='ok',events=[event(1)],session=self.session,
             next_event_id=1,has_more=False,producer_dropped=0,gaps=[],boundary='diagnostic'))
        self.assertEqual(set(value),{'events','session','next_event_id','has_more'})
        self.assertNotIn('notice',player_audio(dict(status='journal_pending',events=[])))
        self.assertIn('notice',player_audio(dict(status='invalid_journal',events=[])))

if __name__=='__main__': unittest.main()
