"""Video de demonstration : ePSXe + FM Speed Tool cote a cote (rien d'autre),
pendant qu'on entre dans le deck, qu'on le fait defiler (R1 toutes les 0,2 s) et
qu'on ressort. Bandeau du bas : resultat attendu (deck reel).

Depart : menu du jeu, curseur sur BUILD DECK. La vraie config n'est pas modifiee.
python tools/record_deck_video.py SORTIE.mp4
"""

import os
import sys
import threading
import time
import tkinter as tk

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
sys.path.insert(0, os.path.dirname(__file__))
import cv2  # noqa: E402
import imageio_ffmpeg  # noqa: E402
import numpy as np  # noqa: E402

import app  # noqa: E402
import capture  # noqa: E402
import drive  # noqa: E402
import fmlogic  # noqa: E402
import vision  # noqa: E402

OUT = sys.argv[1]
FPS = 10
H_PART = 640
EXPECTED = [
    "RESULTAT ATTENDU (deck reel, 40 cartes) :",
    "Dragons < 1600 : 4   Dragons 1600+ : 11   Thunder Dragon : 1   Thunders : 9",
    "Umi : 2   Widespread Ruin : 3   Megamorph : 2   Dark Hole (au lieu de Raigeki) : oui",
    "Equipements : Bright Castle 3   Dragon Treasure 3   Beast Fangs 1   Invigoration 1",
]

orig = app.load_config


def load_config():
    cfg = orig()
    cfg.update({"language": "fr", "source": "epsxe", "deck_auto": True, "dark_hole": False,
                "f6": {f: 0 for f in fmlogic.F6_FIELDS}, "equips": []})
    return cfg


app.load_config = load_config
app.App._save_config = lambda self: None          # ne touche pas a la vraie config

root = tk.Tk()
root.geometry("1440x940+0+0")
a = app.App(root)
root.attributes("-topmost", True)
frames = []
recording = threading.Event()
recording.set()


def app_hwnd():
    return int(root.wm_frame(), 16)


def recorder():
    nxt = time.monotonic()
    while recording.is_set():
        # Image du jeu : celle que le logiciel vient d'analyser (pas de seconde capture
        # d'ePSXe, qui ralentirait le logiciel).
        g = a.tracker.last_frame
        g = None if g is None else g.copy()
        s = capture._grab(app_hwnd(), False)
        if g is not None and s is not None:
            frames.append((g, s))
        nxt += 1 / FPS
        time.sleep(max(0.0, nxt - time.monotonic()))


def press(k, after):
    drive.press(k, hold=0.08)
    time.sleep(after)


def screen_is(name):
    img = a.tracker.last_frame
    return img is not None and name in {t.action for t in a.builtin.matching(img, vision.prepare(img))}


def wait_screen(name, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if screen_is(name):
            return True
        time.sleep(0.05)
    return False


def abort(msg):
    print("ARRET :", msg)
    recording.clear()
    root.after(0, finish)


def scenario():
    while not (a.f6.ready or a.f6.error):     # tableur d'Exarion charge
        time.sleep(0.2)
    if not wait_screen("game_menu", 5):
        return abort("le jeu n'est pas sur le menu")
    time.sleep(1.0)
    drive.focus(a.worker.cap)
    time.sleep(1.0)
    for _ in range(3):                        # BUILD DECK -> coffre (touche verifiee)
        press("X", 0.1)
        if wait_screen("chest_screen", 3):
            break
    else:
        return abort("coffre pas atteint")
    time.sleep(1.0)
    for _ in range(3):                        # le deck, a droite (touche verifiee)
        press("RIGHT", 0.1)
        if wait_screen("deck_screen", 2):
            break
    else:
        return abort("deck pas atteint (aucune autre touche)")
    time.sleep(0.8)
    for _ in range(5):
        press("R1", 0.12)                     # 0,08 s appuye + 0,12 s = une page toutes les 0,2 s
    time.sleep(1.2)
    press("O", 3.0)                           # on quitte le deck ; on laisse voir le resultat
    recording.clear()
    root.after(0, finish)


def compose(g, s):
    gh = cv2.resize(g, (int(g.shape[1] * H_PART / g.shape[0]), H_PART), interpolation=cv2.INTER_AREA)
    sh = cv2.resize(s, (int(s.shape[1] * H_PART / s.shape[0]), H_PART), interpolation=cv2.INTER_AREA)
    top = np.hstack([gh, sh])
    band = np.full((170, top.shape[1], 3), 30, np.uint8)
    for i, line in enumerate(EXPECTED):
        cv2.putText(band, line, (16, 36 + 38 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.85,
                    (80, 230, 255) if i == 0 else (255, 255, 255), 2, cv2.LINE_AA)
    img = np.vstack([top, band])
    h, w = img.shape[:2]
    return img[:h - h % 2, :w - w % 2]


def finish():
    a.close()
    first = compose(*frames[0])
    h, w = first.shape[:2]
    writer = imageio_ffmpeg.write_frames(OUT, (w, h), fps=FPS, codec="libx264", pix_fmt_in="bgr24",
                                         quality=7, macro_block_size=2)
    writer.send(None)
    for g, s in frames:
        writer.send(np.ascontiguousarray(compose(g, s)))
    writer.close()
    print(len(frames), "images,", f"{len(frames) / FPS:.1f} s ->", OUT)


threading.Thread(target=recorder, daemon=True).start()
threading.Thread(target=scenario, daemon=True).start()
root.mainloop()
