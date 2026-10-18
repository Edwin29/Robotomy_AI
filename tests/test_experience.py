"""Recording/transfer contracts in temporary roots; never an actual playthrough."""
import base64
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from robotomy.experience import Experience, journal, record, PLAYER_GUIDE_PATHS
from robotomy.live import LiveReader
from datetime import datetime, timezone


PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aC1sAAAAASUVORK5CYII=')


class ExperienceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.j=journal(self.root)

    def tearDown(self):
        self.j.flush()
        self.temp.cleanup()

    def begin(self,day=1,reason='next_day',player='fixture-not-real-player'):
        return self.j.begin(day,player,reason)

    def test_no_attempt_means_engineering_reads_are_not_experience(self):
        self.assertEqual(record(self.root,'observation_offered',{'visible':'fixture'}),{'status':'inactive'})
        self.assertFalse(self.j.private.exists())
        self.j.setup()
        self.assertEqual(self.j.status()['attempts'],[])
        self.assertEqual(record(self.root,'observation_offered',{}),{'status':'inactive'})

    def test_runs_follow_game_reset_not_model_or_retry(self):
        a=self.begin(2); self.j.finish(a['id'],'failed')
        b=self.begin(2,'retry','different-model')
        self.assertEqual((b['run'],b['attempt']),(1,2))
        self.assertEqual(b['previous_attempt_id'],a['id'])
        self.j.finish(b['id'],'abandoned')
        c=self.begin(1,'memory_repository'); self.assertEqual(c['run'],1)
        self.j.finish(c['id'],'completed')
        d=self.begin(1,'return_to_day_one'); self.assertEqual((d['run'],d['attempt']),(2,1))
        with self.assertRaises(ValueError): self.begin()

    def test_operator_restore_preserves_old_attempt_and_run(self):
        first=self.begin(1); self.j.finish(first['id'],'completed')
        later=self.begin(2); self.j.finish(later['id'],'interrupted')
        replay=self.begin(1,'operator_restore')
        self.assertEqual((replay['run'],replay['day'],replay['attempt']),(1,1,2))
        self.assertEqual(replay['previous_attempt_id'],later['id'])
        self.assertEqual([a['status'] for a in self.j.status()['attempts']],
                         ['completed','interrupted','playing'])

    def test_tutorial_to_main_day_one_keeps_run_and_old_records(self):
        first=self.j.begin(1,'fixture',phase='tutorial')
        self.j.finish(first['id'],'completed')
        last=self.j.begin(3,'fixture',phase='tutorial')
        self.j.finish(last['id'],'completed')
        main=self.j.begin(1,'fixture',phase='story')
        self.assertEqual((main['run'],main['day'],main['game_day']),(1,1,1))
        self.assertNotEqual(main['id'],first['id'])
        self.assertIsNone(last['game_day'])
        self.j.finish(main['id'],'completed')
        second=self.j.begin(2,'fixture')
        self.j.finish(second['id'],'completed')
        with self.assertRaisesRegex(ValueError,'return_to_day_one'):
            self.j.begin(1,'fixture')

    def test_background_capture_is_frozen_and_no_hot_markdown(self):
        a=self.begin(); path=self.j.vault/'Manager-Memory.md'; old=path.read_bytes()
        gate=threading.Event(); entered=threading.Event(); original=self.j._insert
        def delayed(*args,**kwargs):
            entered.set(); gate.wait(3); return original(*args,**kwargs)
        payload={'visible':['original']}
        with patch.object(self.j,'_insert',side_effect=delayed):
            start=time.monotonic(); receipt=self.j.record('observation_offered',payload)
            self.assertLess(time.monotonic()-start,.5)
            entered.wait(1); payload['visible'][0]='mutated'
            self.assertFalse(receipt['durable']); self.assertEqual(path.read_bytes(),old)
            gate.set(); self.j.flush()
        self.assertEqual(self.j.event(receipt['event_id'])['data']['visible'],['original'])
        self.assertEqual(self.j.events(a['id'])['events'][-1]['id'],receipt['event_id'])

    def test_pause_has_no_effect_on_offered_story_media_and_deduplicates(self):
        a=self.begin(); control=self.root/'.robotomy/live/control'; control.mkdir(parents=True)
        (control/'PAUSED').write_text('operator stop')
        one=self.j.record('frame_offered',{'scene':'story','frame_unity_frame':12},PNG)
        self.j.record('frame_offered',{'scene':'story','frame_unity_frame':12},PNG)
        self.j.finish(a['id'],'completed')
        self.assertEqual(len(list(self.j.vault.rglob('*.png'))),1)
        status,data=self.j.frame(one['event_id']); self.assertTrue(status['historical']); self.assertEqual(data,PNG)
        self.assertEqual((control/'PAUSED').read_text(),'operator stop')
        media=self.j.event(one['event_id'])['data']['media']
        (self.j.vault/media['path']).write_bytes(b'changed')
        with self.assertRaises(ValueError): self.j.frame(one['event_id'])

    def test_queue_failure_is_explicit_and_survives_restart(self):
        self.begin()
        self.j.bytes_pending=32*1024*1024
        result=self.j.record('observation_offered',{'visible':'fixture'})
        self.assertEqual(result['status'],'not_recorded')
        self.assertTrue(Experience(self.root).status()['recording_errors'])
        self.j.bytes_pending=0

    def test_writer_exception_is_reported_without_false_success(self):
        self.begin()
        with patch.object(self.j,'_insert',side_effect=OSError('simulated disk failure')):
            receipt=self.j.record('frame_offered',{},PNG); result=self.j.flush()
        self.assertEqual(result['errors'][0]['event_id'],receipt['event_id'])
        with self.assertRaises(ValueError): self.j.event(receipt['event_id'])

    def test_reflection_requires_evidence_and_preserves_belief_revisions(self):
        a=self.begin(); e=self.j.record('observation_offered',{'text':'visible message'})['event_id']
        with self.assertRaises(ValueError): self.j.review(a['id'],'fixture','too early',[e])
        self.j.finish(a['id'],'failed')
        with self.assertRaises(ValueError): self.j.review(a['id'],'fixture','invented',['missing'])
        r=self.j.review(a['id'],'fixture','Retrospective, not a pre-action reason',[e],
                        [{'text':'tentative belief','basis':'hypothesis','evidence_ids':[e]}], 'Employee evaluation')
        original=r['memory_updates'][0]
        b=self.begin(1,'return_to_day_one')
        self.assertEqual(b['starting_memory'][0],original)
        self.assertEqual(b['memory_version'],self.j.memory()['version'])
        f=self.j.record('observation_offered',{'text':'contrary observation'})['event_id']
        self.j.finish(b['id'],'completed')
        self.j.review(b['id'],'second-model','Correct previous belief',[f],
                      [{'text':'revised belief','basis':'retrospective_discovery','evidence_ids':[f], 'supersedes':original['id']}])
        entries=self.j.memory()['entries']
        self.assertEqual(entries[0]['text'],'tentative belief'); self.assertTrue(entries[0]['superseded'])
        self.assertFalse(entries[1]['superseded']); self.assertEqual(entries[1]['author'],'second-model')
        with self.assertRaises(ValueError): self.j.review(a['id'],'fixture','overwrite',[e])
        note=(self.j.vault/'Playthroughs/Run-001/Days/Day-01-Attempt-01.md').read_text(encoding='utf-8')
        self.assertIn('미기록',note)

    def test_pagination_and_portable_media_export(self):
        a=self.begin()
        for i in range(8): self.j.record('observation_offered',{'n':i})
        image=self.j.record('frame_offered',{'scene':'fixture'},PNG)['event_id']
        self.j.finish(a['id'],'interrupted')
        page=self.j.events(a['id'],limit=3); self.assertTrue(page['has_more'])
        second=self.j.events(a['id'],after_seq=page['next_cursor'],limit=50)
        self.assertFalse(set(e['id'] for e in page['events']) & set(e['id'] for e in second['events']))
        self.assertEqual(len(self.j.events(query='"n": 7')['events']),1)
        result=self.j.export(); folder=Path(result['directory']); manifest=json.loads((folder/'Bundle.json').read_text(encoding='utf-8'))
        for relative,digest in manifest['files'].items():
            self.assertEqual(hashlib.sha256((folder/relative).read_bytes()).hexdigest(),digest)
        media=self.j.event(image)['data']['media']; self.assertEqual((folder/media['path']).read_bytes(),PNG)
        self.assertFalse(list(folder.rglob('*.sqlite3')))
        resumed=Experience(self.root); self.assertEqual(len(resumed.events(limit=50)['events']),11)

    def test_subjective_only_review_and_selective_cross_run_retention(self):
        a=self.begin(); e=self.j.record('frame_offered',{'scene':'fixture story'},PNG)['event_id']
        self.j.finish(a['id'],'completed')
        review=self.j.review(a['id'],'first player','No lesson or behavior change',[e], experiences=[
            {'kind':'story','text':'The scene stayed with me','evidence_ids':[e]},
            {'kind':'preference','text':'I like this visual style','evidence_ids':[e],'remember':True}])
        self.assertEqual(len(review['experiences']),2)
        self.assertEqual(len(review['memory_updates']),1)
        old=review['memory_updates'][0]
        self.assertEqual(old['basis'],'subjective_experience')
        day=(self.j.vault/'Playthroughs/Run-001/Days/Day-01-Attempt-01.md').read_text(encoding='utf-8')
        self.assertIn('The scene stayed with me',day)
        self.assertIn('관심·취향·스토리 감상',day)
        b=self.begin(1,'return_to_day_one','second player')
        self.assertEqual(b['starting_memory'],[old])
        f=self.j.record('observation_offered',{'text':'different scene'})['event_id']
        self.j.finish(b['id'],'completed')
        self.j.review(b['id'],'second player','My impression differs',[f], experiences=[
            {'kind':'preference','text':'I now prefer the quieter scenes','evidence_ids':[f],
             'remember':True,'supersedes':old['id']}])
        memory=self.j.memory()['entries']
        self.assertTrue(memory[0]['superseded']); self.assertEqual(memory[0]['author'],'first player')
        self.assertEqual(memory[1]['author'],'second player')

    def test_invalid_impression_rolls_back_entire_review(self):
        a=self.begin(); e=self.j.record('observation_offered',{'text':'fixture'})['event_id']
        self.j.finish(a['id'],'completed')
        good={'kind':'interest','text':'Curious','evidence_ids':[e],'remember':True}
        for bad in ({**good,'kind':'hidden_truth'}, {**good,'evidence_ids':['missing']},
                    {**good,'remember':'true'}, {**good,'supersedes':'missing'},
                    {**good,'remember':False,'supersedes':'missing'}):
            with self.assertRaises(ValueError):
                self.j.review(a['id'],'fixture','Invalid retrospective',[e],experiences=[good,bad])
            self.assertEqual(self.j.memory()['entries'],[])
        self.j.review(a['id'],'fixture','Nothing to add',[e],experiences=[])

    def test_review_template_is_portable(self):
        self.j.setup()
        template=self.j.vault/'Config/Day-Review-Template.md'
        template.parent.mkdir(parents=True,exist_ok=True); template.write_text('Optional impressions',encoding='utf-8')
        bundle=Path(self.j.export()['directory'])
        self.assertEqual((bundle/'Config/Day-Review-Template.md').read_text(encoding='utf-8'),'Optional impressions')

    def test_player_rules_are_versioned_and_exported_without_engineering_rules(self):
        (self.root/'AGENTS.md').write_text('Engineering-only secrets',encoding='utf-8')
        for name,relative in PLAYER_GUIDE_PATHS.items():
            path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('Player document: '+name,encoding='utf-8')
        a=self.begin()
        for name,relative in PLAYER_GUIDE_PATHS.items():
            self.assertEqual(a['config_versions'][name],hashlib.sha256((self.root/relative).read_bytes()).hexdigest())
        self.j.finish(a['id'],'interrupted')
        folder=Path(self.j.export()['directory'])
        self.assertEqual((folder/'Config/AGENTS.md').read_text(encoding='utf-8'),'Player document: AGENTS.md')
        self.assertFalse((folder/'AGENTS.md').exists())

    def test_offered_selection_only_is_recorded_in_live_hook(self):
        self.begin(); reader=LiveReader(self.root)
        snapshot={'schema_version':1,'environment':'lobotomy_live','read_only':True,
            'captured_at_utc':datetime.now(timezone.utc).isoformat(),'process_id':123,'sequence':1,
            'scene':'fixture','screen':{'width':1280,'height':720},'ui_texts':[
                {'text':v,'x':1,'y':1,'width':10,'height':10} for v in ('offered','not offered')],
            'isolation':{'company_name':'Robotomy_AI','product_name':'Lobotomy_Observer',
                         'persistent_data_path':'C:/fixture/Robotomy_AI/Lobotomy_Observer'}}
        reader.directory.mkdir(parents=True,exist_ok=True)
        reader.snapshot_path.write_text(json.dumps(snapshot),encoding='utf-8')
        response=reader.observe(max_items=1)
        event=self.j.event(response['experience_recording']['event_id'])
        self.assertEqual(event['data']['snapshot']['ui_texts'],response['snapshot']['ui_texts'])
        self.assertNotIn('not offered',json.dumps(event))
        self.assertFalse((self.root/'vault/Live').exists())


if __name__=='__main__': unittest.main()
