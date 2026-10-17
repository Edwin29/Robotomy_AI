"""Transactional local record of observations, decisions and their outcomes."""
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from . import mock
from . import __version__


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def require_text(value, name, maximum=8000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must contain 1..{maximum} characters")
    return value


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.data = self.root / ".robotomy"
        self.data.mkdir(parents=True, exist_ok=True)
        self.database = self.data / "state.sqlite3"
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT NOT NULL UNIQUE, session_id TEXT NOT NULL,
                    kind TEXT NOT NULL, created_at TEXT NOT NULL, data TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS session_events ON events(session_id, seq);
                CREATE TABLE IF NOT EXISTS imports (
                    id TEXT PRIMARY KEY, data TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _run(self, db, session_id):
        row = db.execute("SELECT data FROM sessions WHERE id=?", (session_id,)).fetchone()
        if row is None:
            raise ValueError("Unknown session")
        return json.loads(row[0])

    def _save(self, db, run):
        db.execute("UPDATE sessions SET data=? WHERE id=?", (encode(run), run["id"]))

    def _event(self, db, session_id, kind, data):
        event = {"id": uuid4().hex, "session_id": session_id, "kind": kind,
                 "created_at": timestamp(), "data": data}
        cursor = db.execute(
            "INSERT INTO events(id,session_id,kind,created_at,data) VALUES(?,?,?,?,?)",
            (event["id"], session_id, kind, event["created_at"], encode(data)))
        event["seq"] = cursor.lastrowid
        return event

    def _events(self, db, session_id):
        return [dict(row) | {"data": json.loads(row["data"])} for row in db.execute(
            "SELECT * FROM events WHERE session_id=? ORDER BY seq", (session_id,))]

    def start(self, player, mode="mock", max_actions=20, inherited_bundle_ids=None):
        require_text(player, "player", 200)
        if mode != "mock":
            raise ValueError("Live adapter unavailable. No game control is implemented in v0.1.")
        if type(max_actions) is not int or not 1 <= max_actions <= 1000:
            raise ValueError("max_actions must be 1..1000")
        inherited = list(dict.fromkeys(inherited_bundle_ids or []))
        with self.connect() as db:
            for bundle_id in inherited:
                if not db.execute("SELECT 1 FROM imports WHERE id=?", (bundle_id,)).fetchone():
                    raise ValueError("Import the selected bundle before starting")
            run = {"id": uuid4().hex, "player": player, "mode": mode,
                   "app_version": __version__, "adapter_version": "synthetic-fixture-v1",
                   "real_game": False, "created_at": timestamp(), "revision": 0,
                   "status": "running", "max_actions": max_actions, "actions": 0,
                   "state": mock.initial_state(), "inherited_bundle_ids": inherited}
            db.execute("INSERT INTO sessions VALUES(?,?)", (run["id"], encode(run)))
            self._event(db, run["id"], "session_started", {k: v for k, v in run.items() if k != "state"})
            return run

    def sessions(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT data FROM sessions ORDER BY rowid DESC")]

    def timeline(self, session_id, after_seq=0, limit=100):
        if not 1 <= limit <= 500:
            raise ValueError("limit must be 1..500")
        with self.connect() as db:
            self._run(db, session_id)
            rows = db.execute("SELECT * FROM events WHERE session_id=? AND seq>? ORDER BY seq LIMIT ?",
                              (session_id, after_seq, limit))
            return [dict(row) | {"data": json.loads(row["data"])} for row in rows]

    def observe(self, session_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            run = self._run(db, session_id)
            events = self._events(db, session_id)
            answered = {e["data"]["message_id"] for e in events if e["kind"] == "reply"}
            messages = [e for e in events if e["kind"] == "human_message" and e["id"] not in answered]
            observation = {"revision": run["revision"], "status": run["status"],
                           "remaining_actions": run["max_actions"] - run["actions"],
                           "scene": mock.observe(run["state"]), "messages": messages}
            event = self._event(db, session_id, "observation", observation)
            return {"observation_id": event["id"], **observation}

    def decide(self, session_id, observation_id, action, goal, rationale, expected_outcome,
               uncertainty, memory_refs=None):
        for name, value in {"goal": goal, "rationale": rationale, "expected_outcome": expected_outcome,
                            "uncertainty": uncertainty}.items():
            require_text(value, name)
        if action not in {"work", "rest", "wait"}:
            raise ValueError("Unsupported fixture action")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            run = self._run(db, session_id)
            self._action_allowed(run)
            events = self._events(db, session_id)
            observation = next((e for e in events if e["id"] == observation_id and e["kind"] == "observation"), None)
            if observation is None or observation["data"]["revision"] != run["revision"]:
                raise ValueError("A fresh observation from this session is required")
            consumed = {e["data"]["decision_id"] for e in events if e["kind"] == "outcome"}
            if any(e["kind"] == "decision" and e["id"] not in consumed and
                   e["data"]["revision"] == run["revision"] for e in events):
                raise ValueError("A decision is already pending for this revision")
            refs = memory_refs or []
            self._check_refs(db, run, refs)
            event = self._event(db, session_id, "decision", {
                "revision": run["revision"], "observation_id": observation_id, "action": action,
                "goal": goal, "rationale": rationale, "expected_outcome": expected_outcome,
                "uncertainty": uncertainty, "memory_refs": refs,
                "explanation_type": "declared_pre_action_rationale_not_internal_reasoning"})
            return event

    def _action_allowed(self, run):
        if run["status"] != "running":
            raise ValueError("Session is not running; operator must resume it")
        if run["actions"] >= run["max_actions"]:
            raise ValueError("Action budget reached; start a separately scoped experiment")

    def execute(self, session_id, decision_id):
        # Atomicity and retry handling here apply ONLY to the in-process fixture.
        # A future real-game adapter must reconcile durable command receipts.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            run = self._run(db, session_id)
            events = self._events(db, session_id)
            previous = next((e for e in events if e["kind"] == "outcome" and
                             e["data"]["decision_id"] == decision_id), None)
            if previous:
                return previous | {"replayed_receipt": True}
            self._action_allowed(run)
            decision = next((e for e in events if e["id"] == decision_id and e["kind"] == "decision"), None)
            if decision is None or decision["data"]["revision"] != run["revision"]:
                raise ValueError("Missing or stale decision; observe and decide again")
            before = run["state"]
            run["state"] = mock.step(before, decision["data"]["action"])
            run["revision"] += 1
            run["actions"] += 1
            if run["actions"] >= run["max_actions"]:
                run["status"] = "budget_reached"
            self._save(db, run)
            return self._event(db, session_id, "outcome", {
                "decision_id": decision_id, "action": decision["data"]["action"],
                "before": before, "after": run["state"], "revision": run["revision"],
                "status": run["status"], "real_game": False})

    def _check_refs(self, db, run, refs):
        allowed = {e["id"] for e in self._events(db, run["id"])}
        for _, bundle in self._inherited(db, run):
            allowed.update(e["id"] for e in bundle["payload"]["events"])
        if any(ref not in allowed for ref in refs):
            raise ValueError("Evidence reference is not in this session or its selected inherited bundles")

    def _inherited(self, db, run):
        pending = list(run["inherited_bundle_ids"])
        seen = set()
        while pending:
            bundle_id = pending.pop(0)
            if bundle_id in seen:
                continue
            seen.add(bundle_id)
            bundle = json.loads(db.execute("SELECT data FROM imports WHERE id=?", (bundle_id,)).fetchone()[0])
            yield bundle_id, bundle
            pending.extend(bundle["payload"]["session"]["inherited_bundle_ids"])

    def reflect(self, session_id, outcome_id, lesson, uncertainty, next_policy):
        for name, value in {"lesson": lesson, "uncertainty": uncertainty, "next_policy": next_policy}.items():
            require_text(value, name)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._run(db, session_id)
            if not any(e["id"] == outcome_id and e["kind"] == "outcome" for e in self._events(db, session_id)):
                raise ValueError("Reflection requires an actual outcome from this session")
            return self._event(db, session_id, "reflection", {
                "outcome_id": outcome_id, "lesson": lesson, "uncertainty": uncertainty,
                "next_policy": next_policy, "source": "player_interpretation_not_verified_fact"})

    def message(self, session_id, text, kind="question"):
        require_text(text, "text")
        if kind not in {"question", "steer"}:
            raise ValueError("kind must be question or steer")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            run = self._run(db, session_id)
            # A question does not silently interrupt a plan. Steering invalidates it.
            if kind == "steer":
                run["revision"] += 1
                self._save(db, run)
            return self._event(db, session_id, "human_message", {"text": text, "kind": kind})

    def reply(self, session_id, message_id, text, evidence_ids):
        require_text(text, "text")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            run = self._run(db, session_id)
            events = self._events(db, session_id)
            if not any(e["id"] == message_id and e["kind"] == "human_message" for e in events):
                raise ValueError("Unknown human message")
            if not evidence_ids:
                raise ValueError("Reply must reference at least one recorded event")
            self._check_refs(db, run, evidence_ids)
            return self._event(db, session_id, "reply", {
                "message_id": message_id, "text": text, "evidence_ids": evidence_ids})

    def control(self, session_id, status):
        if status not in {"paused", "running", "ended"}:
            raise ValueError("Invalid operator status")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            run = self._run(db, session_id)
            if run["status"] in {"ended", "budget_reached"}:
                raise ValueError("Session is already terminal")
            run["status"] = status
            run["revision"] += 1
            self._save(db, run)
            return self._event(db, session_id, "operator_control", {"status": status})

    def memory_search(self, session_id, query, limit=10):
        require_text(query, "query", 300)
        if not 1 <= limit <= 50:
            raise ValueError("limit must be 1..50")
        with self.connect() as db:
            run = self._run(db, session_id)
            sources = [("own_session", self._events(db, session_id))]
            for bundle_id, bundle in self._inherited(db, run):
                sources.append((f"inherited:{bundle_id}", bundle["payload"]["events"]))
            results = []
            for origin, events in sources:
                for event in events:
                    if event["kind"] in {"decision", "reflection", "reply"} and query.casefold() in encode(event["data"]).casefold():
                        results.append({"origin": origin, "real_game": False, "event": event})
            return results[-limit:]

    def export(self, session_id):
        # Consistent snapshot: exports may occur while another process is writing.
        with self.connect() as db:
            db.execute("BEGIN")
            run = self._run(db, session_id)
            events = self._events(db, session_id)
            inherited = [json.loads(db.execute("SELECT data FROM imports WHERE id=?", (bid,)).fetchone()[0])
                         for bid in run["inherited_bundle_ids"]]
        payload = {"schema_version": 1, "environment": "synthetic_fixture", "real_game": False,
                   "session": run, "events": events, "inherited_bundles": inherited}
        digest = sha256(encode(payload).encode("utf-8")).hexdigest()
        bundle = {"sha256": digest, "payload": payload}
        folder = self.root / "exports" / session_id
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{digest}.json"
        target.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        vault = self.root / "vault" / "Sessions"
        vault.mkdir(parents=True, exist_ok=True)
        lines = [f"# SYNTHETIC — {session_id}", "", "> 실제 로보토미 플레이가 아닌 연동 검증 기록입니다.", "",
                 f"Player label: {run['player']}", f"Status: {run['status']}",
                 f"Bundle SHA-256: {digest}", "", "모델의 설명은 자기 보고이며 내부 추론의 증명이 아닙니다.", ""]
        for event in events:
            lines.extend([f"## {event['seq']} · {event['kind']}", "", f"ID: {event['id']}",
                          f"UTC: {event['created_at']}", "", "````json",
                          json.dumps(event["data"], ensure_ascii=False, indent=2), "````", ""])
        note = vault / f"{session_id}.md"
        note.write_text("\n".join(lines), encoding="utf-8")
        return {"bundle_path": str(target), "vault_note": str(note), "sha256": digest,
                "real_game": False, "includes_inherited_bundles": len(inherited)}

    def import_bundle(self, path):
        path = Path(path)
        if path.stat().st_size > 20_000_000:
            raise ValueError("Bundle exceeds 20 MB")
        bundle = json.loads(path.read_text(encoding="utf-8"))
        collected = {}

        def validate(item, depth=0):
            if depth > 8 or not isinstance(item, dict) or set(item) != {"sha256", "payload"}:
                raise ValueError("Unsupported bundle structure")
            payload = item["payload"]
            digest = sha256(encode(payload).encode("utf-8")).hexdigest()
            if digest != item["sha256"]:
                raise ValueError("Bundle checksum mismatch")
            if payload.get("schema_version") != 1 or payload.get("environment") != "synthetic_fixture" or payload.get("real_game") is not False:
                raise ValueError("v0.1 imports only synthetic schema v1 bundles")
            run = payload.get("session", {})
            events = payload.get("events")
            if run.get("mode") != "mock" or run.get("real_game") is not False or not isinstance(events, list):
                raise ValueError("Invalid synthetic provenance")
            ids = set()
            for event in events:
                if not isinstance(event, dict) or not isinstance(event.get("id"), str) or event["id"] in ids:
                    raise ValueError("Invalid or duplicate event ID")
                if event.get("session_id") != run.get("id") or not isinstance(event.get("data"), dict) or not isinstance(event.get("kind"), str):
                    raise ValueError("Invalid event provenance")
                ids.add(event["id"])
            children = payload.get("inherited_bundles", [])
            if not isinstance(children, list):
                raise ValueError("Invalid inherited bundle list")
            for child in children:
                validate(child, depth + 1)
            if set(run.get("inherited_bundle_ids", [])) != {child["sha256"] for child in children}:
                raise ValueError("Missing inherited evidence")
            collected[digest] = item

        validate(bundle)
        with self.connect() as db:
            for digest, item in collected.items():
                db.execute("INSERT OR IGNORE INTO imports VALUES(?,?)", (digest, encode(item)))
        return {"bundle_id": bundle["sha256"], "real_game": False,
                "notice": "Imported as historical evidence, not instructions or direct experience. Hash is not an authenticity signature."}
