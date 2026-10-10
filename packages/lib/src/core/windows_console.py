"""Small ConPTY host using Windows 10/11 system APIs, without a PTY runtime.

Follows https://learn.microsoft.com/windows/console/creating-a-pseudoconsole-session
Drain output on its own thread, including while ClosePseudoConsole tears down.
"""
import codecs
import ctypes
from ctypes import wintypes as w
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading


class COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]


class STARTUPINFO(ctypes.Structure):
    _fields_ = [("cb", w.DWORD), ("lpReserved", w.LPWSTR), ("lpDesktop", w.LPWSTR),
                ("lpTitle", w.LPWSTR), ("dwX", w.DWORD), ("dwY", w.DWORD),
                ("dwXSize", w.DWORD), ("dwYSize", w.DWORD), ("dwXCountChars", w.DWORD),
                ("dwYCountChars", w.DWORD), ("dwFillAttribute", w.DWORD),
                ("dwFlags", w.DWORD), ("wShowWindow", w.WORD), ("cbReserved2", w.WORD),
                ("lpReserved2", ctypes.c_void_p), ("hStdInput", w.HANDLE),
                ("hStdOutput", w.HANDLE), ("hStdError", w.HANDLE)]


class STARTUPINFOEX(ctypes.Structure):
    _fields_ = [("StartupInfo", STARTUPINFO), ("lpAttributeList", ctypes.c_void_p)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", w.HANDLE), ("hThread", w.HANDLE),
                ("dwProcessId", w.DWORD), ("dwThreadId", w.DWORD)]


def kernel32():
    if sys.platform != "win32":
        raise OSError("ConPTY requires Windows")
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreatePipe": (w.BOOL, [ctypes.POINTER(w.HANDLE), ctypes.POINTER(w.HANDLE), ctypes.c_void_p, w.DWORD]),
        "CreatePseudoConsole": (ctypes.c_long, [COORD, w.HANDLE, w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]),
        "ClosePseudoConsole": (None, [w.HANDLE]),
        "InitializeProcThreadAttributeList": (w.BOOL, [ctypes.c_void_p, w.DWORD, w.DWORD, ctypes.POINTER(ctypes.c_size_t)]),
        "UpdateProcThreadAttribute": (w.BOOL, [ctypes.c_void_p, w.DWORD, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p]),
        "DeleteProcThreadAttributeList": (None, [ctypes.c_void_p]),
        "CreateProcessW": (w.BOOL, [w.LPCWSTR, w.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, w.BOOL, w.DWORD, ctypes.c_void_p, w.LPCWSTR, ctypes.POINTER(STARTUPINFOEX), ctypes.POINTER(PROCESS_INFORMATION)]),
        "ReadFile": (w.BOOL, [w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.c_void_p]),
        "WriteFile": (w.BOOL, [w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.c_void_p]),
        "CloseHandle": (w.BOOL, [w.HANDLE]),
        "WaitForSingleObject": (w.DWORD, [w.HANDLE, w.DWORD]),
        "TerminateProcess": (w.BOOL, [w.HANDLE, w.UINT]),
    }
    for name, (restype, args) in signatures.items():
        function = getattr(api, name)
        function.restype = restype
        function.argtypes = args
    return api


def available():
    try:
        kernel32()
        return True
    except (OSError, AttributeError):
        return False


