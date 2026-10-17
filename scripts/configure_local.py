"""Generate project-local Codex config; never change global config or enable web policy."""
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
folder = root / ".codex"
folder.mkdir(exist_ok=True)
target = folder / "config.toml"
if target.exists():
    raise SystemExit("Project config already exists; merge manually instead of overwriting it.")
# JSON string literals are valid TOML basic strings for these paths.
target.write_text(
    "[mcp_servers.robotomy]\n"
    f"command = {json.dumps(str(Path(sys.executable).resolve()), ensure_ascii=False)}\n"
    f"args = [{json.dumps(str(root / 'scripts' / 'run_mcp.py'), ensure_ascii=False)}]\n"
    "startup_timeout_sec = 20\n"
    "tool_timeout_sec = 30\n",
    encoding="utf-8",
)
print(target)
