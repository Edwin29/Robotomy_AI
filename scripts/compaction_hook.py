"""Synchronous Codex hook. Never resumes, starts, closes, or saves the game."""
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
PLAYER = Path(r"D:\Projects\Robotomy_Player")
sys.path.insert(0, str(ROOT))


def handle(event, root=ROOT, player=PLAYER, pause=None):
    if Path(event.get("cwd", "")).resolve() != player.resolve():
        return {"continue": True}
    name = event.get("hook_event_name")
    if name == "PostCompact":
        return {"continue": True, "systemMessage":
                "Robotomy: 압축 후 자동 재개하지 않습니다. 최신 관찰과 미완료 입력, "
                "정지 예약을 확인하고 플레이어가 재개하세요."}
    if name != "PreCompact":
        return {"continue": True}
    try:
        result = (pause or pause_game)(root)
    except Exception as exc:
        result = {"status": "failed", "reason": str(exc)}
    from robotomy.live_control import atomic
    atomic(root / ".robotomy/live/compaction-last.json",
           {"session_id": event.get("session_id"), "trigger": event.get("trigger"),
            "result": result, "automatic_resume": False})
    ok = result["status"] in ("paused", "already_paused", "stopped", "non_operating_scene")
    message = ("Robotomy: 압축 전 안전 상태 확인. 자동 재개하지 않습니다."
               if ok else "Robotomy: 게임 정지를 확인하지 못해 압축을 중단합니다. "
               "게임 상태를 확인하세요. " + str(result))
    return {"continue": ok, "systemMessage": message, **({} if ok else {"stopReason": message})}


def pause_game(root):
    from robotomy.game_power import GamePower
    from robotomy.live import LiveReader
    from robotomy.quick_input import QuickInput
    from robotomy.realtime import Realtime, context
    from robotomy.live_control import atomic
    if GamePower(root).status()["status"] == "stopped":
        return {"status": "stopped"}
    reader = LiveReader(root)
    status, snapshot = reader._read()
    if snapshot is None or status.get("status") != "live":
        return {"status": "observation_unavailable"}
    # These scenes are outside facility operation; don't infer safety from missing UI.
    if snapshot["scene"] in ("Intro", "NewTitleScene"):
        return {"status": "non_operating_scene"}
    realtime = Realtime(root, reader, QuickInput(root, reader))
    # Supersede pending sequences before waiting for the cross-process input lock.
    realtime.pending.parent.mkdir(parents=True, exist_ok=True)
    realtime.pending.write_text("compaction", encoding="utf-8")
    realtime.barrier.write_text(uuid.uuid4().hex, encoding="ascii")
    atomic(root / ".robotomy/live/control/not-before.json", {"epoch": __import__("time").time()})
    return realtime.pause(context(snapshot))


if __name__ == "__main__":
    try:
        output = handle(json.load(sys.stdin))
    except Exception as exc:
        output = {"continue": False, "stopReason": "Robotomy compaction hook failed: " + str(exc)}
    print(json.dumps(output, ensure_ascii=False))
