"""Device transport boundaries. Render visibility is additionally tested in Unity."""
from datetime import timedelta
import hashlib
import json
import unittest
from unittest.mock import patch
from pathlib import Path

import test_live


class ConsoleContractTests(unittest.TestCase):
    publish = test_live.LiveReaderTests.publish
    publish_frame = test_live.LiveReaderTests.publish_frame
    assert_unrecorded = test_live.LiveReaderTests.assert_unrecorded

    def setUp(self):
        test_live.LiveReaderTests.setUp(self)
        self.obj["console"] = {
            "version": 1, "session": "a" * 32, "unity_frame": 12,
            "policy": "conservative_display_v1", "valid_for_ms": 750,
            "audio_basis": "playback_state_approximation", "audio_dropped": 0,
            "gauges": [{"role": "energy", "x": 1, "y": 1, "width": 100, "height": 10,
                        "filled_pixels": 42, "total_pixels": 100}],
            "audio_events": [{"event_id": 1, "at_utc": self.now.isoformat(), "kind": "start",
                              "source_token": "b"*32, "sound_token": "c"*32}],
        }

    def test_subsecond_expiry_retracts_all_structured_data(self):
        self.publish()
        self.now += timedelta(milliseconds=751)
        result = self.reader.observe()
        self.assertEqual(result["status"], "stale")
        self.assertNotIn("snapshot", result)
        self.assert_unrecorded()

    def test_audio_backlog_is_offered_once_without_diagnostics(self):
        self.publish()
        path=self.reader.directory/('audio-'+self.obj['console']['session']+'.jsonl')
        event=self.obj['console']['audio_events'][0]
        path.write_text(json.dumps(dict(event,sound_id='first_trumpet'))+'\n',encoding='utf-8')
        first=self.reader.observe()
        self.assertEqual(first['audio_delivery']['events'][0]['label'],'퍼스트 트럼펫')
        self.assertNotIn('audio_basis',first['snapshot']['console'])
        self.assertNotIn('producer_dropped',first['audio_delivery'])
        self.assertEqual(self.reader.observe()['audio_delivery']['events'],[])

    def test_action_audio_and_observe_share_cursor(self):
        self.publish()
        path=self.reader.directory/('audio-'+self.obj['console']['session']+'.jsonl')
        event=dict(self.obj['console']['audio_events'][0],sound_id='first_trumpet')
        path.write_text(json.dumps(event)+'\n',encoding='utf-8')
        self.assertEqual(len(self.reader.offer_audio(self.obj)['events']),1)
        offered=self.reader.observe()
        self.assertEqual(offered['audio_delivery']['events'],[])
        self.assertNotIn('audio_events',offered['snapshot']['console'])

    def test_visible_map_changes_do_not_repeat_known_geometry(self):
        self.obj['console']['facility_map']={'known':{'version':1,'landmarks':[{'id':'corridor:1:2','kind':'corridor','x':1,'y':2}]},'visible':[{'id':'corridor:1:2','kind':'corridor','position':{'x':10,'y':20},'click':{'x':12,'y':20,'button':'right'}}]}
        self.publish()
        first=self.reader.observe(compact=True)
        self.assertIn('facility_map_known',first['snapshot'])
        self.obj['console']['facility_map']['visible'][0]['click']['x']=30
        self.obj['sequence']+=1
        self.publish()
        second=self.reader.observe(compact=True)
        changes=second['change_summary']['replacements']
        self.assertIn('/facility_map',changes)
        self.assertNotIn('/facility_map_known',changes)

    def test_transient_missing_snapshot_retries_only_read(self):
        self.publish()
        original_open = Path.open
        calls = []
        def transient(path, *args, **kwargs):
            calls.append(path)
            if len(calls) == 1:
                raise FileNotFoundError('replacement in progress')
            return original_open(path, *args, **kwargs)
        with patch.object(Path, 'open', transient):
            self.assertEqual(self.reader.status()['status'], 'live')
        self.assertEqual(len(calls), 2)
        self.assert_unrecorded()

    def test_persistent_missing_snapshot_still_rejects(self):
        with patch.object(Path, 'open', side_effect=FileNotFoundError) as opened:
            self.assertEqual(self.reader.observe()['status'], 'never_connected')
        self.assertEqual(opened.call_count, 4)
        self.assert_unrecorded()

    def test_engine_fields_and_sound_names_never_enter_record(self):
        self.obj["console"]["hidden_timer"] = 123
        self.obj["console"]["audio_events"][0]["clip_name"] = "hidden_asset_name"
        self.publish()
        result = self.reader.observe()
        payload = json.dumps(result)
        self.assertNotIn("hidden_asset_name", payload)
        self.assertNotIn("hidden_timer", payload)
        saved = (self.reader.directory / "observations.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("hidden_asset_name", saved)

    def test_semantic_tokens_and_out_of_range_bars_reject(self):
        original = json.loads(json.dumps(self.obj))
        for mutate in (
            lambda c: c["audio_events"][0].update(sound_token="secret-monster"),
            lambda c: c["gauges"][0].update(filled_pixels=101),
            lambda c: c.update(valid_for_ms=10000),
            lambda c: c["audio_events"].append(dict(c["audio_events"][0])),
            lambda c: c.update(policy="unfiltered"),
        ):
            self.obj = json.loads(json.dumps(original))
            mutate(self.obj["console"])
            self.publish()
            self.assertEqual(self.reader.observe()["status"], "invalid")
            self.assert_unrecorded()

    def test_frame_requires_matching_session_scene_hash_and_dimensions(self):
        self.obj["screen"] = {"width": 1, "height": 1}
        self.publish()
        data = self.publish_frame()
        meta = {"session": "a"*32, "process_id": 123, "scene": self.obj["scene"],
                "unity_frame": 11, "captured_at_utc": self.now.isoformat(),
                "sha256": hashlib.sha256(data).hexdigest()}
        path = self.reader.directory / "frame-meta.json"
        path.write_text(json.dumps(meta), encoding="utf-8")
        status, frame = self.reader.frame()
        self.assertEqual(frame, data)
        self.assertEqual(status["frame_unity_frame"], 11)
        for key, invalid in (("session", "d"*32), ("scene", "Other"), ("sha256", "0"*64), ("process_id", 124)):
            path.write_text(json.dumps({**meta, key: invalid}), encoding="utf-8")
            status, frame = self.reader.frame()
            self.assertIsNone(frame)
            self.assertEqual(status["reason"], "frame_generation_mismatch")

    def test_unchanged_png_requires_fresh_verified_pixel_check(self):
        self.obj["screen"] = {"width": 1, "height": 1}
        self.publish()
        data = self.publish_frame(age=60)
        meta = {"session":"a"*32, "process_id":123, "scene":self.obj["scene"],
                "unity_frame":11, "captured_at_utc":self.now.isoformat(),
                "sha256":hashlib.sha256(data).hexdigest()}
        path = self.reader.directory / "frame-meta.json"
        path.write_text(json.dumps(meta), encoding="utf-8")
        self.assertEqual(self.reader.frame()[1], data)
        meta["captured_at_utc"] = (self.now-timedelta(seconds=60)).isoformat()
        path.write_text(json.dumps(meta), encoding="utf-8")
        status, frame = self.reader.frame()
        self.assertIsNone(frame)
        self.assertEqual(status["reason"], "frame_stale")

    def add_motion(self):
        self.obj['console']['motion'] = {
            'version': 1, 'basis': 'display_projection_v1', 'coordinates': 'top_left_pixels',
            'units': 'pixels_per_real_second', 'status': 'available',
            'tracks': [{'track_id': 'd'*32, 'state': 'tracking', 'position': {'x': 100, 'y': 200},
                        'bounds': {'x': 90, 'y': 170, 'width': 20, 'height': 30}, 'interval_ms': 100,
                        'screen_velocity': {'x': 40, 'y': 5}, 'object_velocity': {'x': 50, 'y': 5},
                        'camera_velocity': {'x': -10, 'y': 0}}]}
        return self.obj['console']['motion']

    def test_motion_expiry_does_not_require_ui_expiry(self):
        self.add_motion()
        self.publish()
        self.assertEqual(len(self.reader._read()[1]['console']['motion']['tracks']), 1)
        self.now += timedelta(milliseconds=251)
        status, value = self.reader._read()
        self.assertEqual(status['status'], 'live')
        self.assertEqual(value['console']['motion']['tracks'], [])
        self.assertEqual(value['console']['motion']['status'], 'expired')

    def test_motion_allowlist_removes_engine_identity(self):
        motion = self.add_motion()
        motion['tracks'][0].update(internal_name='secret', world_position=[1, 2], destination='hidden')
        self.publish()
        value = json.dumps(self.reader.observe())
        for word in ('secret', 'world_position', 'destination'):
            self.assertNotIn(word, value)

    def test_motion_invalid_geometry_and_unknown_velocity_rejected(self):
        mutations = [
            lambda m: m.update(status='withheld'),
            lambda m: m['tracks'].append(dict(m['tracks'][0])),
            lambda m: m['tracks'][0].update(state='acquiring'),
            lambda m: m['tracks'][0]['position'].update(x=-1),
            lambda m: m['tracks'][0]['bounds'].update(width=100000),
            lambda m: m['tracks'][0]['screen_velocity'].update(x=float('nan')),
            lambda m: m['tracks'][0]['camera_velocity'].update(x=100),
            lambda m: m['tracks'][0].update(interval_ms=301),
            lambda m: m['tracks'][0].update(track_id='secret-unit'),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                motion = self.add_motion()
                mutate(motion)
                self.publish()
                self.assertEqual(self.reader.status()['status'], 'invalid')

    def test_first_seen_and_discontinuity_have_null_velocity(self):
        for state in ('acquiring', 'discontinuity'):
            motion = self.add_motion()
            motion['tracks'][0].update(state=state, screen_velocity=None, object_velocity=None, camera_velocity=None)
            self.publish()
            self.assertEqual(self.reader._read()[1]['console']['motion']['tracks'][0]['screen_velocity'], None)

    def test_compact_motion_records_only_offered_evidence(self):
        self.add_motion()
        self.publish()
        result = self.reader.observe(max_items=1, motion_only=True)
        self.assertEqual(len(result['snapshot']['motion']['tracks']), 1)
        self.assertNotIn('audio_events', json.dumps(result))
        saved = json.loads((self.reader.directory / 'observations.jsonl').read_text(encoding='utf-8'))
        self.assertNotIn('audio_events', json.dumps(saved))
        self.assertEqual(saved['snapshot'], result['snapshot'])

