import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("compaction_hook", Path(__file__).resolve().parents[1] / "scripts/compaction_hook.py")
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class CompactionHookTests(unittest.TestCase):
    def test_pause_results(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for state, allowed in [("paused", True), ("already_paused", True),
                                   ("stopped", True), ("not_confirmed", False),
                                   ("playback_unknown", False), ("context_unavailable", False)]:
                result = hook.handle({"cwd": str(root), "hook_event_name": "PreCompact"},
                                     root, root, lambda _: {"status": state})
                self.assertEqual(result["continue"], allowed)

    def test_post_and_other_workspace_never_send_input(self):
        def forbidden(_):
            self.fail("unexpected game input")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for cwd, event in [(root, "PostCompact"), (root / "other", "PreCompact")]:
                self.assertTrue(hook.handle({"cwd": str(cwd), "hook_event_name": event},
                                           root, root, forbidden)["continue"])

    def test_error_blocks_compaction(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def fail(_):
                raise RuntimeError("input busy")
            self.assertFalse(hook.handle({"cwd": str(root), "hook_event_name": "PreCompact"},
                                        root, root, fail)["continue"])
