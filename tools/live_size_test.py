"""Test en direct : relance ePSXe avec plusieurs tailles de fenetre (reglage
GPUWinSize), charge la sauvegarde d'etat (duel) et verifie la lecture du HUD.
Le reglage d'origine est toujours remis a la fin.

python tools/live_size_test.py 800x600 1024x768
"""

import os
import subprocess
import sys
import tempfile
import time
import winreg

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
sys.path.insert(0, os.path.dirname(__file__))
import cv2  # noqa: E402

import capture  # noqa: E402
import drive  # noqa: E402
import vision  # noqa: E402

EPSXE = os.environ.get("EPSXE_DIR", r"C:\ePSXe")   # dossier d'ePSXe
GAME = os.path.join(EPSXE, "jeux", "YGOFM Vanilla (15 Card Mod).cue")
KEY = r"Software\epsxe\config"


def get_size():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as k:
        return winreg.QueryValueEx(k, "GPUWinSize")[0]


def set_size(value):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, "GPUWinSize", 0, winreg.REG_SZ, str(value))


def restart_epsxe():
    subprocess.run(["taskkill", "/IM", "ePSXe.exe", "/F"], capture_output=True)
    time.sleep(1.5)
    subprocess.Popen([os.path.join(EPSXE, "ePSXe.exe"), "-nogui", "-loadbin", GAME], cwd=EPSXE)
    time.sleep(9)


def read_duel():
    cap = capture.WindowCapture()
    cap.ensure_window()
    drive.focus(cap)
    drive.press("F3")
    time.sleep(3.5)
    area = vision.GameArea()
    raw = img = None
    for _ in range(15):
        raw = cap.grab()
        if raw is not None:
            img = vision.normalize(area.crop(raw))
        time.sleep(0.05)
    digits = vision.DigitReader(os.path.join(tempfile.mkdtemp(), "d.json"),
                                os.path.join(ROOT, "fm_speedtool", "assets", "digits_default.json"))
    return raw, img, {k: digits.read(img, k) for k in vision.HUD_CELLS}


original = get_size()
try:
    for arg in sys.argv[1:]:
        w, h = (int(v) for v in arg.split("x"))
        set_size((h << 16) | w)
        restart_epsxe()
        raw, img, hud = read_duel()
        cv2.imwrite(os.path.join(ROOT, "captures", f"live_{arg}_s.png"), cv2.resize(img, (320, 256)))
        print(f"reglage {arg} -> fenetre {raw.shape[1]}x{raw.shape[0]}  HUD {hud}  tour {vision.active_player(img)}")
finally:
    set_size(original)
    restart_epsxe()
    print("reglage d'origine remis :", get_size())
