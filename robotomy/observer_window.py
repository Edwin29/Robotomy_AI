"""Operator display controls for the verified private Unity window; no input injection."""
import ctypes
from ctypes import wintypes as w
from pathlib import Path
import os
import subprocess
import sys
import time

from .virtual_input import read_json, verify_process


def configure(root, *, enable_resize=False, client_size=None):
    """Enable normal border resize/maximize, optionally size the client in physical pixels.

    Never selects the installed game, changes focus, injects input or touches saves.
    No persistent Win32 hooks or changes to game binaries/settings.
    """
    root=Path(root).resolve()
    if client_size is not None:
        width,height=client_size
        if any(type(v) is not int for v in (width,height)) or not (640<=width<=3840 and 360<=height<=2160):
            raise ValueError('Client size must be 640..3840 x 360..2160')
    manifest=read_json(root/'.robotomy/live/isolation.json')
    runtime=root/'.robotomy/runtime/LobotomyCorp'
    if not manifest.get('prepared') or Path(manifest['runtime']).resolve()!=runtime:
        raise ValueError('Unrecognized private runtime')
    observation=read_json(root/'.robotomy/live/latest.json')
    if Path(observation['isolation']['persistent_data_path']).resolve()!=Path(manifest['isolated_save_path']).resolve():
        raise ValueError('Unexpected save identity')
    pid=observation['process_id']
    verify_process(pid,runtime/'LobotomyCorp.exe')
    u=ctypes.WinDLL('user32',use_last_error=True)
    u.GetWindowThreadProcessId.argtypes=[w.HWND,ctypes.POINTER(w.DWORD)]
    u.IsWindowVisible.argtypes=[w.HWND];u.IsWindowVisible.restype=w.BOOL
    u.GetWindowTextW.argtypes=[w.HWND,w.LPWSTR,ctypes.c_int]
    u.GetClientRect.argtypes=[w.HWND,ctypes.POINTER(w.RECT)]
    u.GetWindowRect.argtypes=[w.HWND,ctypes.POINTER(w.RECT)]
    u.GetWindowLongW.argtypes=[w.HWND,ctypes.c_int];u.GetWindowLongW.restype=ctypes.c_long
    u.SetWindowLongW.argtypes=[w.HWND,ctypes.c_int,ctypes.c_long];u.SetWindowLongW.restype=ctypes.c_long
    u.SetWindowPos.argtypes=[w.HWND,w.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.UINT]
    u.SetWindowPos.restype=w.BOOL
    u.SetThreadDpiAwarenessContext.argtypes=[w.HANDLE];u.SetThreadDpiAwarenessContext.restype=w.HANDLE
    callback_type=ctypes.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
    u.EnumWindows.argtypes=[callback_type,w.LPARAM]
    handles=[]
    @callback_type
    def found(hwnd,_):
        actual=w.DWORD();u.GetWindowThreadProcessId(hwnd,ctypes.byref(actual))
        if actual.value==pid and u.IsWindowVisible(hwnd):
            title=ctypes.create_unicode_buffer(512);u.GetWindowTextW(hwnd,title,len(title))
            if title.value=='Lobotomy_Observer': handles.append(hwnd)
        return True
    u.EnumWindows(found,0)
    if len(handles)!=1: raise ValueError('Expected one visible private observer window')
    hwnd=handles[0]
    dpi_before=u.SetThreadDpiAwarenessContext(w.HANDLE(-4))
    try:
        client=w.RECT();outer=w.RECT()
        if not u.GetClientRect(hwnd,ctypes.byref(client)) or not u.GetWindowRect(hwnd,ctypes.byref(outer)):
            raise ctypes.WinError(ctypes.get_last_error())
        before=[client.right,client.bottom]
        style=u.GetWindowLongW(hwnd,-16)&0xffffffff
        wanted=style|0x00040000|0x00010000 if enable_resize else style
        if wanted!=style:
            ctypes.set_last_error(0)
            prior=u.SetWindowLongW(hwnd,-16,ctypes.c_long(wanted).value)
            if not prior and ctypes.get_last_error(): raise ctypes.WinError(ctypes.get_last_error())
            if not u.SetWindowPos(hwnd,None,0,0,0,0,0x0020|0x0001|0x0002|0x0004|0x0010):
                u.SetWindowLongW(hwnd,-16,ctypes.c_long(style).value)
                raise ctypes.WinError(ctypes.get_last_error())
            # The thicker border would otherwise shrink the Unity render area.
            if client_size is None: client_size=before
        if client_size is not None:
            width,height=client_size
            u.GetClientRect(hwnd,ctypes.byref(client));u.GetWindowRect(hwnd,ctypes.byref(outer))
            border_x=outer.right-outer.left-client.right
            border_y=outer.bottom-outer.top-client.bottom
            if not u.SetWindowPos(hwnd,None,0,0,width+border_x,height+border_y,0x0002|0x0004|0x0010):
                raise ctypes.WinError(ctypes.get_last_error())
        u.GetClientRect(hwnd,ctypes.byref(client))
        return {'process_id':pid,'window':hwnd,'resizable':bool(wanted&0x40000),
                'maximize_enabled':bool(wanted&0x10000),'before_client':before,
                'client':[client.right,client.bottom],'coordinate_unit':'physical_pixels',
                'boundary':'Operator display configuration only; no game input'}
    finally:
        if dpi_before: u.SetThreadDpiAwarenessContext(dpi_before)