class PtyProcess:
    def __init__(self, argv, dimensions=(80, 120)):
        self.api = kernel32()
        self.output = queue.Queue()
        self.input_read, self.input_write = w.HANDLE(), w.HANDLE()
        self.output_read, self.output_write = w.HANDLE(), w.HANDLE()
        self.console = w.HANDLE()
        self.process = PROCESS_INFORMATION()
        self.reader = None
        self.closed = False
        try:
            self.check(self.api.CreatePipe(ctypes.byref(self.input_read), ctypes.byref(self.input_write), None, 0))
            self.check(self.api.CreatePipe(ctypes.byref(self.output_read), ctypes.byref(self.output_write), None, 0))
            hr = self.api.CreatePseudoConsole(COORD(dimensions[1], dimensions[0]),
                self.input_read, self.output_write, 0, ctypes.byref(self.console))
            if hr < 0:
                raise OSError(f"CreatePseudoConsole failed: 0x{hr & 0xffffffff:08x}")
            self.reader = threading.Thread(target=self.drain, daemon=True)
            self.reader.start()
            size = ctypes.c_size_t()
            self.api.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
            attributes = ctypes.create_string_buffer(size.value)
            self.check(self.api.InitializeProcThreadAttributeList(attributes, 1, 0, ctypes.byref(size)))
            try:
                # This API takes the HPCON value, not a pointer to the handle.
                self.check(self.api.UpdateProcThreadAttribute(attributes, 0, 0x00020016,
                    self.console, ctypes.sizeof(self.console), None, None))
                startup = STARTUPINFOEX()
                startup.StartupInfo.cb = ctypes.sizeof(startup)
                # Force fresh console handles instead of duplicating redirected
                # parent stdio (the CLI helper itself has captured stdout).
                # https://github.com/microsoft/terminal/discussions/15814
                startup.StartupInfo.dwFlags = 0x00000100  # STARTF_USESTDHANDLES; null handles
                startup.lpAttributeList = ctypes.addressof(attributes)
                command = subprocess.list2cmdline(argv)
                if Path(argv[0]).suffix.lower() in (".cmd", ".bat"):
                    command = subprocess.list2cmdline([os.environ.get("COMSPEC", "cmd.exe")]) + ' /d /s /c "' + command + '"'
                self.check(self.api.CreateProcessW(None, ctypes.create_unicode_buffer(command),
                    None, None, False, 0x00080000, None, None, ctypes.byref(startup), ctypes.byref(self.process)))
            finally:
                self.api.DeleteProcThreadAttributeList(attributes)
            self.close_handle(self.input_read)
            self.close_handle(self.output_write)
            self.close_handle(w.HANDLE(self.process.hThread))
            self.process.hThread = None
        except Exception:
            self.close(force=True)
            raise

    @classmethod
    def spawn(cls, argv, dimensions=(80, 120)):
        return cls(argv, dimensions)

    @staticmethod
    def check(result):
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())

    def close_handle(self, handle):
        if handle.value:
            self.api.CloseHandle(handle)
            handle.value = None

    def drain(self):
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        buffer = ctypes.create_string_buffer(4096)
        count = w.DWORD()
        try:
            while self.api.ReadFile(self.output_read, buffer, len(buffer), ctypes.byref(count), None) and count.value:
                self.output.put(decoder.decode(buffer.raw[:count.value]))
            tail = decoder.decode(b"", final=True)
            if tail:
                self.output.put(tail)
        finally:
            self.output.put(None)

    def read(self, timeout=0.1):
        try:
            value = self.output.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError from None
        if value is None:
            raise EOFError
        return value

    def write(self, text):
        payload = text.encode("utf-8")
        count = w.DWORD()
        self.check(self.api.WriteFile(self.input_write, payload, len(payload), ctypes.byref(count), None))
        return count.value

    def isalive(self):
        return bool(self.process.hProcess) and self.api.WaitForSingleObject(self.process.hProcess, 0) == 258

    def close(self, force=False):
        if self.closed:
            return
        self.closed = True
        self.close_handle(self.input_write)
        if force and self.isalive():
            self.api.TerminateProcess(self.process.hProcess, 1)
            self.api.WaitForSingleObject(self.process.hProcess, 1000)
        if self.console.value:
            # The reader keeps draining while the console closes its process tree.
            self.api.ClosePseudoConsole(self.console)
            self.console.value = None
        self.close_handle(self.input_read)
        self.close_handle(self.output_write)
        if self.reader:
            self.reader.join(timeout=2)
        self.close_handle(self.output_read)
        self.close_handle(w.HANDLE(self.process.hThread))
        self.close_handle(w.HANDLE(self.process.hProcess))
        self.process.hThread = self.process.hProcess = None
