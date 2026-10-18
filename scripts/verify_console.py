"""Bounded, read-only sampling of the live console; never launches or controls the game."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from robotomy.live import LiveReader


def distribution(values):
    ordered = sorted(values)
    if not ordered:
        return {"n": 0}
    return {"n": len(ordered), "p50": round(statistics.median(ordered), 3),
            "p95": round(ordered[min(len(ordered)-1, int(len(ordered)*.95))], 3),
            "max": round(ordered[-1], 3)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=20, choices=range(5, 61))
    parser.add_argument("--label", default="sample")
    args = parser.parse_args()
    if not args.label.replace("-", "").replace("_", "").isalnum():
        parser.error("label must be alphanumeric")
    reader = LiveReader(ROOT)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / ".robotomy/live/verification" / (stamp + "-" + args.label)
    out.mkdir(parents=True)
    snapshots, metrics, frames, failures, ages = {}, {}, {}, {}, []
    deadline = time.monotonic() + args.seconds
    while time.monotonic() < deadline:
        status, snapshot = reader._read()
        if snapshot is None or "console" not in snapshot:
            reason = status.get("reason", status["status"])
            failures[reason] = failures.get(reason, 0) + 1
        else:
            key = (snapshot["console"]["session"], snapshot["sequence"])
            snapshots[key] = snapshot
            ages.append(status["age_seconds"]*1000)
            frame_status, data = reader.frame()
            if data is not None:
                frame_id = frame_status["frame_unity_frame"]
                if frame_id not in frames:
                    name = f"frame-{snapshot['process_id']}-{frame_id}.png"
                    (out / name).write_bytes(data)
                    frames[frame_id] = {"file": name, **frame_status}
            else:
                reason = frame_status.get("reason", frame_status["status"])
                failures[reason] = failures.get(reason, 0) + 1
            try:
                value = json.loads((reader.directory / "console-diagnostics.json").read_text(encoding="utf-8-sig"))
                if value["session"] == snapshot["console"]["session"]:
                    metrics[(value["session"], value["unity_frame"])] = value
            except (OSError, ValueError):
                pass
        time.sleep(.05)
    samples = list(snapshots.values())
    costs = list(metrics.values())
    gaps = [(datetime.fromisoformat(b["captured_at_utc"].replace("Z", "+00:00")) -
             datetime.fromisoformat(a["captured_at_utc"].replace("Z", "+00:00"))).total_seconds()*1000
            for a, b in zip(samples, samples[1:]) if a["console"]["session"] == b["console"]["session"]]
    result = {"basis": "actual_runtime_passive_sample", "seconds": args.seconds,
              "scenes": sorted({s["scene"] for s in samples}), "snapshots": len(samples), "frames": len(frames),
              "ui_sample_gap_ms": distribution(gaps), "observed_snapshot_age_ms": distribution(ages),
              "component_ms": {k: distribution([m[k] for m in costs if k != "capture_ms" or m[k] > 0])
                               for k in ("ui_ms", "audio_ms", "publish_ms", "capture_ms")},
              "transient_or_rejected_reads": failures,
              "accepted_panels": {k: max((m["ui"].get("panels", {}).get(k, m["ui"].get(k, 0)) for m in costs), default=0)
                                  for k in ("energy", "agent", "creature", "command", "mission", "notice", "tooltip", "bullets", "gauges")},
              "boundary": "Sampling/producer costs, not stimulus-to-action latency or all-frame FPS; no model was called."}
    (out / "snapshots.jsonl").write_text("".join(json.dumps(s, ensure_ascii=False)+"\n" for s in samples), encoding="utf-8")
    (out / "metrics.jsonl").write_text("".join(json.dumps(s, ensure_ascii=False)+"\n" for s in costs), encoding="utf-8")
    (out / "frames.json").write_text(json.dumps(list(frames.values()), ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"directory": str(out), **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
