"""Acceptance boundaries for the read-only live UI bridge, using synthetic JSON only."""
from datetime import datetime, timedelta, timezone
import base64
import json
import os
from pathlib import Path
import tempfile
import unittest

from robotomy.live import LiveReader, MAX_SNAPSHOT_BYTES, MAX_FRAME_BYTES


class LiveReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = datetime(2026, 10, 17, 0, 0, tzinfo=timezone.utc)
        self.reader = LiveReader(self.root, clock=lambda: self.now)
        self.obj = {
            "schema_version": 1, "environment": "lobotomy_live", "read_only": True,
            "captured_at_utc": self.now.isoformat(), "process_id": 123, "sequence": 7,
            "scene": "MainMenu", "screen": {"width": 1280, "height": 720},
            "isolation": {"company_name": "Robotomy_AI", "product_name": "Lobotomy_Observer",
                          "persistent_data_path": "C:/test/Robotomy_AI/Lobotomy_Observer"},
            "ui_texts": [{"text": "테스트 메뉴", "x": 10, "y": 20, "width": 200, "height": 30}],
        }

    def publish(self):
        self.reader.directory.mkdir(parents=True, exist_ok=True)
        self.reader.snapshot_path.write_text(json.dumps(self.obj, ensure_ascii=False), encoding="utf-8")

    def assert_unrecorded(self):
        self.assertFalse((self.reader.directory / "observations.jsonl").exists())
        self.assertFalse((self.root / "vault").exists())

    def publish_frame(self, age=0, data=None):
        data = data if data is not None else base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aC1sAAAAASUVORK5CYII=")
        self.reader.directory.mkdir(parents=True, exist_ok=True)
        path = self.reader.directory / "frame.png"
        path.write_bytes(data)
        timestamp = self.now.timestamp() - age
        os.utime(path, (timestamp, timestamp))
        return data

    def test_frame_requires_valid_live_identity(self):
        self.publish_frame()
        status, frame = self.reader.frame()
        self.assertEqual(status["status"], "never_connected")
        self.assertIsNone(frame)
        self.obj["isolation"]["company_name"] = "Project_Moon"
        self.publish()
        status, frame = self.reader.frame()
        self.assertEqual(status["status"], "invalid")
        self.assertIsNone(frame)
        self.assert_unrecorded()

    def test_fresh_png_is_returned_without_record_writes(self):
        self.publish()
        expected = self.publish_frame(age=2)
        status, frame = self.reader.frame()
        self.assertEqual(status["status"], "live")
        self.assertEqual(frame, expected)
        self.assertEqual(status["frame_age_seconds"], 2)
        self.assert_unrecorded()

    def test_missing_stale_and_future_frames_fail_closed(self):
        self.publish()
        status, frame = self.reader.frame()
        self.assertEqual(status["reason"], "frame_missing")
        self.assertIsNone(frame)
        for age, expected in ((11, "frame_stale"), (-6, "frame_from_future")):
            self.publish_frame(age=age)
            status, frame = self.reader.frame()
            self.assertEqual(status["reason"], expected)
            self.assertIsNone(frame)
        self.assert_unrecorded()

    def test_fresh_frame_cannot_bypass_stale_snapshot(self):
        self.obj["captured_at_utc"] = (self.now - timedelta(seconds=11)).isoformat()
        self.publish()
        self.publish_frame()
        status, frame = self.reader.frame()
        self.assertEqual(status["status"], "stale")
        self.assertIsNone(frame)

    def test_oversize_and_malformed_frames_reject(self):
        self.publish()
        for data, reason in ((b"x" * (MAX_FRAME_BYTES + 1), "frame_too_large"),
                             (b"not a PNG", "frame_invalid_png_header"),
                             (b"\x89PNG\r\n\x1a\n" + b"\0" * 30, "frame_invalid_png_header")):
            self.publish_frame(data=data)
            status, frame = self.reader.frame()
            self.assertEqual(status["reason"], reason)
            self.assertIsNone(frame)
        self.assert_unrecorded()

    def test_never_connected_is_read_only(self):
        self.assertEqual(self.reader.status()["status"], "never_connected")
        self.assertEqual(self.reader.observe()["status"], "never_connected")
        self.assertFalse(self.reader.directory.exists())

    def test_live_status_does_not_record(self):
        self.publish()
        result = self.reader.status()
        self.assertEqual(result["status"], "live")
        self.assertEqual(result["source"], "actual_game_ui")
        self.assertEqual(result["ui_text_count"], 1)
        self.assert_unrecorded()

    def test_stale_and_future_reject_without_exposing_ui(self):
        for seconds, expected in ((-11, "stale"), (6, "invalid")):
            with self.subTest(seconds=seconds):
                self.obj["captured_at_utc"] = (self.now + timedelta(seconds=seconds)).isoformat()
                self.publish()
                result = self.reader.observe()
                self.assertEqual(result["status"], expected)
                self.assertNotIn("snapshot", result)
                self.assert_unrecorded()

    def test_identity_rejected(self):
        for mutate in (
            lambda obj: obj.update(environment="synthetic_fixture"),
            lambda obj: obj.update(read_only=False),
            lambda obj: obj["isolation"].update(company_name="Project_Moon"),
            lambda obj: obj["isolation"].update(product_name="Lobotomy"),
            lambda obj: obj["isolation"].update(persistent_data_path="C:/save/Project_Moon/Lobotomy"),
            lambda obj: obj["isolation"].update(persistent_data_path="C:/../Robotomy_AI/Lobotomy_Observer"),
            lambda obj: obj["isolation"].update(persistent_data_path="relative/Robotomy_AI/Lobotomy_Observer"),
        ):
            original = json.loads(json.dumps(self.obj))
            mutate(self.obj)
            self.publish()
            self.assertEqual(self.reader.observe()["status"], "invalid")
            self.assert_unrecorded()
            self.obj = original

    def test_malformed_and_oversized_reject(self):
        self.reader.directory.mkdir(parents=True)
        for data in (b"{", b"[]", b"null", b"\xff", b" " * (MAX_SNAPSHOT_BYTES + 1)):
            self.reader.snapshot_path.write_bytes(data)
            self.assertEqual(self.reader.observe()["status"], "invalid")
            self.assert_unrecorded()

    def test_duplicate_keys_reject(self):
        self.publish()
        raw = self.reader.snapshot_path.read_text(encoding="utf-8")
        self.reader.snapshot_path.write_text(raw[:-1] + ', "read_only": true}', encoding="utf-8")
        self.assertEqual(self.reader.status()["status"], "invalid")

    def test_unpaired_json_surrogate_rejects(self):
        self.publish()
        raw = self.reader.snapshot_path.read_text(encoding="utf-8")
        self.reader.snapshot_path.write_text(raw.replace("테스트 메뉴", r"\ud800"), encoding="utf-8")
        self.assertEqual(self.reader.observe()["status"], "invalid")
        self.assert_unrecorded()

    def test_contract_rejects_bool_ids_naive_time_and_nonfinite_coordinates(self):
        for mutate in (
            lambda obj: obj.update(process_id=True),
            lambda obj: obj.update(sequence=-1),
            lambda obj: obj.update(schema_version=True),
            lambda obj: obj.update(captured_at_utc="2026-10-17T00:00:00"),
            lambda obj: obj["ui_texts"][0].update(x=float("nan")),
            lambda obj: obj["ui_texts"][0].update(height=-1),
            lambda obj: obj["screen"].update(width=0),
        ):
            original = json.loads(json.dumps(self.obj))
            mutate(self.obj)
            self.publish()
            self.assertEqual(self.reader.status()["status"], "invalid")
            self.obj = original

    def test_append_only_events_defer_markdown_until_day_review(self):
        self.obj["ui_texts"][0]["text"] = "```\n<script>untrusted text</script>"
        self.obj["hidden_game_data"] = {"secret": "must not be returned or recorded"}
        self.publish()
        first = self.reader.observe()
        log = self.reader.directory / "observations.jsonl"
        original = log.read_bytes()
        second = self.reader.observe()
        self.assertNotEqual(first["observation_id"], second["observation_id"])
        self.assertTrue(log.read_bytes().startswith(original))
        records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["snapshot"]["ui_texts"], self.obj["ui_texts"])
        self.assertEqual(records[0]["source"], "actual_game_ui")
        self.assertNotIn("hidden_game_data", records[0]["snapshot"])
        self.assertEqual(set(path.name for path in self.root.iterdir()), {".robotomy"})
        self.assertFalse((self.root / "vault").exists())
        self.assertNotIn("checkpoint_path", first)

    def test_bounded_response_records_only_offered_selection(self):
        self.obj["ui_texts"] *= 3
        self.publish()
        result = self.reader.observe(max_items=1)
        self.assertEqual(len(result["snapshot"]["ui_texts"]), 1)
        self.assertEqual(result["ui_text_count"], 3)
        self.assertTrue(result["truncated"])
        record = json.loads((self.reader.directory / "observations.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(len(record["snapshot"]["ui_texts"]), 1)
        for invalid in (0, 101, True):
            with self.assertRaises(ValueError):
                self.reader.observe(invalid)


if __name__ == "__main__":
    unittest.main()
