"""Windows-only ownership primitives for the installed Kikitan headless host."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import socket
import subprocess

from .gui_operator_adapter import process_identity
from .native_process import _resume_primary_thread
from . import quality_process


class WindowsRuntime:
    def __init__(self, executable):
        if os.name != "nt":
            raise ValueError("Installed Kikitan control requires Windows")
        self.executable = Path(executable).resolve(strict=True)
        if self.executable.name.lower() != "kikitantranslator.photino.exe":
            raise ValueError("Use the installed KikitanTranslator.Photino.exe")
        self.process = self.job = None

    def identity(self, pid):
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            if ctypes.get_last_error() == 87:  # process no longer exists
                return None
            raise ValueError("Cannot inspect owned process")
        try:
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                raise ValueError("Cannot inspect owned process exit")
            if code.value != 259:
                return None
            return process_identity(pid)
        finally:
            kernel.CloseHandle(handle)

    def instances(self):
        class Entry(ctypes.Structure):
            _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD),
                        ("heap", ctypes.c_size_t), ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
                        ("parent", wintypes.DWORD), ("priority", wintypes.LONG), ("flags", wintypes.DWORD),
                        ("name", wintypes.WCHAR * 260)]
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
        kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel.Process32FirstW.argtypes = kernel.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(Entry))
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.CreateToolhelp32Snapshot(2, 0)
        if handle == ctypes.c_void_p(-1).value:
            raise ValueError("Cannot enumerate application instances")
        try:
            entry, found = Entry(), []
            entry.size = ctypes.sizeof(entry)
            more = kernel.Process32FirstW(handle, ctypes.byref(entry))
            while more:
                if entry.name.lower().startswith("kikitan"):
                    found.append(entry.pid)
                more = kernel.Process32NextW(handle, ctypes.byref(entry))
            if ctypes.get_last_error() != 18:
                raise ValueError("Incomplete application process enumeration")
            return found
        finally:
            kernel.CloseHandle(handle)

    def listeners(self):
        class Row(ctypes.Structure):
            _fields_ = [(name, wintypes.DWORD) for name in ("state", "address", "port", "remote", "remote_port", "pid")]
        api = ctypes.WinDLL("iphlpapi", use_last_error=True)
        api.GetExtendedTcpTable.argtypes = (ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), wintypes.BOOL,
                                           wintypes.ULONG, ctypes.c_int, wintypes.ULONG)
        size = wintypes.DWORD()
        result = api.GetExtendedTcpTable(None, ctypes.byref(size), False, 2, 3, 0)  # AF_INET, OWNER_PID_LISTENER
        if result not in (0, 122):
            raise ValueError("Cannot inspect application listener")
        buffer = ctypes.create_string_buffer(size.value)
        if api.GetExtendedTcpTable(buffer, ctypes.byref(size), False, 2, 3, 0):
            raise ValueError("Cannot inspect application listener")
        count = ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD)).contents.value
        rows = (Row * count).from_buffer(buffer, ctypes.sizeof(wintypes.DWORD))
        return [(socket.inet_ntoa(row.address.to_bytes(4, "little")), row.pid)
                for row in rows if socket.ntohs(row.port & 0xffff) == 18378]

    def launch(self, persist_identity):
        # Kill-on-controller-exit containment also covers the tiny interval before
        # the durable identity is written. No untracked running host is released.
        self.job = quality_process._WindowsJob()
        try:
            self.process = subprocess.Popen([str(self.executable), "--no-ui"], cwd=self.executable.parent,
                                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL, creationflags=4, close_fds=True)
            self.job.assign(self.process)
            identity = self.identity(self.process.pid)
            persist_identity(identity)
            _resume_primary_thread(self.process)
        except BaseException:
            if self.process is not None and self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=5)
            self.release()
            raise

    def terminate(self, identity):
        # A held handle, plus birth/path verification, prevents PID reuse races.
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
        kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.OpenProcess(0x101001, False, identity["pid"])
        if not handle:
            if self.identity(identity["pid"]) is None:
                return
            raise ValueError("Cannot terminate owned application")
        try:
            current = self.identity(identity["pid"])
            if current is None:
                return
            if current != identity:
                raise ValueError("Owned PID identity changed; refusing termination")
            if not kernel.TerminateProcess(handle, 1) or kernel.WaitForSingleObject(handle, 5000) != 0:
                raise ValueError("Owned application termination failed")
        finally:
            kernel.CloseHandle(handle)

    def release(self):
        if self.job is not None:
            self.job.close()
            self.job = None
        if self.process is not None:
            self.process.wait(timeout=5)
            self.process = None


def protect(data, *, decrypt=False):
    """Current-user DPAPI backup, not a plaintext copy of shared credentials."""
    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]
    source_buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    api = ctypes.WinDLL("crypt32", use_last_error=True)
    function = api.CryptUnprotectData if decrypt else api.CryptProtectData
    function.argtypes = (ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob))
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ValueError("Private configuration backup protection failed")
    kernel = ctypes.WinDLL("kernel32")
    kernel.LocalFree.argtypes = (ctypes.c_void_p,)
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(target.data)


def restore_config(path, original, validate):
    """Compare and restore under one Windows handle denying other access.

    Keep the original file ACL and create no plaintext secret-bearing temporary
    copy. The encrypted durable backup survives interrupted restoration.
    """
    import msvcrt
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                  wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.CreateFileW(str(path), 0xC0000000, 0, None, 3, 0, None)  # existing, READ|WRITE, share none
    if handle == ctypes.c_void_p(-1).value:
        raise ValueError("Cannot exclusively compare/restore shared Kikitan config")
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDWR | os.O_BINARY)
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    with os.fdopen(descriptor, "r+b") as target:
        validate(target.read())
        target.seek(0)
        target.write(original)
        target.truncate()
        target.flush()
        os.fsync(target.fileno())
