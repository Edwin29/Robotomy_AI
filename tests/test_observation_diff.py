import json
from datetime import timedelta
from unittest.mock import patch
import test_live
import unittest


class DiffTests(unittest.TestCase):
    setUp=test_live.LiveReaderTests.setUp
    publish=test_live.LiveReaderTests.publish

    def test_compact_baseline_then_no_change_and_exact_logged_payload(self):
        self.publish()
        first=self.reader.observe(compact=True)
        self.assertEqual(first['payload_mode'],'full')
        self.obj['sequence']+=1;self.publish()
        second=self.reader.observe(compact=True)
        self.assertNotIn('snapshot',second)
        self.assertTrue(second['change_summary']['no_structured_changes'])
        self.assertEqual(second['change_summary']['base_observation_id'],first['observation_id'])
        events=[json.loads(x) for x in (self.reader.directory/'observations.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertNotIn('snapshot',events[-1])
        self.assertEqual(events[-1]['change_summary'],second['change_summary'])

    def test_visible_loss_never_replays_previous_text(self):
        self.obj['ui_texts'][0]['text']='old-private-to-current-view';self.publish()
        self.reader.observe(compact=True)
        self.obj['ui_texts']=[];self.publish()
        result=self.reader.observe(compact=True)
        self.assertEqual(result['change_summary']['replacements']['/ui_texts'],[])
        self.assertNotIn('old-private-to-current-view',json.dumps(result))

    def test_scene_selection_stale_and_new_reader_reset(self):
        self.publish();self.reader.observe(compact=True)
        self.obj['scene']='Another';self.publish()
        self.assertEqual(self.reader.observe(compact=True)['change_summary']['mode'],'reset')
        self.assertEqual(self.reader.observe(1,compact=True)['change_summary']['reset_reason'],'selection_changed')
        self.now+=timedelta(seconds=60)
        self.assertEqual(self.reader.observe(compact=True)['status'],'stale')
        self.obj['captured_at_utc']=self.now.isoformat();self.publish()
        self.assertEqual(self.reader.observe(compact=True)['payload_mode'],'full')

    def test_failed_append_does_not_advance_base(self):
        self.publish();first=self.reader.observe(compact=True)
        self.obj['ui_texts'][0]['text']='new';self.publish()
        with patch('robotomy.live.os.write',side_effect=OSError('fixture')):
            with self.assertRaises(OSError):self.reader.observe(compact=True)
        result=self.reader.observe(compact=True)
        self.assertEqual(result['change_summary']['base_observation_id'],first['observation_id'])

    def test_default_full_and_read_only_queries_do_not_advance_base(self):
        self.publish();a=self.reader.observe()
        self.reader.status();self.reader._read()
        b=self.reader.observe()
        self.assertIn('snapshot',b)
        self.assertEqual(b['change_summary']['base_observation_id'],a['observation_id'])
