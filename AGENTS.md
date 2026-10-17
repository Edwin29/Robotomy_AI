# Robotomy AI contributor instructions

This repository is an engineering workspace, not a clean player environment.

- Product goal: a player that makes meaningful choices, exposes concise decision records,
  learns from observed outcomes, and transfers attributed experience across models.
- v0.1 runs only a synthetic integration fixture. Never label fixture results as
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
