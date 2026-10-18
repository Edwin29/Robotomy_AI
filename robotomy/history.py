"""Bounded, read-only access to the console's count-limited observation ring.

History is never a fresh control observation. Files may be replaced while they
are read; generation checks reject missing/overwritten entries instead of
substituting a newer capture. No read creates experience or vault records.
"""
import hashlib
import json
from pathlib import Path

from .live import (BOUNDARY, SOURCE, MAX_FRAME_BYTES, MAX_SNAPSHOT_BYTES,
                   _integer, _unique_object, validate_snapshot)

MAX_INDEX_BYTES = 256 * 1024
MAX_CAPACITY = 600
MAX_FRAME_CAPACITY = 60
MAX_READ_LIMIT = 50
_ERRORS = (OSError, ValueError, TypeError, KeyError, AttributeError,
           OverflowError, RecursionError)
_BASE = {"source": SOURCE, "read_only": True, "historical": True,
         "actionable": False, "boundary": BOUNDARY}


def _token(value, length=32):
    if (not isinstance(value, str) or len(value) != length
            or any(c not in "0123456789abcdef" for c in value)):
        raise ValueError("invalid history token")
    return value


def _json(path, maximum):
    with path.open("rb") as handle:
        raw = handle.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("oversized history file")
    result = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_object)
    if not isinstance(result, dict):
        raise ValueError("invalid history object")
    return result


