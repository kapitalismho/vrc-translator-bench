from __future__ import annotations

import os
import subprocess
import time


WINDOWS = os.name == "nt"


class UnsupportedJudgePlatform(OSError):
    pass


if WINDOWS:
    import ctypes
    from ctypes import wintypes

    class _IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class _BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD),
        ]

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimits), ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    class _Accounting(ctypes.Structure):
        _fields_ = [
            ("TotalUserTime", ctypes.c_longlong), ("TotalKernelTime", ctypes.c_longlong),
            ("ThisPeriodTotalUserTime", ctypes.c_longlong), ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
            ("TotalPageFaultCount", wintypes.DWORD), ("TotalProcesses", wintypes.DWORD),
            ("ActiveProcesses", wintypes.DWORD), ("TotalTerminatedProcesses", wintypes.DWORD),
        ]

    class _ProcessListHeader(ctypes.Structure):
        _fields_ = [("NumberOfAssignedProcesses", wintypes.DWORD), ("NumberOfProcessIdsInList", wintypes.DWORD)]

    class _WindowsJob:
        def __init__(self):
            self.api = ctypes.WinDLL("kernel32", use_last_error=True)
            signatures = {
                "CreateJobObjectW": ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
                "SetInformationJobObject": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
                "AssignProcessToJobObject": ([wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
                "TerminateJobObject": ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
                "QueryInformationJobObject": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p], wintypes.BOOL),
                "OpenProcess": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
                "IsProcessInJob": ([wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)], wintypes.BOOL),
                "WaitForSingleObject": ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
                "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
            }
            for name, (arguments, result) in signatures.items():
                function = getattr(self.api, name)
                function.argtypes = arguments
                function.restype = result
            self.handle = self.api.CreateJobObjectW(None, None)
            if not self.handle:
                raise ctypes.WinError(ctypes.get_last_error())
            limits = _ExtendedLimits()
            limits.BasicLimitInformation.LimitFlags = 0x2000
            if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                error = ctypes.WinError(ctypes.get_last_error())
                self.close()
                raise error

        def assign(self, process):
            if not self.api.AssignProcessToJobObject(self.handle, wintypes.HANDLE(int(process._handle))):
                raise ctypes.WinError(ctypes.get_last_error())

        def _process_ids(self):
            capacity = 16
            while True:
                buffer = ctypes.create_string_buffer(ctypes.sizeof(_ProcessListHeader) + capacity * ctypes.sizeof(ctypes.c_size_t))
                header = _ProcessListHeader.from_buffer(buffer)
                result = self.api.QueryInformationJobObject(self.handle, 3, buffer, ctypes.sizeof(buffer), None)
                if not result and ctypes.get_last_error() != 234:
                    raise ctypes.WinError(ctypes.get_last_error())
                if result and header.NumberOfProcessIdsInList == header.NumberOfAssignedProcesses:
                    values = (ctypes.c_size_t * header.NumberOfProcessIdsInList).from_buffer(buffer, ctypes.sizeof(_ProcessListHeader))
                    return list(values)
                capacity = max(capacity * 2, header.NumberOfAssignedProcesses)

        def _process_handles(self):
            handles = []
            try:
                for pid in self._process_ids():
                    handle = self.api.OpenProcess(0x101000, False, pid)
                    if not handle:
                        if ctypes.get_last_error() == 87:
                            continue
                        raise ctypes.WinError(ctypes.get_last_error())
                    member = wintypes.BOOL()
                    if not self.api.IsProcessInJob(handle, self.handle, ctypes.byref(member)):
                        error = ctypes.WinError(ctypes.get_last_error())
                        self.api.CloseHandle(handle)
                        raise error
                    if member.value:
                        handles.append(handle)
                    else:
                        self.api.CloseHandle(handle)
                return handles
            except BaseException:
                for handle in handles:
                    self.api.CloseHandle(handle)
                raise

        def stop(self):
            limits = _ExtendedLimits()
            limits.BasicLimitInformation.LimitFlags = 0x2008
            limits.BasicLimitInformation.ActiveProcessLimit = 0
            if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
            handles = self._process_handles()
            try:
                if not self.api.TerminateJobObject(self.handle, 1):
                    raise ctypes.WinError(ctypes.get_last_error())
                for handle in handles:
                    if self.api.WaitForSingleObject(handle, 0xFFFFFFFF) != 0:
                        raise ctypes.WinError(ctypes.get_last_error())
                accounting = _Accounting()
                while True:
                    if not self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None):
                        raise ctypes.WinError(ctypes.get_last_error())
                    if accounting.ActiveProcesses == 0:
                        return
                    time.sleep(0.01)
            finally:
                for handle in handles:
                    self.api.CloseHandle(handle)

        def close(self):
            if self.handle:
                handle, self.handle = self.handle, None
                if not self.api.CloseHandle(handle):
                    raise ctypes.WinError(ctypes.get_last_error())


def run_command(command, *, input, timeout, env, synthetic):
    if not WINDOWS:
        if not synthetic:
            raise UnsupportedJudgePlatform("Real Sign in with ChatGPT judging requires Windows process containment; no subprocess was started")
        return subprocess.run(command, input=input, capture_output=True, text=True, encoding="utf-8", timeout=timeout, env=env)
    job = _WindowsJob()
    try:
        with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, encoding="utf-8", env=env, close_fds=True) as process:
            try:
                job.assign(process)
                try:
                    stdout, stderr = process.communicate(input, timeout=timeout)
                except subprocess.TimeoutExpired as error:
                    job.stop()
                    stdout, stderr = process.communicate()
                    raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr) from error
                return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
            finally:
                try:
                    job.stop()
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
    finally:
        job.close()
