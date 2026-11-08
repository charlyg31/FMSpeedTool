"""Test en direct du mode PS2 : une fenetre "PS2 test" diffuse la zone de jeu
d'une video de run (comme un projecteur OBS de la carte d'acquisition), et le
logiciel tourne en mode PS2 sur cette fenetre, sans toucher a la vraie config.

python tools/ps2_live_test.py VIDEO X Y W H DEBUT_S DUREE_S
"""

import os
import sys
import threading
import time
import tkinter as tk

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
import cv2  # noqa: E402

import app  # noqa: E402

video, x, y, w, h, start, dur = sys.argv[1], *map(int, sys.argv[2:6]), float(sys.argv[6]), float(sys.argv[7])
TITLE = "PS2 test"
stop = threading.Event()


def player():
    cap = cv2.VideoCapture(video)
    cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    cv2.namedWindow(TITLE, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(TITLE, w, h)
    cv2.moveWindow(TITLE, 0, 0)
    cv2.setWindowProperty(TITLE, cv2.WND_PROP_TOPMOST, 1)
    t0 = time.monotonic()
    n = 0
    while not stop.is_set():
        ok, im = cap.read()
        if not ok:
            break
        cv2.imshow(TITLE, im[y:y + h, x:x + w])
        n += 1
        cv2.waitKey(max(1, int((t0 + n / fps - time.monotonic()) * 1000)))
    cv2.destroyAllWindows()


orig = app.load_config


def load_config():
    cfg = orig()
    cfg.update({"source": "ps2", "ps2_window": TITLE, "ps2_framing": None, "language": "fr"})
    return cfg


app.load_config = load_config
app.App._save_config = lambda self: None
th = threading.Thread(target=player, daemon=True)
th.start()
time.sleep(1.5)
root = tk.Tk()
root.geometry("+700+300")
a = app.App(root)


def finish():
    print("img/s:", round(a.worker.fps), "| cadrage:", a.tracker.framing.locked,
          a.tracker.framing.dy, a.tracker.framing.sy)
    print("HUD:", a.tracker.hud, "| tour:", a.tracker.active)
    print("journal:")
    for line in reversed(a.log.get(0, "end")):
        print("  ", line)
    stop.set()
    a.close()


root.after(int(dur * 1000), finish)
root.mainloop()
