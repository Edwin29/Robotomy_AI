"""Synthetic publication fixtures; not evidence of game pause/render behavior."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from robotomy.history import HistoryReader, MAX_INDEX_BYTES


SESSION = "a" * 32
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aC1sAAAAASUVORK5CYII=")


class HistoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.reader = HistoryReader(self.root)
        self.directory = self.reader.directory
        self.directory.mkdir(parents=True)
        self.index = {"version": 1, "session": SESSION, "capacity": 3,
                      "frame_capacity": 2, "records": []}

    def write_json(self, name, value):
        (self.directory / name).write_text(json.dumps(value), encoding="utf-8")

    def publish_index(self):
        self.write_json("index.json", self.index)

    def append(self, sequence, slot, frame_slot=None):
        snapshot = {
            "schema_version": 1, "environment": "lobotomy_live", "read_only": True,
            "captured_at_utc": "2020-01-01T00:00:00Z", "process_id": 1,
            "sequence": sequence, "scene": "Tutorial_1", "screen": {"width": 1, "height": 1},
            "isolation": {"company_name": "Robotomy_AI", "product_name": "Lobotomy_Observer",
                          "persistent_data_path": "C:/test/Robotomy_AI/Lobotomy_Observer"},
            "hidden_agent_hp": 888, "ui_texts": [],
            "console": {"version": 1, "session": SESSION, "unity_frame": sequence * 2,
                        "policy": "conservative_display_v1", "valid_for_ms": 750,
                        "audio_basis": "playback_state_approximation", "audio_dropped": 0,
                        "audio_events": [], "gauges": [], "hidden_target": "spoiler",
                        "motion": {"version": 1, "basis": "display_projection_v1",
                                   "coordinates": "top_left_pixels", "units": "pixels_per_real_second",
                                   "status": "available", "tracks": []}}}
        envelope = {"version": 1, "session": SESSION, "sequence": sequence, "snapshot": snapshot}
        self.write_json(f"sample-{slot}.json", envelope)
        self.index["records"] = [r for r in self.index["records"] if r["slot"] != slot]
        if frame_slot is not None:
            (self.directory / f"frame-{frame_slot}.png").write_bytes(PNG)
            for record in self.index["records"]:
                if record["frame_slot"] == frame_slot:
                    record.update(has_frame=False, frame_slot=None, sha256=None)
        self.index["records"].append({"sequence": sequence, "unity_frame": sequence * 2,
                                      "slot": slot, "has_frame": frame_slot is not None,
                                      "frame_slot": frame_slot,
                                      "sha256": hashlib.sha256(PNG).hexdigest() if frame_slot is not None else None})
        self.publish_index()
        return envelope

    def test_old_history_keeps_original_time_and_filters_hidden_fields(self):
        self.append(1, 0)
        result = self.reader.read()
        self.assertEqual(result["status"], "available")
        record = result["records"][0]
        self.assertTrue(result["historical"])
        self.assertFalse(result["actionable"])
        self.assertFalse(record["actionable"])
        self.assertEqual(record["captured_at_utc"], "2020-01-01T00:00:00Z")
        self.assertNotIn("hidden_agent_hp", record["snapshot"])
        self.assertNotIn("hidden_target", record["snapshot"]["console"])
        self.assertEqual(record["snapshot"]["console"]["motion"]["status"], "available")
        self.assertFalse((self.directory.parent / "observations.jsonl").exists())
        self.assertFalse((self.root / "vault").exists())

    def test_ring_rollover_and_cursor_paging(self):
        for sequence in range(1, 6):
            self.append(sequence, (sequence - 1) % 3)
        result = self.reader.read(after_sequence=1, limit=2)
        self.assertEqual([r["sequence"] for r in result["records"]], [3, 4])
        self.assertEqual(result["retained_count"], 3)
        self.assertTrue(result["cursor_before_retained"])
        self.assertTrue(result["truncated"])
        self.assertEqual(result["next_after_sequence"], 4)
        self.assertEqual([r["sequence"] for r in self.reader.read(limit=2)["records"]], [4, 5])
        self.assertEqual([r["sequence"] for r in self.reader.read(after_sequence=4)["records"]], [5])

    def test_paused_publication_simulation_preserves_entries_without_ttl(self):
        self.append(1, 0)
        self.append(2, 1)
        before = (self.directory / "index.json").read_bytes()
        for _ in range(3):
            self.assertEqual(self.reader.read()["retained_count"], 2)
        self.assertEqual(before, (self.directory / "index.json").read_bytes())
        # Capture sequence can advance during pause while history does not.
        self.append(1000, 2)
        result = self.reader.read(after_sequence=2)
        self.assertEqual([r["sequence"] for r in result["records"]], [1000])
        self.assertEqual(result["gaps"], [])
        self.assertEqual(result["sequence_gaps"], [{"after": 2, "before": 1000}])

    def test_overwritten_slot_is_reported_not_substituted(self):
        old = self.append(1, 0)
        old["sequence"] = 2
        old["snapshot"]["sequence"] = 2
        self.write_json("sample-0.json", old)
        result = self.reader.read()
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["records"], [])
        self.assertEqual(result["gaps"][0]["sequence"], 1)

    def test_missing_and_torn_samples_fail_closed(self):
        self.append(1, 0)
        for content in ('{"version":', '{"version":1,"version":1}', '[]'):
            (self.directory / "sample-0.json").write_text(content)
            self.assertEqual(self.reader.read()["status"], "partial")
        (self.directory / "sample-0.json").unlink()
        self.assertEqual(self.reader.read()["records"], [])

    def test_identity_mismatch_rejected(self):
        original = self.append(1, 0)
        for key, value in (("session", "b" * 32), ("unity_frame", 999)):
            changed = copy.deepcopy(original)
            changed["snapshot"]["console"][key] = value
            self.write_json("sample-0.json", changed)
            self.assertEqual(self.reader.read()["records"], [])
        self.assertEqual(self.reader.read(session="b" * 32)["status"], "invalid")

    def test_restart_during_read_discards_mixed_generation(self):
        self.append(1, 0)
        original = self.reader._sample
        def restart(index, record):
            snapshot = original(index, record)
            self.index["session"] = "b" * 32
            self.publish_index()
            return snapshot
        self.reader._sample = restart
        result = self.reader.read()
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["records"], [])

    def test_historical_frame_and_overwrite_hash_validation(self):
        self.append(1, 0, 0)
        status, data = self.reader.frame(SESSION, 1)
        self.assertEqual(status["status"], "available")
        self.assertFalse(status["actionable"])
        self.assertEqual(data, PNG)
        (self.directory / "frame-0.png").write_bytes(PNG + b"newer frame")
        self.assertIsNone(self.reader.frame(SESSION, 1)[1])
        self.assertIsNone(self.reader.frame("b" * 32, 1)[1])
        self.assertEqual(self.reader.frame(SESSION, 2)[0]["status"], "unavailable")

    def test_frame_ring_rollover_drops_old_availability(self):
        self.append(1, 0, 0)
        self.append(2, 1, 1)
        self.append(3, 2, 0)
        self.assertEqual(self.reader.frame(SESSION, 1)[0]["status"], "unavailable")
        self.assertEqual(self.reader.frame(SESSION, 3)[1], PNG)
        self.assertEqual([r["has_frame"] for r in self.reader.read()["records"]], [False, True, True])

    def test_index_limits_duplicate_slots_and_invalid_inputs(self):
        self.append(1, 0)
        good = copy.deepcopy(self.index)
        for key, value in (("capacity", 601), ("frame_capacity", 61), ("capacity", True), ("version", True)):
            self.index = {**good, key: value}
            self.publish_index()
            self.assertEqual(self.reader.read()["status"], "invalid")
        self.index = good
        self.index["records"].append({**good["records"][0], "sequence": 2})
        self.publish_index()
        self.assertEqual(self.reader.read()["status"], "invalid")
        (self.directory / "index.json").write_bytes(b" " * (MAX_INDEX_BYTES + 1))
        self.assertEqual(self.reader.read()["status"], "invalid")
        for kwargs in ({"limit": 51}, {"limit": True}, {"after_sequence": -1}, {"session": "../x"}):
            with self.assertRaises(ValueError):
                self.reader.read(**kwargs)


if __name__ == "__main__":
    unittest.main()
