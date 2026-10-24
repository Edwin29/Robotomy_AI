"""Contract tests; simulated observations are not gameplay evidence."""
import copy
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from robotomy.perception import Delivery, compact_audio
from robotomy.realtime import Realtime
from robotomy.quick_input import QuickInput


def sample(sequence=1, signals=None):
    return dict(process_id=1, scene="Main", sequence=sequence,
                captured_at_utc="2026-10-20T00:00:00Z",
                screen=dict(width=100, height=100), ui_texts=[], buttons=[],
                console=dict(session="a"*32, signal_epoch=1,
                             signals=signals or [], dead_employees=[]))


class DeltaTests(unittest.TestCase):
    def test_keyed_patch_reconstructs_and_removes(self):
        delivery = Delivery()
        first = sample()
        first["console"]["hazards"] = {"gauge": {"filled": 2, "max": 4}}
        baseline = delivery.offer(first)
        second = copy.deepcopy(first)
        second["sequence"] = 2
        second["console"]["hazards"]["gauge"]["filled"] = 3
        second["console"]["hazards"]["room"] = "observed"
        delta = delivery.offer(second)
        state = copy.deepcopy(baseline["state"])
        for op in delta["priority_changes"] + delta["changes"]:
            path = op.get("set", op.get("remove"))
            cursor = state
            for key in path[:-1]:
                cursor = cursor[key]
            if "set" in op:
                cursor[path[-1]] = op["value"]
            else:
                del cursor[path[-1]]
        self.assertEqual(state, Delivery().offer(second)["state"])
        self.assertEqual(delta["base"], baseline["id"])
        second["sequence"] = 3
        second["console"]["hazards"] = {}
        removed = delivery.offer(second)
        self.assertTrue(all("remove" in x for x in removed["priority_changes"]))

    def test_same_sequence_empty_delta_and_stage_reset(self):
        d = Delivery()
        first = d.offer(sample())
        second = d.offer(sample())
        self.assertEqual(second["changes"], [])
        self.assertEqual(second["priority_changes"], [])
        self.assertEqual(first["id"], second["base"])
        s = sample(2)
        s["console"]["signal_epoch"] = 2
        self.assertEqual(d.offer(s)["mode"], "full")

    def test_internal_fields_never_projected(self):
        s = sample()
        s["secret"] = "not player information"
        s["console"]["hidden_target"] = "secret"
        self.assertNotIn("secret", str(Delivery().offer(s)))

    def test_audio_preserves_start_stop_start_order(self):
        events = [dict(kind=k, sound_id="first_trumpet", at_utc=str(i))
                  for i, k in enumerate(["start", "start", "stop", "start"])]
        result = compact_audio({"events": events})["events"]
        self.assertEqual([e["kind"] for e in result], ["start", "stop", "start"])
        self.assertEqual([e["count"] for e in result], [2, 1, 1])

    def test_internal_batch_receipt_does_not_advance_shared_baseline(self):
        with tempfile.TemporaryDirectory() as root:
            reader = Mock()
            quick = QuickInput(Path(root), reader, Mock())
            quick._defer_offer = True
            result = quick.offered({"status": "input_sent"}, sample(), "ready")
            reader.deliver.assert_not_called()
            reader.offer_audio.assert_not_called()
            self.assertNotIn("observation", result)

    def test_invalid_later_intent_never_sends_earlier_input(self):
        with tempfile.TemporaryDirectory() as root:
            quick = QuickInput(Path(root), Mock(), Mock())
            with self.assertRaises(ValueError):
                quick.intents([{"kind": "input", "command": ["K", "Space"]},
                               {"kind": "input", "command": ["K", []]}])
            quick.executor._snapshot.assert_not_called()


class ReservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.reader = Mock()
        self.reader._read.return_value = ({"status": "live"}, sample())
        self.runtime = Realtime(Path(self.temp.name), self.reader, Mock())
        self.runtime.start = Mock()  # Deliberately stepped fixture observations.
        self.runtime.pause = Mock(return_value={"status": "paused"})
        self.addCleanup(self.runtime.close)

    def emit(self, kind="meltdown_cycle", sequence=2, event_id=1):
        self.runtime.ingest(sample(sequence, [dict(
            id=event_id, kind=kind, at="2026-10-20T00:00:01Z", text="visible announcement")]))

    def test_not_armed_never_pauses(self):
        self.runtime.ingest(sample())
        self.emit()
        self.runtime.pause.assert_not_called()

    def test_gauge_event_fires_without_room_timers_only_once(self):
        r = self.runtime.arm("meltdown_cycle")
        self.emit()
        self.emit(sequence=3, event_id=2)
        self.runtime.pause.assert_called_once()
        self.assertEqual(self.runtime.reservations[r["id"]]["status"], "consumed")

    def test_existing_incident_not_reused_when_armed(self):
        old = sample(5, [dict(id=5, kind="meltdown_cycle",
                             at="2026-10-20T00:00:01Z", text="old")])
        self.reader._read.return_value = ({"status": "live"}, old)
        self.runtime.arm("meltdown_cycle")
        self.runtime.ingest({**old, "sequence": 6})
        self.runtime.pause.assert_not_called()

    def test_slots_are_operator_owned_and_cancel_releases(self):
        r = self.runtime.arm("meltdown_cycle")
        with self.assertRaises(ValueError):
            self.runtime.arm("employee_death")
        self.runtime.cancel(r["id"])
        self.runtime.arm("employee_death")

    def test_scene_or_stage_disarms(self):
        r = self.runtime.arm("meltdown_cycle")
        s = sample(3)
        s["console"]["signal_epoch"] = 2
        self.runtime.ingest(s)
        self.assertEqual(self.runtime.reservations[r["id"]]["status"], "context_changed")
        self.runtime.pause.assert_not_called()

    def test_death_is_roster_difference_not_repeated(self):
        self.runtime.arm("employee_death")
        s = sample(2)
        s["console"]["dead_employees"] = [dict(employee_id="3", name="Seen", state="dead")]
        self.runtime.ingest(s)
        self.runtime.ingest({**s, "sequence": 3})
        self.runtime.pause.assert_called_once()

    def test_wait_cancel_does_not_disarm(self):
        self.runtime.arm("meltdown_cycle")
        answer = []
        worker = threading.Thread(target=lambda: answer.append(self.runtime.wait(["employee_death"])))
        worker.start()
        time.sleep(.02)
        self.runtime.cancel_wait()
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(answer[0]["status"], "cancelled")
        self.assertEqual(self.runtime.status()["reservations"][0]["status"], "armed")

    def test_retained_events_retrievable_and_delivery_deduplicated(self):
        self.runtime.ingest(sample())
        self.emit()
        rows = self.runtime.wait(["meltdown_cycle"], 0, after=0)
        self.assertFalse(rows["timed_out"])
        self.assertTrue(self.runtime.offer()["events"])
        self.assertFalse(self.runtime.offer()["events"])

    def test_already_paused_never_sends_space(self):
        from robotomy.realtime import context
        s = sample()
        s["ui_texts"] = [dict(panel="playback", text="paused")]
        self.reader._read.return_value = ({"status": "live"}, s)
        self.assertEqual(Realtime.pause(self.runtime, context(s))["status"], "already_paused")
        self.runtime.quick.executor.capture.assert_not_called()
