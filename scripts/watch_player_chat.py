"""Background public-chat collector. No game input, model calls, or player tool calls."""
from pathlib import Path
import sys
import ctypes
from ctypes import wintypes as w
import time
import os
import hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from robotomy.chat_capture import ChatCapture, stamp
from robotomy.experience import write, encode


def main():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,w.BOOL,w.LPCWSTR];kernel.CreateMutexW.restype=w.HANDLE
    kernel.CloseHandle.argtypes=[w.HANDLE]
    mutex=kernel.CreateMutexW(None,False,'Local\\RobotomyChat-'+hashlib.sha256(str(ROOT).encode()).hexdigest()[:16])
    if not mutex: raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error()==183:
        kernel.CloseHandle(mutex);return
    try:
        while True:
            start=time.monotonic()
            try:
                # Reload committed cursor after errors, never acknowledge uncommitted events.
                report=ChatCapture(ROOT).poll();report['status']='ready'
            except Exception as exc:
                report={'status':'error','error':str(exc)}
            write(ROOT/'.robotomy/experience/chat-status.json',encode({**report,'at':stamp(),
                'pid':os.getpid(),'poll_ms':round((time.monotonic()-start)*1000,2)}))
            time.sleep(1)
    finally:kernel.CloseHandle(mutex)


if __name__=='__main__':main()
