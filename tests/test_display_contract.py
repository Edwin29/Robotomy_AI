"""Transport tests only: visibility and progression are enforced in Unity."""
import copy
import json
import unittest

import test_console
from robotomy.history import HistoryReader
from robotomy.live import validate_snapshot


PANELS = ("energy", "agent", "creature", "command", "mission", "notice", "tooltip", "bullets")


class DisplayContractTests(unittest.TestCase):
    def setUp(self):
        test_console.ConsoleContractTests.setUp(self)

    def texts(self):
        template = self.obj["ui_texts"][0]
        return [{**template, "panel": panel, "text": f"visible {panel}"} for panel in PANELS]

    def history_sample(self, snapshot):
        reader = HistoryReader(self.root)
        reader.directory.mkdir(parents=True, exist_ok=True)
        session = snapshot["console"]["session"]
        envelope = {"version": 1, "session": session, "sequence": snapshot["sequence"],
                    "snapshot": snapshot}
        index = {"version": 1, "session": session, "capacity": 1, "frame_capacity": 1,
                 "records": [{"sequence": snapshot["sequence"], "unity_frame": snapshot["console"]["unity_frame"],
                              "slot": 0, "has_frame": False, "frame_slot": None, "sha256": None}]}
        for name, value in (("sample-0.json", envelope), ("index.json", index)):
            (reader.directory / name).write_text(json.dumps(value), encoding="utf-8")
        return reader.read()

    def test_known_panels_survive_live_and_historical_validation(self):
        self.obj["ui_texts"] = self.texts()
        self.obj["buttons"] = [{**item, "interactable": True} for item in self.texts()]
        live, _ = validate_snapshot(self.obj)
        historical = self.history_sample(self.obj)
        self.assertEqual(historical["status"], "available")
        for snapshot in (live, historical["records"][0]["snapshot"]):
            self.assertEqual([item["panel"] for item in snapshot["ui_texts"]], list(PANELS))
            self.assertEqual([item["panel"] for item in snapshot["buttons"]], list(PANELS))

    def test_unknown_and_malformed_panel_sources_reject(self):
        for value in ("internal_debug_console", "kit_use_counter", "employee_model", "", None, ["agent"]):
            with self.subTest(panel=value):
                snapshot = copy.deepcopy(self.obj)
                snapshot["ui_texts"][0]["panel"] = value
                with self.assertRaises(ValueError):
                    validate_snapshot(snapshot)
                history = self.history_sample(snapshot)
                self.assertEqual(history["status"], "partial")
                self.assertEqual(history["records"], [])

    def test_model_fields_are_not_authorized_by_visible_panel_label(self):
        hidden = {"current_hp": 88, "current_sp": 77, "tool_use_count": 13,
                  "tool_use_time": 301, "research_unlocked": True,
                  "unrevealed_text": "HIDDEN_SENTINEL"}
        self.obj["ui_texts"] = [{**item, **hidden} for item in self.texts()]
        self.obj["buttons"] = [{**self.texts()[0], "interactable": True, **hidden}]
        self.obj["console"].update(hidden)
        self.obj["console"]["gauges"][0].update(hidden)
        self.obj.update(hidden)
        live, _ = validate_snapshot(self.obj)
        historical = self.history_sample(self.obj)["records"][0]["snapshot"]
        for snapshot in (live, historical):
            payload = json.dumps(snapshot)
            for key in hidden:
                self.assertNotIn(key, payload)
            self.assertNotIn("HIDDEN_SENTINEL", payload)
            self.assertEqual(snapshot["ui_texts"][0]["text"], "visible energy")

    def test_legacy_snapshot_without_panel_or_console_still_validates(self):
        self.obj.pop("console")
        value, _ = validate_snapshot(self.obj)
        self.assertEqual(value["ui_texts"], self.obj["ui_texts"])
        self.assertNotIn("console", value)
        self.assertNotIn("panel", value["ui_texts"][0])


if __name__ == "__main__":
    unittest.main()
