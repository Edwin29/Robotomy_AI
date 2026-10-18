"""Player-only stdio entrypoint: no synthetic tools or developer control timeline."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import asyncio
from robotomy.reload_host import serve

if __name__=='__main__':
    from robotomy.chat_capture import ensure_capture
    ensure_capture(ROOT)
    from robotomy.git_sync import ensure_sync
    try:
        ensure_sync(ROOT)
    except Exception:
        # Publishing availability must never prevent playing.
        import traceback
        traceback.print_exc(file=sys.stderr)
    asyncio.run(serve(ROOT))
