"""Read-only consumer of visible UI snapshots; independent of synthetic sessions.

The producer must publish latest.json atomically. This reader never attaches to a
process, sends input, opens a game save, or interprets hidden game state.
"""
from datetime import datetime, timezone
import json
import hashlib
import math
import os
from pathlib import Path, PureWindowsPath
import threading
import time
import uuid
import copy


def command_rows(snapshot):
    """Group only this offered snapshot's admitted display items, never cached employees."""
    rows={}
    for item in snapshot.get('ui_texts',[])+snapshot.get('buttons',[]):
        if item.get('panel')!='command' or not item.get('row_id'): continue
        row=rows.setdefault(item['row_id'],dict(row_id=item['row_id'],name=None,hp=None,sp=None,
            status=None,action=None,action_detail=None,selectable=None,click=None))
        role=item.get('role')
        if role in ('name','hp','sp','status','action','action_detail'):
            row[role]=item['text']
        elif role=='click' and item.get('interactable'):
            row['click']={'x':item['x']+item['width']/2,'y':item['y']+item['height']/2,
                          'basis':'visible_row_click_handler_not_orderability'}
    # A displayed hover action is evidence only; unknown is never treated as false/true.
    return list(rows.values())


def observation_sections(snapshot):
    """Only current, disclosed values. Lists are replaced atomically, never merged by index."""
    ignored = {'captured_at_utc', 'sequence', 'unity_frame', 'isolation'}
    sections = {('/'+k):v for k,v in snapshot.items() if k not in ignored and k != 'console'}
    sections.update({'/console/'+k:v for k,v in snapshot.get('console', {}).items() if k not in ignored})
    return sections


def observation_diff(previous, current, observation_id, selection, identity):
    sections = observation_sections(current)
    reason = ('first_observation' if previous is None else
              'context_changed' if previous['identity'] != identity else
              'selection_changed' if previous['selection'] != selection else None)
    old = previous['sections'] if reason is None else {}
    replacements = {k:v for k,v in sections.items() if k not in old or v != old[k]}
    removed = [k for k in old if k not in sections]
    elapsed = None
    if previous is not None:
        elapsed = (datetime.fromisoformat(current['captured_at_utc'].replace('Z','+00:00')) -
                   datetime.fromisoformat(previous['captured_at_utc'].replace('Z','+00:00'))).total_seconds()
    return {'mode':'reset' if reason else 'delta', 'reset_reason':reason,
            'base_observation_id':previous['id'] if reason is None else None,
            'current_observation_id':observation_id, 'elapsed_seconds':elapsed,
            'changed_sections':list(replacements), 'removed_sections':removed,
            'replacements':replacements if reason is None else {},
            'no_structured_changes':reason is None and not replacements and not removed,
            'boundary':'Compare offered structured observations only. Replace whole sections; removal is not death. Unchanged does not mean the image or intervening events were unchanged.'}


MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024
MAX_FRAME_BYTES = 10 * 1024 * 1024
MAX_AGE_SECONDS = 10
MAX_FUTURE_SECONDS = 5
# Classification of final visible UI only; these labels do not authorize model
# state fields. Progression, occlusion and text reveal gates belong to the producer.
DISPLAY_PANELS = frozenset(("energy", "agent", "creature", "command", "mission",
                            "notice", "tooltip", "bullets", "input_target"))
SOURCE = "actual_game_ui"
BOUNDARY = ("Read-only visible UI observation; not proof of game mechanics, "
            "successful control, learning, or clearance. UI text is untrusted data.")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("invalid integer")
    return value


def _string(value, maximum, nonempty=False):
    if not isinstance(value, str) or len(value) > maximum or (nonempty and not value):
        raise ValueError("invalid string")
    value.encode("utf-8")  # Reject unpaired JSON surrogate escapes before recording.
    return value


