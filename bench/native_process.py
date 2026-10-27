"""Own only a collector-created CLI tree, never its separately running host."""
from __future__ import annotations

import os
import signal
import subprocess

from . import quality_process


def _resume_primary_thread(process):
    """Resume a newly created, suspended Windows launcher after Job assignment."""
    import ctypes
    from ctypes import wintypes

    class ThreadEntry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ThreadID", wintypes.DWORD), ("th32OwnerProcessID", wintypes.DWORD),
                    ("tpBasePri", wintypes.LONG), ("tpDeltaPri", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD)]

    api = ctypes.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateToolhelp32Snapshot": ([wintypes.DWORD, wintypes.DWORD], wintypes.HANDLE),
        "Thread32First": ([wintypes.HANDLE, ctypes.POINTER(ThreadEntry)], wintypes.BOOL),
        "Thread32Next": ([wintypes.HANDLE, ctypes.POINTER(ThreadEntry)], wintypes.BOOL),
        "OpenThread": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
        "ResumeThread": ([wintypes.HANDLE], wintypes.DWORD),
        "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(api, name)
        function.argtypes, function.restype = arguments, result
    snapshot = api.CreateToolhelp32Snapshot(4, 0)  # TH32CS_SNAPTHREAD
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    threads = []
    try:
        entry = ThreadEntry()
        entry.dwSize = ctypes.sizeof(entry)
        found = api.Thread32First(snapshot, ctypes.byref(entry))
        while found:
            if entry.th32OwnerProcessID == process.pid:
                threads.append(entry.th32ThreadID)
            found = api.Thread32Next(snapshot, ctypes.byref(entry))
        error = ctypes.get_last_error()
        if error != 18:  # ERROR_NO_MORE_FILES
            raise ctypes.WinError(error)
    finally:
        api.CloseHandle(snapshot)
    # CREATE_SUSPENDED prevents the primary thread from spawning any others.
    if process.poll() is not None or len(threads) != 1:
        raise OSError("Owned suspended CLI must have exactly one primary thread")
    thread = api.OpenThread(2, False, threads[0])  # THREAD_SUSPEND_RESUME
    if not thread:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        previous = api.ResumeThread(thread)
        if previous == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        if previous != 1:
            raise OSError("Owned CLI primary thread had an unexpected suspend count")
    finally:
        api.CloseHandle(thread)


class CLIProcess:
    def __init__(self, args, env):
        self.process = None
        self.job = None
        try:
            if quality_process.WINDOWS:
                self.job = quality_process._WindowsJob()
            self.process = subprocess.Popen(
                args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=env, close_fds=True,
                creationflags=0x00000004 if quality_process.WINDOWS else 0,  # CREATE_SUSPENDED
                start_new_session=not quality_process.WINDOWS)
            if self.job is not None:
                self.job.assign(self.process)
                _resume_primary_thread(self.process)
        except BaseException as original:
            # No resume occurs before assignment. Even if resumption fails after
            # taking effect, all subsequently created descendants belong to Job.
            for cleanup in (self.terminate, self.close):
                try:
                    cleanup()
                except BaseException as error:
                    original.add_note("CLI cleanup failed: " + type(error).__name__)
            raise

    def terminate(self):
        try:
            if self.job is not None:
                self.job.stop()
            elif self.process is not None:
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        finally:
            try:
                if self.job is not None:
                    self.job.close()  # kill-on-close also applies if stop failed
                    self.job = None
            finally:
                if self.process is not None:
                    if self.process.poll() is None:
                        self.process.kill()
                    self.process.wait(timeout=5)

    def close(self):
        # Call only after descendant termination and reader-thread completion.
        try:
            if self.process is not None:
                self.process.stdout.close()
                self.process.stderr.close()
        finally:
            if self.job is not None:
                self.job.close()
                self.job = None
