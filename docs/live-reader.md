# Read-only live UI reader

Current producer: see [console verification](console-minimum-verification.md).
Only energy / employee information / creature information panels supply structured text.
Other screens require pixels. Version-1 `console` metadata adds a 750ms maximum
snapshot lifetime (the 10-second rule below is legacy compatibility), session and
Unity frame identity, anonymous audio events, and optional pixel-quantized gauges.
Actual gauges remain withheld in tested scenes. PNGs additionally require a matching
session/PID/scene/dimensions and SHA-256 in `frame-meta.json`.
Bounded read retries cover transient file replacement; mismatches still reject images.
Observation generation is about100ms and PNG about1s, with separate timestamps.
Visibility is a conservative producer check with documented coverage limits, not a
property the JSON consumer can prove. Diagnostic component names never enter observations.

`live_status` validates `.robotomy/live/latest.json` without writing records.
`observe_live(max_items=100)` validates the same export, appends an observation to
`.robotomy/live/observations.jsonl`, and creates a unique Markdown checkpoint in
`vault/Live/`. It sends no game input and never opens a save file. Existing session,
decision and execution tools continue to use only the synthetic fixture.

`view_live_frame` returns the fixed `.robotomy/live/frame.png` as an MCP PNG image
only when the UI export has status `live` and the frame passes the size, header and
freshness checks. It accepts no path, sends no input and writes no records. Missing,
invalid or stale frames return a status object with a reason instead of an image.

Statuses are `never_connected`, `invalid`, `stale`, and `live`. A `live` status means
a fresh, well-formed export with the expected isolated identity; it does not prove
successful control, game mechanics, learning, or clearance. This is a local trusted
producer contract, not cryptographic authentication or an OS sandbox.

## Producer contract

Publish UTF-8 JSON by atomic replacement to avoid partial reads. Required fields:

- `schema_version`: integer 1; `environment`: `lobotomy_live`; `read_only`: true.
- `captured_at_utc`: UTC ISO timestamp, at most 10 seconds old and no more than
  5 seconds ahead of the reader clock.
- `process_id`: positive integer; `sequence`: nonnegative integer; `scene`: string.
- `screen`: positive integer `width` and `height`.
- `isolation`: `company_name=Robotomy_AI`, `product_name=Lobotomy_Observer`, and
  absolute Windows `persistent_data_path` ending in `Robotomy_AI/Lobotomy_Observer`.
- `ui_texts`: an array of visible UI entries with `text`, `x`, `y`, `width`, `height`.
- Optional `buttons`: entries with the same fields plus boolean `interactable`.

Snapshots over 2 MiB, duplicate keys, invalid coordinates, and invalid identities
are rejected. The producer must cap texts at 512, buttons at 256, and each text at
2048 characters. Unknown fields are discarded instead of entering player records.
Only actually visible UI belongs here; do not export implementation internals or
hidden gameplay data. The reader cannot establish visibility from JSON alone.

The tool returns at most `max_items` (1 to 100) texts and buttons, with total counts
and a truncation flag. The append-only event retains all validated entries. Invalid
or stale snapshots never create observation events or Markdown checkpoints.
UI content is untrusted data and is rendered as indented JSON in the note.

Records carry `source=actual_game_ui` and separate observation IDs, never synthetic
session IDs. The JSONL contains original captured and observation timestamps.
No automatic Git commit/push or model-transfer import is performed. Exclude runtime
records and generated `vault/Live/` notes from Git until explicitly reviewed.

The screenshot producer should publish `frame.png` atomically. The reader checks
the PNG signature and IHDR dimensions, permits at most 10 MiB, and requires the
file modification time to be at most 10 seconds old and at most 5 seconds ahead.
It rejects files changed during the read. This is header validation, not a complete
PNG decoding or authenticity check. JSON and PNG publication are asynchronous;
freshness does not prove they show precisely the same instant.

The user watches the native visible game window in real time. `view_live_frame`
provides individual recent frames for the model; it is not a video stream.