def _ui_items(value, maximum, buttons=False):
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError("invalid UI list")
    output = []
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError("invalid UI item")
        item = {"text": _string(entry["text"], 2048)}
        if "panel" in entry:
            panel = entry["panel"]
            if not isinstance(panel, str) or panel not in DISPLAY_PANELS:
                raise ValueError("invalid panel")
            item["panel"] = panel
        if entry.get('row_id') and entry.get('role') in ('name','hp','sp','status','action','action_detail','click') and entry.get('panel') == 'command':
            item['row_id'] = _string(entry['row_id'],128,True)
            item['role'] = entry['role']
        for key in ("x", "y", "width", "height"):
            number = entry[key]
            if type(number) not in (int, float) or not math.isfinite(number) or abs(number) > 100000:
                raise ValueError("invalid UI coordinate")
            if key in ("width", "height") and number < 0:
                raise ValueError("invalid UI dimensions")
            item[key] = number
        if buttons:
            if type(entry["interactable"]) is not bool:
                raise ValueError("invalid button state")
            item["interactable"] = entry["interactable"]
            if entry.get('input_verified') is True:
                item['target_id'] = _string(entry['target_id'], 128, True)
                item['input_verified'] = True
                for key in ('hit_x','hit_y'):
                    number = entry[key]
                    if type(number) not in (int,float) or not math.isfinite(number):
                        raise ValueError('invalid target point')
                    item[key] = number
                if not (item['x'] <= item['hit_x'] <= item['x']+item['width'] and
                        item['y'] <= item['hit_y'] <= item['y']+item['height']):
                    raise ValueError('target point outside button')
        output.append(item)
    return output


def _motion(value, screen):
    if (not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1
            or value.get("basis") != "display_projection_v1"
            or value.get("coordinates") != "top_left_pixels"
            or value.get("units") != "pixels_per_real_second"
            or value.get("status") not in ("available", "withheld")):
        raise ValueError("invalid motion contract")
    tracks = value["tracks"]
    if not isinstance(tracks, list) or len(tracks) > 128 or (value["status"] == "withheld" and tracks):
        raise ValueError("invalid motion tracks")
    def number(v, low, high):
        if type(v) not in (float, int) or not math.isfinite(v) or not low <= v <= high:
            raise ValueError("invalid motion number")
        return v
    def vector(v, position=False):
        return {axis: number(v[axis], 0 if position else -10000000,
                            screen[dim] if position else 10000000)
                for axis, dim in (("x", "width"), ("y", "height"))}
    result, seen = [], set()
    for track in tracks:
        token = track["track_id"]
        if (not isinstance(token, str) or len(token) != 32 or any(c not in "0123456789abcdef" for c in token)
                or token in seen or track["state"] not in ("acquiring", "tracking", "discontinuity")):
            raise ValueError("invalid motion identity/state")
        seen.add(token)
        bbox = track["bounds"]
        rect = {k: number(bbox[k], 0, screen["width" if k in ("x", "width") else "height"])
                for k in ("x", "y", "width", "height")}
        if rect["x"] + rect["width"] > screen["width"] + .02 or rect["y"] + rect["height"] > screen["height"] + .02:
            raise ValueError("motion bounds outside screen")
        interval = number(track["interval_ms"], 0, 60000)
        item = {"track_id": token, "state": track["state"], "position": vector(track["position"], True),
                "bounds": rect, "interval_ms": interval}
        for key in ("screen_velocity", "object_velocity", "camera_velocity"):
            if track["state"] == "tracking":
                if not 10 <= interval <= 300:
                    raise ValueError("motion interval invalid")
                item[key] = vector(track[key])
            elif track[key] is not None:
                raise ValueError("unobserved motion must be unknown")
            else:
                item[key] = None
        if track["state"] == "tracking":
            for axis in ("x", "y"):
                if abs(item["screen_velocity"][axis] - item["object_velocity"][axis] - item["camera_velocity"][axis]) > .031:
                    raise ValueError("motion decomposition mismatch")
        result.append(item)
    return {"version": 1, "basis": "display_projection_v1", "coordinates": "top_left_pixels",
            "units": "pixels_per_real_second", "status": value["status"], "tracks": result}


