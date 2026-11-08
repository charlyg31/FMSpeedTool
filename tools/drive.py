"""Outil de dev : pilote ePSXe (touches) et prend des captures.

python tools/drive.py shot NOM                -> captures/NOM.png
python tools/drive.py keys "X X START" [NOM]  -> appuie puis capture
Touches ePSXe (config du PC) : X=x, O=c, CARRE=s, TRIANGLE=d, START=entree,
SELECT=espace, fleches, L1=w, R1=r, L2=e, R2=t, F1/F3 = sauver/charger etat.
"""

import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fm_speedtool"))
import cv2  # noqa: E402

from capture import WindowCapture, user32  # noqa: E402

SC = {"LEFT": (0x4B, True), "RIGHT": (0x4D, True), "UP": (0x48, True), "DOWN": (0x50, True),
      "X": (0x2D, False), "O": (0x2E, False), "SQ": (0x1F, False), "TRI": (0x20, False),
      "START": (0x1C, False), "SELECT": (0x39, False), "L1": (0x11, False),
      "R1": (0x13, False), "L2": (0x12, False), "R2": (0x14, False),
      "F1": (0x3B, False), "F3": (0x3D, False), "ESC": (0x01, False), "F4": (0x3E, False)}

KEYEVENTF_SCANCODE = 0x8
KEYEVENTF_KEYUP = 0x2
KEYEVENTF_EXTENDEDKEY = 0x1


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _U)]


def send_scan(code, ext, up):
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_EXTENDEDKEY if ext else 0) | (KEYEVENTF_KEYUP if up else 0)
    inp = INPUT(type=1)
    inp.ki = KEYBDINPUT(0, code, flags, 0, 0)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def press(name, hold=0.08):
    code, ext = SC[name]
    send_scan(code, ext, False)
    time.sleep(hold)
    send_scan(code, ext, True)


def focus(cap):
    cap.ensure_window()
    user32.SetForegroundWindow(cap.hwnd)
    time.sleep(0.2)


def shot(cap, name):
    os.makedirs("captures", exist_ok=True)
    img = cap.grab()
    if img is None:
        print("pas de fenetre ePSXe")
        return
    path = os.path.join("captures", name + ".png")
    cv2.imwrite(path, img)
    cv2.imwrite(os.path.join("captures", name + "_s.png"), cv2.resize(img, (480, 384), interpolation=cv2.INTER_AREA))
    print(path, img.shape, cap.method)


def main():
    cap = WindowCapture()
    cmd = sys.argv[1]
    if cmd == "shot":
        shot(cap, sys.argv[2])
    elif cmd == "keys":
        focus(cap)
        for tok in sys.argv[2].split():
            if tok.startswith("w"):
                time.sleep(float(tok[1:]))
                continue
            name, _, rep = tok.partition("*")
            for _ in range(int(rep or 1)):
                press(name)
                time.sleep(0.15)
        if len(sys.argv) > 3:
            time.sleep(0.5)
            shot(cap, sys.argv[3])


if __name__ == "__main__":
    main()
