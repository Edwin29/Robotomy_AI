import argparse
import json
from pathlib import Path
import sys
import time

from .store import Store


def output(value):
    print(json.dumps(value, ensure_ascii=False, indent=2), flush=True)


def doctor(game_path):
    path = Path(game_path)
    managed = path / "LobotomyCorp_Data" / "Managed"
    names = ["Assembly-CSharp.dll", "0Harmony.dll", "LobotomyBaseModLib.dll"]
    return {"game_path": str(path), "exe_present": (path / "LobotomyCorp.exe").is_file(),
            "managed_files": {name: (managed / name).is_file() for name in names},
            "live_adapter": "READ_ONLY_EXPORTER_AVAILABLE", "game_started_by_this_probe": False, "game_files_modified_by_this_probe": False,
            "scope": "File existence only. Does not prove runtime compatibility or a working mod loader."}


def demo(store):
    """Scripted plumbing test; no model inference and no actual game."""
    run = store.start("scripted-fixture-demo", max_actions=2)
    sid = run["id"]
    obs = store.observe(sid)
    decision = store.decide(sid, obs["observation_id"], "work", "연결 검증",
                            "모의 작업의 결과를 관찰한다.", "상태 변화가 있을 것이다.", "실제 게임 규칙과 무관하다.")
    result = store.execute(sid, decision["id"])
    reflection = store.reflect(sid, result["id"], "모의 작업 후 체력이 감소했다.",
                                "로보토미의 규칙으로 일반화할 수 없다.", "다음에는 모의 휴식을 관찰한다.")
    message = store.message(sid, "왜 다음 행동을 바꿨어?")
    store.reply(sid, message["id"], "기록된 체력 감소를 보고 휴식 결과를 비교하려고 한다.", [result["id"], reflection["id"]])
    obs = store.observe(sid)
    decision = store.decide(sid, obs["observation_id"], "rest", "휴식 결과 비교",
                            "앞선 모의 작업에서 체력이 줄었다.", "회복 여부를 관찰한다.",
                            "실제 게임에 대한 가설이 아니다.", [reflection["id"]])
    store.execute(sid, decision["id"])
    return {"session_id": sid, "scripted_not_llm": True, **store.export(sid)}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Robotomy AI — read-only live observation and synthetic control fixture")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("mcp", help="Serve MCP over stdio")
    sub.add_parser("demo", help="Run a scripted synthetic integration example; no model calls")
    sub.add_parser("sessions")
    sub.add_parser("live-status", help="Check actual game observer freshness")
    sub.add_parser("live-observe", help="Record actual UI observation and Obsidian note")
    sub.add_parser("live-pause", help="Operator stop: refuse new actual UI inputs")
    sub.add_parser("live-resume", help="Operator resume; old decisions remain invalid")
    sub.add_parser("live-timeline", help="Read actual UI decision/input/outcome records")
    sub.add_parser("live-capture", help="Capture native input coordinates and a game frame; no input")
    sub.add_parser("live-action", help="Record and execute one bounded native UI action from JSON on stdin")
    sub.add_parser("live-execute-pending", help="Consume at most one queued native input without Codex")
    sub.add_parser("live-outcome", help="Record an input outcome from JSON on stdin")
    probe = sub.add_parser("doctor")
    probe.add_argument("--game", default=r"D:\SteamLibrary\steamapps\common\LobotomyCorp")
    watch = sub.add_parser("watch")
    watch.add_argument("session_id")
    watch.add_argument("--follow", action="store_true")
    msg = sub.add_parser("message")
    msg.add_argument("session_id")
    msg.add_argument("text")
    msg.add_argument("--kind", choices=["question", "steer"], default="question")
    for command in ["pause", "resume", "end", "checkpoint"]:
        sub.add_parser(command).add_argument("session_id")
    sub.add_parser("import").add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        if args.command in {"live-capture", "live-execute-pending"}:
            from .virtual_input import VirtualExecutor
            native = VirtualExecutor(args.root)
            output(native.capture() if args.command == "live-capture" else native.execute_one())
            return
        if args.command in {"live-pause", "live-resume", "live-timeline", "live-action", "live-outcome"}:
            from .live_control import LiveControl
            control = LiveControl(args.root)
            if args.command == "live-pause": output(control.pause())
            elif args.command == "live-resume": output(control.resume())
            elif args.command == "live-timeline": output(control.timeline())
            elif args.command == "live-outcome": output(control.outcome(**json.load(sys.stdin)))
            else:
                from .virtual_input import VirtualExecutor
                decision = control.prepare(**json.load(sys.stdin))
                output({"decision": decision, "execution": VirtualExecutor(args.root).execute(decision['id'])})
            return
        if args.command in {"live-status", "live-observe"}:
            from .live import LiveReader
            reader = LiveReader(args.root)
            output(reader.status() if args.command == "live-status" else reader.observe())
            return
        if args.command == "doctor":
            output(doctor(args.game))
            return
        if args.command == "mcp":
            from .mcp_server import create_server
            create_server(args.root).run(transport="stdio")
            return
        store = Store(args.root)
        if args.command == "demo":
            output(demo(store))
        elif args.command == "sessions":
            output(store.sessions())
        elif args.command == "message":
            output(store.message(args.session_id, args.text, args.kind))
        elif args.command in {"pause", "resume", "end"}:
            output(store.control(args.session_id, {"pause": "paused", "resume": "running", "end": "ended"}[args.command]))
        elif args.command == "checkpoint":
            output(store.export(args.session_id))
        elif args.command == "import":
            output(store.import_bundle(args.path))
        elif args.command == "watch":
            cursor = 0
            while True:
                events = store.timeline(args.session_id, cursor)
                for event in events:
                    output(event)
                    cursor = event["seq"]
                if len(events) == 100:
                    continue
                if not args.follow:
                    break
                time.sleep(0.5)
    except (ValueError, OSError, KeyError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