def _console(value, screen=None):
    """Whitelist device data. Internal object/clip names never cross this boundary."""
    if not isinstance(value, dict) or value.get("version") != 1 or type(value.get("version")) is not int:
        raise ValueError("invalid console version")
    if value.get("policy") != "conservative_display_v1" or value.get("audio_basis") != "playback_state_approximation":
        raise ValueError("invalid console policy")
    def token(item, empty=False):
        if empty and item == "":
            return item
        if not isinstance(item, str) or len(item) != 32 or any(c not in "0123456789abcdef" for c in item):
            raise ValueError("invalid anonymous token")
        return item
    events = value["audio_events"]
    gauges = value["gauges"]
    if not isinstance(events, list) or len(events) > 128 or not isinstance(gauges, list) or len(gauges) > 512:
        raise ValueError("oversized console list")
    audio, bars = [], []
    previous = 0
    for event in events:
        identity = _integer(event["event_id"], 1, 2**63-1)
        if identity <= previous or event["kind"] not in ("start", "stop", "pause", "resume", "source_idle", "source_destroyed", "ongoing_detected"):
            raise ValueError("invalid audio sequence or kind")
        previous = identity
        at = _string(event["at_utc"], 64, True)
        instant = datetime.fromisoformat(at.replace("Z", "+00:00"))
        if instant.tzinfo is None or instant.utcoffset().total_seconds() != 0:
            raise ValueError("invalid audio timestamp")
        audio.append({"event_id": identity, "at_utc": at, "kind": event["kind"],
                      "source_token": token(event["source_token"]), "sound_token": token(event["sound_token"], True)})
    for gauge in gauges:
        if gauge["role"] not in ("energy", "agent_hp_bar", "agent_mental_bar"):
            raise ValueError("invalid gauge role")
        rectangle = _ui_items([{**gauge, "text": ""}], 1)[0]
        total = _integer(gauge["total_pixels"], 1, 32768)
        bars.append({"role": gauge["role"], **{key: rectangle[key] for key in ("x", "y", "width", "height")},
                     "filled_pixels": _integer(gauge["filled_pixels"], 0, total), "total_pixels": total})
    result = {"version": 1, "session": token(value["session"]),
            "unity_frame": _integer(value["unity_frame"], 0, 2**31-1),
            "policy": "conservative_display_v1", "valid_for_ms": _integer(value["valid_for_ms"], 1, 750),
            "audio_basis": "playback_state_approximation",
            "audio_dropped": _integer(value["audio_dropped"], 0, 2**31-1), "audio_events": audio, "gauges": bars}
    if "motion" in value:
        result["motion"] = _motion(value["motion"], screen)
    return result