class HistoryReader:
    def __init__(self, root):
        self.directory = Path(root).resolve() / ".robotomy" / "live" / "history"

    def _index(self, session=None):
        index = _json(self.directory / "index.json", MAX_INDEX_BYTES)
        if type(index.get("version")) is not int or index["version"] != 1:
            raise ValueError("invalid history version")
        identity = _token(index["session"])
        if session is not None and identity != session:
            raise ValueError("history session changed")
        capacity = _integer(index["capacity"], 1, MAX_CAPACITY)
        frame_capacity = _integer(index["frame_capacity"], 1, MAX_FRAME_CAPACITY)
        records = index["records"]
        if not isinstance(records, list) or len(records) > capacity:
            raise ValueError("invalid history list")
        output, slots, frame_slots, previous = [], set(), set(), -1
        for item in records:
            sequence = _integer(item["sequence"], 0, 2**63 - 1)
            slot = _integer(item["slot"], 0, capacity - 1)
            unity_frame = _integer(item["unity_frame"], 0, 2**31 - 1)
            if sequence <= previous or slot in slots or type(item["has_frame"]) is not bool:
                raise ValueError("invalid history ordering")
            previous = sequence
            slots.add(slot)
            frame_slot = item["frame_slot"]
            digest = item["sha256"]
            if item["has_frame"]:
                _integer(frame_slot, 0, frame_capacity - 1)
                _token(digest, 64)
                if frame_slot in frame_slots:
                    raise ValueError("duplicate frame slot")
                frame_slots.add(frame_slot)
            elif frame_slot is not None or digest is not None:
                raise ValueError("unexpected frame metadata")
            output.append({"sequence": sequence, "unity_frame": unity_frame,
                           "slot": slot, "has_frame": item["has_frame"],
                           "frame_slot": frame_slot, "sha256": digest})
        return {"session": identity, "capacity": capacity,
                "frame_capacity": frame_capacity, "records": output,
                "dropped": _integer(index.get("dropped", 0), 0, 2**63 - 1)}

    def _sample(self, index, record):
        envelope = _json(self.directory / f"sample-{record['slot']}.json",
                         MAX_SNAPSHOT_BYTES + 4096)
        if (type(envelope.get("version")) is not int or envelope["version"] != 1
                or envelope["session"] != index["session"]
                or type(envelope["sequence"]) is not int
                or envelope["sequence"] != record["sequence"]):
            raise ValueError("history slot overwritten")
        snapshot, _ = validate_snapshot(envelope["snapshot"])
        console = snapshot.get("console", {})
        if (snapshot["sequence"] != record["sequence"]
                or console.get("session") != index["session"]
                or console.get("unity_frame") != record["unity_frame"]):
            raise ValueError("history generation mismatch")
        return snapshot

    def read(self, after_sequence=None, limit=10, session=None):
        """Read latest N or first N after a cursor, without wall-clock expiry.

        Sequence gaps can include paused captures, so no fabricated missing
        samples are inferred from sequence arithmetic. Retention loss and
        unreadable/overwritten records are reported explicitly instead.
        """
        _integer(limit, 1, MAX_READ_LIMIT)
        if after_sequence is not None:
            _integer(after_sequence, 0, 2**63 - 1)
        if session is not None:
            _token(session)
        try:
            index = self._index(session)
        except FileNotFoundError:
            return {**_BASE, "status": "unavailable", "reason": "history_missing", "records": []}
        except _ERRORS:
            return {**_BASE, "status": "invalid", "reason": "history_index_invalid_or_session_changed", "records": []}
        records = index["records"]
        selected = ([r for r in records if r["sequence"] > after_sequence]
                    if after_sequence is not None else records)
        truncated = len(selected) > limit
        selected = selected[:limit] if after_sequence is not None else selected[-limit:]
        sequence_gaps = []
        previous = after_sequence
        for record in selected:
            if previous is not None and record["sequence"] > previous + 1:
                sequence_gaps.append({"after": previous, "before": record["sequence"]})
            previous = record["sequence"]
        output, gaps = [], []
        for record in selected:
            try:
                snapshot = self._sample(index, record)
            except _ERRORS:
                gaps.append({"sequence": record["sequence"], "reason": "sample_unavailable_or_overwritten"})
                continue
            output.append({"historical": True, "actionable": False,
                           "sequence": record["sequence"], "unity_frame": record["unity_frame"],
                           "captured_at_utc": snapshot["captured_at_utc"],
                           "has_frame": record["has_frame"], "snapshot": snapshot})
        # A process restart must not mix history from two producer sessions.
        try:
            self._index(index["session"])
        except _ERRORS:
            return {**_BASE, "status": "invalid", "reason": "history_changed_during_read", "records": []}
        return {**_BASE, "status": "partial" if gaps else "available",
                "session": index["session"], "capacity": index["capacity"],
                "frame_capacity": index["frame_capacity"], "retained_count": len(records),
                "producer_dropped": index["dropped"],
                "oldest_sequence": records[0]["sequence"] if records else None,
                "newest_sequence": records[-1]["sequence"] if records else None,
                "cursor_before_retained": bool(records and after_sequence is not None
                                                and after_sequence < records[0]["sequence"]),
                "next_after_sequence": selected[-1]["sequence"] if selected else after_sequence,
                "sequence_gaps": sequence_gaps,
                "sequence_gap_note": "Capture sequence gaps can include pause or skipped publication; they do not prove lost active samples.",
                "truncated": truncated, "gaps": gaps, "records": output}

    def frame(self, session, sequence):
        """Get the exact historical frame by session and sequence, never a path."""
        _token(session)
        _integer(sequence, 0, 2**63 - 1)
        base = {**_BASE, "session": session, "sequence": sequence}
        try:
            index = self._index(session)
            record = next((r for r in index["records"] if r["sequence"] == sequence), None)
            if record is None or not record["has_frame"]:
                return {**base, "status": "unavailable", "reason": "frame_not_retained"}, None
            snapshot = self._sample(index, record)
            with (self.directory / f"frame-{record['frame_slot']}.png").open("rb") as handle:
                data = handle.read(MAX_FRAME_BYTES + 1)
            if (len(data) > MAX_FRAME_BYTES or len(data) < 33
                    or data[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR"
                    or int.from_bytes(data[16:20], "big") != snapshot["screen"]["width"]
                    or int.from_bytes(data[20:24], "big") != snapshot["screen"]["height"]
                    or hashlib.sha256(data).hexdigest() != record["sha256"]):
                raise ValueError("historical frame mismatch")
            current = self._index(session)
            if record not in current["records"]:
                raise ValueError("historical frame no longer retained")
        except _ERRORS:
            return {**base, "status": "invalid", "reason": "frame_unavailable_or_generation_mismatch"}, None
        return {**base, "status": "available", "unity_frame": record["unity_frame"],
                "captured_at_utc": snapshot["captured_at_utc"], "mime_type": "image/png"}, data