def aspect_size(current, previous, maximum=(1920,1080)):
    """Use the edge that changed most; exact 16:9 avoids camera viewport rounding."""
    width,height=current
    if abs(width-previous[0])>=abs(height-previous[1])*16/9:
        units=round(width/16)
    else: units=round(height/9)
    # The game encodes capture PNG on its main thread. Bound this display feature
    # to tested Full HD so a 4K desktop does not accidentally multiply capture cost.
    limit=min(maximum[0]//16,maximum[1]//9,120)
    units=max(1,min(max(40,units),limit))
    return (units*16,units*9)


def ensure_aspect_guard(root):
    root=Path(root).resolve()
    window=configure(root,enable_resize=True)
    marker=root/'.robotomy/live/observer-window.json'
    def alive():
        try:
            state=read_json(marker)
            return state['game_pid']==window['process_id'] and 0<=time.time()-state['at_epoch']<3
        except (OSError,ValueError,KeyError): return False
    if not alive():
        subprocess.Popen([sys.executable,'-X','utf8',str(root/'scripts/observer_window.py'),'--watch-aspect'],
                         cwd=root,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                         creationflags=subprocess.CREATE_NO_WINDOW)
        deadline=time.monotonic()+4
        while not alive() and time.monotonic()<deadline: time.sleep(.1)
        if not alive(): raise ValueError('Observer aspect guard did not start')
    return window


def watch_aspect(root):
    """Lightweight operator display helper. Waits out Windows modal move/resize.

    Does not sample the game, send game input, move the pointer or acquire focus.
    Ends with this particular game process; one watcher per PID.
    """
    from .live_control import atomic
    root=Path(root).resolve(); window=configure(root,enable_resize=True)
    pid=window['process_id'];hwnd=window['window']
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,w.BOOL,w.LPCWSTR];kernel.CreateMutexW.restype=w.HANDLE
    kernel.CloseHandle.argtypes=[w.HANDLE]
    mutex=kernel.CreateMutexW(None,False,'Local\\RobotomyObserverAspect-'+str(pid))
    if not mutex: raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error()==183:
        kernel.CloseHandle(mutex);return
    class GuiInfo(ctypes.Structure):
        _fields_=[('cbSize',w.DWORD),('flags',w.DWORD),('active',w.HWND),('focus',w.HWND),
                  ('capture',w.HWND),('menu',w.HWND),('move',w.HWND),('caret',w.HWND),('caretRect',w.RECT)]
    class MonitorInfo(ctypes.Structure):
        _fields_=[('cbSize',w.DWORD),('monitor',w.RECT),('work',w.RECT),('flags',w.DWORD)]
    u=ctypes.WinDLL('user32',use_last_error=True)
    u.IsWindow.argtypes=[w.HWND];u.IsZoomed.argtypes=[w.HWND];u.IsIconic.argtypes=[w.HWND]
    u.GetWindowThreadProcessId.argtypes=[w.HWND,ctypes.POINTER(w.DWORD)]
    u.GetGUIThreadInfo.argtypes=[w.DWORD,ctypes.POINTER(GuiInfo)]
    u.GetClientRect.argtypes=[w.HWND,ctypes.POINTER(w.RECT)]
    u.GetWindowRect.argtypes=[w.HWND,ctypes.POINTER(w.RECT)]
    u.MonitorFromWindow.argtypes=[w.HWND,w.DWORD];u.MonitorFromWindow.restype=w.HANDLE
    u.GetMonitorInfoW.argtypes=[w.HANDLE,ctypes.POINTER(MonitorInfo)]
    u.ShowWindow.argtypes=[w.HWND,ctypes.c_int]
    u.SetWindowPos.argtypes=[w.HWND,w.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.UINT]
    u.SetThreadDpiAwarenessContext.argtypes=[w.HANDLE];u.SetThreadDpiAwarenessContext.restype=w.HANDLE
    context=u.SetThreadDpiAwarenessContext(w.HANDLE(-4))
    previous=tuple(window['client']); heartbeat=0
    try:
        while u.IsWindow(hwnd):
            actual=w.DWORD();thread=u.GetWindowThreadProcessId(hwnd,ctypes.byref(actual))
            if actual.value!=pid: break
            gui=GuiInfo();gui.cbSize=ctypes.sizeof(gui)
            readable=u.GetGUIThreadInfo(thread,ctypes.byref(gui))
            if readable and not gui.flags&2 and not u.IsIconic(hwnd):
                client=w.RECT();outer=w.RECT()
                u.GetClientRect(hwnd,ctypes.byref(client));u.GetWindowRect(hwnd,ctypes.byref(outer))
                current=(client.right,client.bottom)
                if current!=previous or current[0]*9!=current[1]*16 or current[0]>1920 or current[1]>1080 or u.IsZoomed(hwnd):
                    monitor=MonitorInfo();monitor.cbSize=ctypes.sizeof(monitor)
                    if not u.GetMonitorInfoW(u.MonitorFromWindow(hwnd,2),ctypes.byref(monitor)):
                        raise ctypes.WinError(ctypes.get_last_error())
                    work=monitor.work
                    if u.IsZoomed(hwnd):
                        # Use the largest ordinary 16:9 window inside the monitor work area.
                        u.ShowWindow(hwnd,4)  # SW_SHOWNOACTIVATE; return to a resizable normal window.
                        u.GetClientRect(hwnd,ctypes.byref(client));u.GetWindowRect(hwnd,ctypes.byref(outer))
                        current=(work.right-work.left,work.bottom-work.top)
                    border=(outer.right-outer.left-client.right,outer.bottom-outer.top-client.bottom)
                    maximum=(work.right-work.left-border[0],work.bottom-work.top-border[1])
                    target=aspect_size(current,previous,maximum)
                    if target!=(client.right,client.bottom):
                        width,height=target[0]+border[0],target[1]+border[1]
                        left=max(work.left,min(outer.left,work.right-width))
                        top=max(work.top,min(outer.top,work.bottom-height))
                        if not u.SetWindowPos(hwnd,None,left,top,width,height,0x0004|0x0010):
                            raise ctypes.WinError(ctypes.get_last_error())
                    previous=target
            if time.monotonic()>=heartbeat:
                atomic(root/'.robotomy/live/observer-window.json',{'helper_pid':os.getpid(),
                       'game_pid':pid,'at_epoch':time.time(),'ratio':'16:9','last_client':list(previous)})
                heartbeat=time.monotonic()+1
            time.sleep(.25)
    finally:
        if context: u.SetThreadDpiAwarenessContext(context)
        kernel.CloseHandle(mutex)