def validate_snapshot(obj):
    """Validate and whitelist one capture without applying live freshness policy.

    Historical readers retain original timestamps; callers decide whether the
    validated capture can be used as a current observation.
    """
    if not isinstance(obj, dict):
        raise ValueError("invalid object")
    if (type(obj["schema_version"]) is not int or obj["schema_version"] != 1
            or obj["environment"] != "lobotomy_live" or obj["read_only"] is not True):
        raise ValueError("invalid identity")
    isolation = obj["isolation"]
    if (isolation["company_name"] != "Robotomy_AI"
            or isolation["product_name"] != "Lobotomy_Observer"):
        raise ValueError("invalid isolation identity")
    persistent_path = _string(isolation["persistent_data_path"], 4096, True)
    normalized = persistent_path.replace("\\", "/").rstrip("/")
    if (not PureWindowsPath(persistent_path).is_absolute()
            or not normalized.endswith("/Robotomy_AI/Lobotomy_Observer")
            or ".." in normalized.split("/")):
        raise ValueError("invalid isolation path")
    captured = _string(obj["captured_at_utc"], 64, True)
    timestamp = datetime.fromisoformat(captured.replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp.utcoffset().total_seconds() != 0:
        raise ValueError("timestamp must be UTC")
    screen = obj["screen"]
    snapshot = {
        "schema_version": 1, "environment": "lobotomy_live", "read_only": True,
        "captured_at_utc": captured,
        "process_id": _integer(obj["process_id"], 1, 2**32 - 1),
        "sequence": _integer(obj["sequence"], 0, 2**63 - 1),
        "scene": _string(obj["scene"], 256),
        "screen": {key: _integer(screen[key], 1, 32768) for key in ("width", "height")},
        "isolation": {"company_name": "Robotomy_AI", "product_name": "Lobotomy_Observer",
                      "persistent_data_path": persistent_path},
        "ui_texts": _ui_items(obj["ui_texts"], 512),
        "buttons": _ui_items(obj.get("buttons", []), 256, buttons=True),
    }
    if "console" in obj:
        snapshot["console"] = _console(obj["console"], snapshot["screen"])
    return snapshot, timestamp


class LiveReader:
    def __init__(self, root, *, clock=None):
        self.root = Path(root).resolve()
        self.directory = self.root / ".robotomy" / "live"
        self.snapshot_path = self.directory / "latest.json"
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()
        self._offered_baseline = None

    def _read(self):
        base = {"source": SOURCE, "read_only": True, "boundary": BOUNDARY}
        try:
            for attempt in range(4):
                try:
                    with self.snapshot_path.open("rb") as handle:
                        raw = handle.read(MAX_SNAPSHOT_BYTES + 1)
                    break
                except (PermissionError, FileNotFoundError):
                    # Mono/Windows replacement can briefly deny sharing or
                    # make the old path disappear. Retry reads only; the final
                    # absence still rejects observation and no action is sent.
                    if attempt == 3:
                        raise
                    time.sleep(.01)
        except FileNotFoundError:
            return {**base, "status": "never_connected"}, None
        except OSError:
            return {**base, "status": "invalid", "reason": "snapshot_unreadable"}, None
        if len(raw) > MAX_SNAPSHOT_BYTES:
            return {**base, "status": "invalid", "reason": "snapshot_too_large"}, None
        try:
            obj = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_object)
            snapshot, timestamp = validate_snapshot(obj)
            captured = snapshot["captured_at_utc"]
            age = (self.clock() - timestamp).total_seconds()
            if "console" in snapshot:
                motion = snapshot["console"].get("motion")
                if motion is not None and age > .25:
                    motion.update(status="expired", tracks=[])
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
            return {**base, "status": "invalid", "reason": "snapshot_contract_violation"}, None
        if age < -MAX_FUTURE_SECONDS:
            return {**base, "status": "invalid", "reason": "snapshot_from_future"}, None
        summary = {**base, "captured_at_utc": captured, "age_seconds": round(age, 3),
                   "process_id": snapshot["process_id"], "sequence": snapshot["sequence"]}
        max_age = snapshot.get("console", {}).get("valid_for_ms", MAX_AGE_SECONDS * 1000) / 1000
        if age > max_age:
            return {**summary, "status": "stale"}, None
        return {**summary, "status": "live", "scene": snapshot["scene"],
                "ui_text_count": len(snapshot["ui_texts"]),
                "button_count": len(snapshot["buttons"])}, snapshot

    def status(self):
        """Validate freshness and producer identity without creating observation records."""
        summary, _ = self._read()
        return summary

    def frame(self):
        """Retry only read-side publication races, never an input/action."""
        for attempt in range(5):
            status, data = self._frame_once()
            if data is not None or status.get("reason") not in ("frame_unreadable", "frame_missing", "frame_generation_mismatch"):
                return status, data
            if attempt < 4:
                time.sleep(.02)
        return status, None

    def _frame_once(self):
        """Return validated fixed-path PNG bytes or a status, without writing any records."""
        summary, snapshot = self._read()
        if snapshot is None:
            return summary, None
        try:
            with (self.directory / "frame.png").open("rb") as handle:
                before = os.fstat(handle.fileno())
                data = handle.read(MAX_FRAME_BYTES + 1)
                after = os.fstat(handle.fileno())
        except FileNotFoundError:
            return {**summary, "status": "invalid", "reason": "frame_missing"}, None
        except OSError:
            return {**summary, "status": "invalid", "reason": "frame_unreadable"}, None
        if len(data) > MAX_FRAME_BYTES:
            return {**summary, "status": "invalid", "reason": "frame_too_large"}, None
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            return {**summary, "status": "invalid", "reason": "frame_changed_during_read"}, None
        if (len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n"
                or data[8:16] != b"\x00\x00\x00\x0dIHDR"
                or not 1 <= int.from_bytes(data[16:20], "big") <= 32768
                or not 1 <= int.from_bytes(data[20:24], "big") <= 32768):
            return {**summary, "status": "invalid", "reason": "frame_invalid_png_header"}, None
        age = self.clock().timestamp() - after.st_mtime
        if age < -MAX_FUTURE_SECONDS:
            return {**summary, "status": "invalid", "reason": "frame_from_future"}, None
        if age > MAX_AGE_SECONDS:
            return {**summary, "status": "stale", "reason": "frame_stale",
                    "frame_age_seconds": round(age, 3)}, None
        frame_meta = {}
        if "console" in snapshot:
            try:
                raw_meta = (self.directory / "frame-meta.json").read_bytes()
                if len(raw_meta) > 4096:
                    raise ValueError("oversized frame metadata")
                meta = json.loads(raw_meta, object_pairs_hook=_unique_object)
                if (meta["session"] != snapshot["console"]["session"] or meta["process_id"] != snapshot["process_id"]
                        or meta["scene"] != snapshot["scene"] or hashlib.sha256(data).hexdigest() != meta["sha256"]
                        or int.from_bytes(data[16:20], "big") != snapshot["screen"]["width"]
                        or int.from_bytes(data[20:24], "big") != snapshot["screen"]["height"]):
                    raise ValueError("frame generation mismatch")
                frame_meta = {"frame_unity_frame": _integer(meta["unity_frame"], 0, 2**31-1),
                              "frame_captured_at_utc": _string(meta["captured_at_utc"], 64, True)}
            except (OSError, ValueError, KeyError, TypeError):
                return {**summary, "status": "invalid", "reason": "frame_generation_mismatch"}, None
        return {**summary, "frame_age_seconds": round(age, 3), **frame_meta}, data

    def frame_after(self, after_utc=None, wait_ms=1200):
        """Wait for a post-action frame, not for dialogue completion. Never sends input."""
        _integer(wait_ms, 0, 2000)
        threshold = None
        if after_utc is not None:
            parsed = datetime.fromisoformat(after_utc.replace('Z', '+00:00'))
            if parsed.tzinfo is None: raise ValueError('after_utc needs a timezone')
            threshold = parsed.timestamp()
        started = time.monotonic(); deadline = started + wait_ms/1000
        while True:
            status, data = self.frame()
            captured = status.get('frame_captured_at_utc')
            newer = threshold is None or (captured is not None and
                datetime.fromisoformat(captured.replace('Z', '+00:00')).timestamp() > threshold)
            if data is not None and newer:
                return {**status, 'waited_ms':round((time.monotonic()-started)*1000),
                        'frame_boundary':'Fresh frame only; dialogue may still be revealing.'}, data
            if status.get('status') != 'live' or time.monotonic() >= deadline:
                return {**status, 'status':status.get('status') if status.get('status') != 'live' else 'no_new_frame',
                        'waited_ms':round((time.monotonic()-started)*1000)}, None
            time.sleep(min(.03, max(0, deadline-time.monotonic())))

    def observe(self, max_items=100, motion_only=False, compact=False, after_sequence=None, wait_ms=350):
        """Record exactly the bounded response; Markdown is deferred to day review."""
        from .experience import record
        _integer(max_items, 1, 100)
        if type(motion_only) is not bool:
            raise ValueError('motion_only must be boolean')
        if type(compact) is not bool:
            raise ValueError('compact must be boolean')
        _integer(wait_ms, 0, 1000)
        if after_sequence is not None: _integer(after_sequence, 0, 2**63-1)
        started = time.monotonic(); deadline = started + wait_ms/1000
        with self._lock:
            summary, snapshot = self._read()
            reference = self._offered_baseline
            def pending(value):
                if value is None or after_sequence is None: return False
                identity = (value['process_id'], value['scene'], value['screen'], value.get('console',{}).get('session'))
                # A new scene/process must be returned even when its counter restarted.
                if reference is not None and identity != reference['identity']: return False
                return value['sequence'] <= after_sequence
            while pending(snapshot) and time.monotonic() < deadline:
                time.sleep(min(.025, max(0, deadline-time.monotonic())))
                summary, snapshot = self._read()
            if pending(snapshot):
                return {**summary, 'status':'no_new_observation', 'waited_ms':round((time.monotonic()-started)*1000),
                        'boundary':'No newer sample yet; not evidence that the game is unchanged.'}
            if snapshot is None:
                self._offered_baseline = None
                return summary
            event_id = "live_" + uuid.uuid4().hex
            now = self.clock().astimezone(timezone.utc).isoformat()
            bounded = {**snapshot, "ui_texts": snapshot["ui_texts"][:max_items],
                       "buttons": snapshot["buttons"][:max_items]}
            truncated = len(snapshot["ui_texts"]) > max_items or len(snapshot["buttons"]) > max_items
            if motion_only:
                motion = snapshot.get('console', {}).get('motion', {'status': 'unsupported', 'tracks': []})
                truncated = len(motion['tracks']) > max_items
                bounded = {key:snapshot[key] for key in ('captured_at_utc','process_id','scene','screen')}
                bounded.update(unity_frame=snapshot.get('console', {}).get('unity_frame'),
                               motion={**motion, 'tracks': motion['tracks'][:max_items]})
            if not motion_only: bounded['command_rows'] = command_rows(bounded)
            response = {**summary, "observation_id": event_id, "recorded_at_utc": now,
                        "snapshot": bounded, "truncated": truncated}
            selection = {'max_items':max_items,'motion_only':motion_only}
            identity = (snapshot['process_id'], snapshot['scene'], snapshot['screen'],
                        snapshot.get('console',{}).get('session'))
            previous = self._offered_baseline
            if previous is not None and snapshot['sequence'] < previous['sequence']:
                previous = None
            diff = observation_diff(previous,bounded,event_id,selection,identity)
            reasons = []
            if snapshot['scene'] != 'Main': reasons.append('story_or_other_scene')
            if diff['mode'] == 'reset': reasons.append('new_context_or_baseline')
            if truncated: reasons.append('truncated_information')
            if not bounded.get('ui_texts') and not bounded.get('console'): reasons.append('limited_structured_coverage')
            response['visual_check'] = {'recommended':bool(reasons), 'reasons':reasons,
                'boundary':'Advisory only. No change cannot rule out animation, danger, story or missed events. Player must inspect significant/ambiguous changes and periodic frames.'}
            response['waited_ms'] = round((time.monotonic()-started)*1000)
            response = {'change_summary':diff, **response, 'compact':compact,
                        'payload_mode':'full' if not compact or diff['mode']=='reset' else 'delta',
                        'comparison_scope':'selected structured fields only; truncated response is not full coverage'}
            if response['payload_mode']=='delta':
                response.pop('snapshot')
            event = {"id": event_id, "kind": "live_observation", "recorded_at_utc": now,
                     "source": SOURCE, "read_only": True, "boundary": BOUNDARY,
                     "snapshot": bounded, "selection": {"max_items":max_items,"motion_only":motion_only},
                     "truncated":truncated}
            event.update(change_summary=diff,compact=compact,payload_mode=response['payload_mode'])
            if response['payload_mode']=='delta':
                event.pop('snapshot')
            self.directory.mkdir(parents=True, exist_ok=True)
            payload = (json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
            descriptor = os.open(self.directory / "observations.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                if os.write(descriptor, payload) != len(payload):
                    raise OSError("incomplete observation append")
            finally:
                os.close(descriptor)
            response['experience_recording'] = record(self.root, 'observation_offered', response)
            self._offered_baseline = copy.deepcopy({'id':event_id,'sections':observation_sections(bounded),
                'identity':identity,'selection':selection,'captured_at_utc':bounded['captured_at_utc'],
                'sequence':snapshot['sequence']})
            return response
