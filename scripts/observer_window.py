"""Allow resizing/maximizing the private Lobotomy_Observer window without restarting."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from robotomy.observer_window import configure, ensure_aspect_guard, watch_aspect

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable-resize',action='store_true')
    parser.add_argument('--watch-aspect',action='store_true')
    parser.add_argument('--size',nargs=2,type=int,metavar=('WIDTH','HEIGHT'))
    args=parser.parse_args()
    if args.watch_aspect: watch_aspect(ROOT)
    else:
        if args.enable_resize: ensure_aspect_guard(ROOT)
        print(json.dumps(configure(ROOT,enable_resize=args.enable_resize,client_size=args.size),ensure_ascii=False))
