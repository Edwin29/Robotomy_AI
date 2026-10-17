"""Absolute-path launcher so MCP does not depend on the host's working directory."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from robotomy.mcp_server import create_server

create_server(root).run(transport="stdio")
