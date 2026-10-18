"""Independent Git publisher. No game input and no extra model calls."""
from pathlib import Path
import sys
import os
import time
import ctypes
from ctypes import wintypes as w
import hashlib
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from robotomy.git_sync import sync_once
from robotomy.experience import write, encode, now


def main():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, w.BOOL, w.LPCWSTR]
    kernel.CreateMutexW.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    mutex = kernel.CreateMutexW(None, False, 'Local\\RobotomyGit-'+hashlib.sha256(str(ROOT).encode()).hexdigest()[:16])
    if not mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        kernel.CloseHandle(mutex)
        return
    try:
        while True:
            try:
                report = sync_once(ROOT)
            except Exception as exc:
                report = {'status': 'error', 'error': str(exc)}
            write(ROOT/'.robotomy/experience/git-sync-status.json', encode({**report, 'at': now(), 'pid': os.getpid()}))
            time.sleep(60)
    finally:
        kernel.CloseHandle(mutex)


if __name__ == '__main__':
    main()
