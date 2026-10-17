import json
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

from robotomy.store import Store


class PlayerRecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)
        self.run = self.store.start("test-model", max_actions=2)
        self.sid = self.run["id"]

    def decision(self, sid=None):
        sid = sid or self.sid
        obs = self.store.observe(sid)
        return self.store.decide(sid, obs["observation_id"], "work", "observe", "fixture choice",
                                 "a state change", "unknown")

    def test_duplicate_delivery_changes_world_once_even_concurrently(self):
        decision = self.decision()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.store.execute(self.sid, decision["id"]), range(2)))
        self.assertEqual(results[0]["id"], results[1]["id"])
        self.assertEqual(self.store.observe(self.sid)["scene"]["tick"], 1)
        events = self.store.timeline(self.sid)
        self.assertEqual(sum(e["kind"] == "outcome" for e in events), 1)
        self.assertLess(next(e["seq"] for e in events if e["kind"] == "decision"),
                        next(e["seq"] for e in events if e["kind"] == "outcome"))

    def test_steering_invalidates_pending_action(self):
        decision = self.decision()
        self.store.message(self.sid, "reconsider", "steer")
        with self.assertRaisesRegex(ValueError, "stale"):
            self.store.execute(self.sid, decision["id"])
        self.assertEqual(self.store.observe(self.sid)["scene"]["tick"], 0)

    def test_pause_blocks_action_but_keeps_dialogue_available(self):
        decision = self.decision()
        self.store.control(self.sid, "paused")
        msg = self.store.message(self.sid, "why?")
        self.store.reply(self.sid, msg["id"], "because of the recorded decision", [decision["id"]])
        with self.assertRaises(ValueError):
            self.store.execute(self.sid, decision["id"])
        self.store.control(self.sid, "running")
        with self.assertRaisesRegex(ValueError, "stale"):
            self.store.execute(self.sid, decision["id"])

    def test_cross_session_observation_and_references_rejected(self):
        other = self.store.start("other")["id"]
        obs = self.store.observe(other)
        with self.assertRaises(ValueError):
            self.store.decide(self.sid, obs["observation_id"], "rest", "g", "r", "e", "u")
        msg = self.store.message(self.sid, "why?")
        with self.assertRaises(ValueError):
            self.store.reply(self.sid, msg["id"], "invalid evidence", [obs["observation_id"]])

    def test_budget_is_enforced_and_survives_restart(self):
        for _ in range(2):
            decision = self.decision()
            self.store.execute(self.sid, decision["id"])
        restarted = Store(self.tmp.name)
        self.assertEqual(restarted.observe(self.sid)["status"], "budget_reached")
        with self.assertRaises(ValueError):
            self.decision()
        with self.assertRaises(ValueError):
            restarted.control(self.sid, "running")

    def test_live_mode_cannot_silently_fall_back_to_mock(self):
        with self.assertRaisesRegex(ValueError, "Live adapter unavailable"):
            self.store.start("model", mode="live")

    def test_portable_experience_on_fresh_store_and_tamper_detection(self):
        decision = self.decision()
        outcome = self.store.execute(self.sid, decision["id"])
        reflection = self.store.reflect(self.sid, outcome["id"], "체력 감소", "fixture only", "try rest")
        exported = self.store.export(self.sid)
        fresh = Store(Path(self.tmp.name) / "new-model")
        imported = fresh.import_bundle(exported["bundle_path"])
        sid = fresh.start("different-model", inherited_bundle_ids=[imported["bundle_id"]])["id"]
        results = fresh.memory_search(sid, "체력")
        self.assertEqual(results[0]["event"]["id"], reflection["id"])
        self.assertTrue(results[0]["origin"].startswith("inherited:"))
        self.assertFalse(results[0]["real_game"])
        # Another model without explicit inheritance sees none of that history.
        clean = fresh.start("unrelated")["id"]
        self.assertEqual(fresh.memory_search(clean, "체력"), [])
        path = Path(exported["bundle_path"])
        broken = json.loads(path.read_text(encoding="utf-8"))
        broken["payload"]["real_game"] = True
        path.write_text(json.dumps(broken), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "checksum"):
            fresh.import_bundle(path)

    def test_observation_has_no_hidden_simulation_parameters(self):
        observation = self.store.observe(self.sid)
        self.assertFalse(observation["scene"]["real_game"])
        self.assertNotIn("damage_per_work", observation["scene"])

    def test_second_generation_transfer_keeps_original_evidence_searchable(self):
        decision = self.decision()
        outcome = self.store.execute(self.sid, decision["id"])
        reflection = self.store.reflect(self.sid, outcome["id"], "original lesson", "tentative", "retry")
        first = self.store.export(self.sid)
        imported = self.store.import_bundle(first["bundle_path"])
        second = self.store.start("model-b", inherited_bundle_ids=[imported["bundle_id"]])["id"]
        second_export = self.store.export(second)
        fresh = Store(Path(self.tmp.name) / "model-c")
        transferred = fresh.import_bundle(second_export["bundle_path"])
        third = fresh.start("model-c", inherited_bundle_ids=[transferred["bundle_id"]])["id"]
        self.assertEqual(fresh.memory_search(third, "original lesson")[0]["event"]["id"], reflection["id"])
        obs = fresh.observe(third)
        fresh.decide(third, obs["observation_id"], "rest", "g", "r", "e", "u", [reflection["id"]])


if __name__ == "__main__":
    unittest.main()
