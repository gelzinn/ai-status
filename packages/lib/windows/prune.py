"""Keep one copy of the newest compatible MSVC 14 runtime in _internal.

PySide/shiboken/Python wheels carry different minor versions. MSVC 14 runtimes
are backwards compatible; choose by file version, not filename or file size.
Windows 10/11 supply the Universal CRT themselves.
"""
import ctypes as C
from pathlib import Path
import shutil
import sys

runtime = Path(sys.argv[1]).resolve() / "_internal"
api = C.WinDLL("version", use_last_error=True)
api.GetFileVersionInfoSizeW.argtypes = [C.c_wchar_p, C.POINTER(C.c_uint32)]
api.GetFileVersionInfoSizeW.restype = C.c_uint32
api.GetFileVersionInfoW.argtypes = [C.c_wchar_p, C.c_uint32, C.c_uint32, C.c_void_p]
api.GetFileVersionInfoW.restype = C.c_int32
api.VerQueryValueW.argtypes = [C.c_void_p, C.c_wchar_p, C.POINTER(C.c_void_p), C.POINTER(C.c_uint32)]
api.VerQueryValueW.restype = C.c_int32


def version(path):
    size = api.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        raise RuntimeError(f"Cannot read runtime version: {path.name}")
    buffer = C.create_string_buffer(size)
    pointer, length = C.c_void_p(), C.c_uint32()
    if (not api.GetFileVersionInfoW(str(path), 0, size, buffer)
            or not api.VerQueryValueW(buffer, "\\", C.byref(pointer), C.byref(length))
            or length.value < 52):
        raise RuntimeError(f"Cannot read runtime version: {path.name}")
    info = C.cast(pointer, C.POINTER(C.c_uint32))
    return info[2] >> 16, info[2] & 65535, info[3] >> 16, info[3] & 65535


families = {}
for path in runtime.rglob("*.dll"):
    name = path.name.lower()
    if name.startswith(("vcruntime140", "msvcp140")) or name == "concrt140.dll":
        families.setdefault(name, []).append(path)
for name, copies in sorted(families.items()):
    versions = [(version(path), path) for path in copies]
    if any(value[0] != 14 for value, _ in versions):
        raise RuntimeError(f"Unexpected MSVC runtime major version: {name}")
    newest_version, newest = max(versions, key=lambda item: item[0])
    destination = runtime / name
    if newest != destination:
        shutil.copy2(newest, destination)
    for path in copies:
        if path != destination:
            path.unlink()
    print(f"{name}: shared {'.'.join(map(str, newest_version))} ({len(copies)} input copies)")
