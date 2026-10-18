"""Set up the local player notebook. Never starts a play attempt or changes game state."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from robotomy.experience import journal

if __name__=='__main__':
    print(json.dumps(journal(ROOT).setup(),ensure_ascii=False,indent=2))
