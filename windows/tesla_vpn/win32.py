"""Small, typed Win32 boundary: UAC, private state, and child process containment."""
import csv
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys


def supported_windows():
    return sys.platform == 'win32' and sys.getwindowsversion().major >= 10 and sys.getwindowsversion().build >= 17763 and sys.maxsize > 2**32


def is_admin():
    return sys.platform == 'win32' and bool(ctypes.windll.shell32.IsUserAnAdmin())


def private_directory(root):
    root.mkdir(parents=True, exist_ok=True)
    if sys.platform != 'win32':
        root.chmod(0o700); return
    result = subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'],
        text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    sid = next(csv.reader([result.strip()]))[1]
    if not sid.startswith('S-1-'): raise OSError('Could not identify the current Windows account.')
    subprocess.run(['icacls', str(root), '/inheritance:r', '/grant:r',
        f'*{sid}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F', '*S-1-5-32-544:(OI)(CI)F'],
        check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)


def repair_account_permissions(root):
    """Migrate old elevated mkdir(0700) ACLs without replacing account identities."""
    if sys.platform != 'win32' or not is_admin(): return
    accounts = root / 'accounts'
    if not accounts.exists(): return
    # The private root already grants the actual user SID, SYSTEM and administrators.
    # Reset old protected child ACLs to inherit those entries. /L acts on links themselves.
    subprocess.run(['icacls', str(accounts), '/reset', '/T', '/L', '/Q'],
        check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)


def wait_for_parent(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x100000, False, pid)
    if handle:
        try:
            if kernel.WaitForSingleObject(handle, 20000) != 0: raise OSError('Previous instance is still running.')
        finally: kernel.CloseHandle(handle)


def elevate(root, mode="tun"):
    if sys.platform != "win32": raise OSError("Windows TUN requires Windows 10/11.")
    from .runtime import command
    args = command('--connect', '--mode', mode, '--state-root', str(root), '--wait-parent', str(os.getpid()))
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    shell.ShellExecuteW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
        wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_int]
    shell.ShellExecuteW.restype = ctypes.c_ssize_t
    code = shell.ShellExecuteW(None, 'runas', args[0], subprocess.list2cmdline(args[1:]), None, 1)
    if code <= 32: raise OSError('Administrator permission was cancelled or could not be requested.')


class Job:
    """Kill an entire native process tree when its owning helper exits/crashes."""
    def __init__(self):
        if sys.platform != 'win32': raise OSError('Windows Job Objects require Windows.')
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        class Basic(ctypes.Structure):
            _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64), ('PerJobUserTimeLimit', ctypes.c_int64),
                ('LimitFlags', wintypes.DWORD), ('MinimumWorkingSetSize', ctypes.c_size_t),
                ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', wintypes.DWORD),
                ('Affinity', ctypes.c_size_t), ('PriorityClass', wintypes.DWORD), ('SchedulingClass', wintypes.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in ['ReadOperationCount','WriteOperationCount',
                'OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount']]
        class Extended(ctypes.Structure):
            _fields_ = [('BasicLimitInformation', Basic), ('IoInfo', IO),
                ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel = kernel; self.handle = kernel.CreateJobObjectW(None, None)
        info = Extended(); info.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
        if not self.handle or not kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            self.close(); raise ctypes.WinError(ctypes.get_last_error())

    def spawn(self, args, **kwargs):
        # Assign before the first thread runs so descendants cannot escape the job.
        child = subprocess.Popen(args, creationflags=0x4 | subprocess.CREATE_NO_WINDOW, **kwargs)
        if not self.kernel.AssignProcessToJobObject(self.handle, wintypes.HANDLE(int(child._handle))):
            child.kill(); child.wait(); raise ctypes.WinError(ctypes.get_last_error())
        # Python closes the primary thread handle; use NtResumeProcess instead.
        ntdll = ctypes.WinDLL('ntdll'); ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
        ntdll.NtResumeProcess.restype = ctypes.c_long
        if ntdll.NtResumeProcess(wintypes.HANDLE(int(child._handle))) < 0:
            child.kill(); child.wait(); raise OSError('Could not resume the VPN process.')
        return child

    def close(self):
        if getattr(self, 'handle', None):
            self.kernel.CloseHandle(self.handle); self.handle = None


def helper_stdio():
    """Windowed PyInstaller has no Python stdio; reopen inherited IPC pipe handles.

    Never AllocConsole/AttachConsole: the GUI and its helpers remain windowless.
    Duplicate handles so Python owns only its copies, not the OS standard handles.
    """
    if sys.platform != 'win32': return
    import io, msvcrt
    kernel = ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetStdHandle.argtypes=[wintypes.DWORD];kernel.GetStdHandle.restype=wintypes.HANDLE
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    kernel.DuplicateHandle.argtypes=[wintypes.HANDLE,wintypes.HANDLE,wintypes.HANDLE,
        ctypes.POINTER(wintypes.HANDLE),wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    process=kernel.GetCurrentProcess()
    for name,number,mode,flags in [('stdin',-10,'r',os.O_RDONLY),('stdout',-11,'w',os.O_WRONLY),('stderr',-12,'w',os.O_WRONLY)]:
        original=kernel.GetStdHandle(number & 0xffffffff)
        if not original or original==ctypes.c_void_p(-1).value:
            raise OSError('The helper requires inherited IPC pipes.')
        duplicate=wintypes.HANDLE()
        if not kernel.DuplicateHandle(process,original,process,ctypes.byref(duplicate),0,False,2):
            raise ctypes.WinError(ctypes.get_last_error())
        fd=msvcrt.open_osfhandle(int(duplicate.value),flags|os.O_BINARY)
        stream=io.TextIOWrapper(os.fdopen(fd,mode+'b',buffering=0),encoding='utf-8',line_buffering=mode=='w')
        setattr(sys,name,stream)
