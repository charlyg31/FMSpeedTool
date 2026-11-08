"""Joue des evenements via la memoire partagee (comme FMSpeedTool.exe) et
capture la fenetre LiveSplit apres chacun, pour verifier le script .asl.

python tools/asl_test_run.py
"""

import os
import sys
import time

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
import cv2  # noqa: E402

import capture  # noqa: E402
import livesplit_bridge as lb  # noqa: E402


def shot(name):
    hw = []

    def cb(h, _):
        if capture.window_title(h).startswith("LiveSplit") and capture.user32.IsWindowVisible(h):
            hw.append(h)
        return True

    capture.user32.EnumWindows(capture.WNDENUMPROC(cb), 0)
    if not hw:
        print("fenetre LiveSplit introuvable")
        return
    capture.user32.SetForegroundWindow(hw[0])
    time.sleep(0.4)
    img = capture._grab(hw[0], False)
    cv2.imwrite(os.path.join(ROOT, "captures", f"asl_{name}.png"), img)
    print("capture", name, img.shape)


bridge = lb.Bridge()
print("memoire partagee prete ; attente que LiveSplit compile le script...")
for _ in range(15 * 10):                 # 15 s de battements
    bridge.beat()
    time.sleep(0.1)
shot("0_attente")
steps = [("1_depart", lambda: (bridge.reset(), bridge.start())),
         ("2_split_victoire", lambda: bridge.split(lb.KIND_WIN, "Rex Raptor")),
         ("3_split_ferme_ignore", lambda: bridge.split(lb.KIND_FARM)),
         ("4_split_1re_defaite", lambda: bridge.split(lb.KIND_FIRST_LOSS, "Heishin")),
         ("5_reset", lambda: bridge.reset())]
for name, action in steps:
    action()
    for _ in range(25):                  # 2,5 s
        bridge.beat()
        time.sleep(0.1)
    shot(name)
