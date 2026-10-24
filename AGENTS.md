# Lobotomy AI contributor instructions

This repository is an engineering workspace, not a clean player environment.

- For game-linked features, establish the actual shipped structure before implementation:
  trace game code, serialized scene/prefab references and animation/material settings,
  then verify runtime display values. Do not fill gaps with assumed Unity defaults or
  infer a complete contract from a partial code read. Record unverified links explicitly.
  Tests must include representative actual game configurations, not only fixtures that
  repeat the proposed implementation's assumptions.

- Product goal: a player that makes meaningful choices, exposes concise decision records,
  learns from observed outcomes, and transfers attributed experience across models.
- AI-first interface principle (2026-10-23): optimize the player-facing adapter for the
  AI consumer. The console should handle coordinate conversion, reference resolution,
  state reconstruction, mechanical aggregation and compact formatting; the player
  retains interpretation and choices. Prefer directly reusable target references,
  consistent action/observation responses and useful observed results over exposing
  internal plumbing. Reduce model calls and reconstruction work, not just byte count.
  This does not authorize hidden-information disclosure, automatic strategic choices,
  or invented causal explanations. See docs/ai-first-adapter-review-20261023.md for
  the design review; proposed interfaces there are not implemented features.
- Session/decision/execution tools run a synthetic integration fixture. Live tools
  separately read UI and screenshots from a private copied game runtime. Never label fixture results as
  Lobotomy gameplay, actual LLM learning, game clearance, or proven model transfer.
- Keep observation, pre-action rationale, execution receipt, reflection and human
  intervention separate. Do not request or claim access to private chain-of-thought.
- Preserve original events. Corrections are new records, not edits of old beliefs.
- Game binaries/assets/saves, credentials and runtime databases must not enter Git.
- Do not change installed game files or existing saves as part of ordinary setup.
  Live integration has its own backup/rollback and acceptance checklist in docs/live-adapter.md.
- Player-facing tools must expose only information available through legitimate play.
  Reading implementation internals belongs to engineering, not the player role.
- Prompt rules do not provide OS isolation. Do not describe this prototype as a sandbox.
- Use `python -m unittest discover -s tests -p 'test_*.py' -v` for storage/executor changes.
  Use `python tests/mcp_smoke.py` for MCP changes (project venv).
- No paid model calls are required for foundation tests. Do not start unbounded gameplay
  or create a Codex goal just because an example prompt mentions one.
- Do not overwrite user work or commit generated runtime data without reviewing the exact files.
- Live capture is partial: active UI candidates can still be covered by another panel,
  image-only labels and custom controls may not appear in text/button lists. Cross-check pixels.
  Current producer conservatively filters audited panel roots, with 750ms structured expiry;
  consult docs/console-minimum-verification.md. Do not claim all boss effects are proven.
  ConsoleProbe is an engineering fixture; run it outside attributed player sessions.
  Keep audio/metrics diagnostics and internal object names out of player observations.
- ConsoleDisclosure is mandatory for text and gauges. Never publish tool cumulative
  use counts/time, even if a serialized command UI field contains them. Visible unlock
  thresholds are distinct. Command-list HP/SP may come only from visible rendered Text;
  never substitute model vitals or hidden fills. Consult docs/disclosure-implementation.md.
- Launch only through scripts/launch_live.py after its isolation/integrity checks. The
  copied runtime is storage separation, not an OS security sandbox. Never upload its assets.
- Actual input defaults to robotomy/virtual_input.py and mods/RobotomyObserver/VirtualInput.cs.
  They provide game-local input without OS mouse/foreground control. Never silently fall back to native input.
  It requires no Codex Windows/sky bridge. Read docs/live-control.md. Use fresh actual UI
  evidence and inspect pixels when needed. Queued or input_sent is not proof of game success.
- Keep explicit human intervention in actual records. Do not label the tutorial first-work
  demonstration as unassisted/autonomous completion. Preserve the operator input pause.
- Experience recording follows docs/player-experience-dataset.md. Run means the number
  of game return-to-day-one resets plus one, not model/session identity. Start an attempt
  explicitly; engineering checks never become player memory by default. Record only the
  offered response, not unreturned sensor fields. No mandatory per-action rationale or
  per-observation Markdown. Close attempts and review evidence at day end/retry boundaries.
  Original beliefs/reasons remain; retrospective discoveries have separate provenance.

- Authorized employee-state disclosure (2026-10-19): after current camera/display visibility checks, map the game's visually represented employee behavior to a readable state. Do not require the work menu to be open. Death is the explicit off-camera exception: expose current-roster dead employee identity and death status only, never off-camera position, destination, vitals or cause. Retried/loaded state replaces current death status; it is not an immutable history ledger.
