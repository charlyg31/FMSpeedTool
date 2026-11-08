"""Lit les messages OutputDebugString (comme DebugView) : LiveSplit y ecrit les
erreurs de compilation et les messages des scripts .asl.

python tools/dbwin.py SECONDES FICHIER_SORTIE
"""

import ctypes
import ctypes.wintypes as wt
import struct
import sys
import time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateEventW.restype = wt.HANDLE
k32.CreateFileMappingW.restype = wt.HANDLE
k32.MapViewOfFile.restype = ctypes.c_void_p
k32.CreateFileMappingW.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.DWORD, wt.LPCWSTR]
k32.MapViewOfFile.argtypes = [wt.HANDLE, wt.DWORD, wt.DWORD, wt.DWORD, ctypes.c_size_t]
k32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
k32.SetEvent.argtypes = [wt.HANDLE]

buffer_ready = k32.CreateEventW(None, False, False, "DBWIN_BUFFER_READY")
data_ready = k32.CreateEventW(None, False, False, "DBWIN_DATA_READY")
mapping = k32.CreateFileMappingW(wt.HANDLE(-1), None, 0x04, 0, 4096, "DBWIN_BUFFER")
view = k32.MapViewOfFile(mapping, 0x0004, 0, 0, 4096)

end = time.time() + float(sys.argv[1])
with open(sys.argv[2], "w", encoding="utf-8") as out:
    while time.time() < end:
        k32.SetEvent(buffer_ready)
        if k32.WaitForSingleObject(data_ready, 500) != 0:
            continue
        raw = ctypes.string_at(view, 4096)
        pid = struct.unpack("<I", raw[:4])[0]
        text = raw[4:].split(b"\0", 1)[0].decode("mbcs", "replace").rstrip()
        out.write(f"{pid}: {text}\n")
        out.flush()
