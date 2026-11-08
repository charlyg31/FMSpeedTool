"""Depuis le menu (curseur sur BUILD DECK) : entre dans le deck, va a la derniere
page (R1), descend le curseur ligne par ligne jusqu'en bas (+ 2 appuis de plus) et
capture l'ecran apres chaque appui, puis ressort.

python tools/deck_bottom_check.py SORTIE.png
"""

import os
import sys
import time

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
sys.path.insert(0, os.path.dirname(__file__))
import cv2  # noqa: E402
import numpy as np  # noqa: E402

import capture  # noqa: E402
import deckscreen as ds  # noqa: E402
import drive  # noqa: E402
import vision  # noqa: E402

assets = os.path.join(ROOT, "fm_speedtool", "assets")
lib = vision.TemplateLibrary(os.path.join(assets, "builtin"))
reader = ds.DeckReader(assets)
cap = capture.WindowCapture()
area = vision.GameArea()


def img():
    while True:
        f = cap.grab()
        if f is not None:
            return vision.normalize(area.crop(f))
        time.sleep(0.05)


def on(name, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        im = img()
        if name in {t.action for t in lib.matching(im, vision.prepare(im))}:
            return True
        time.sleep(0.1)
    return False


cap.ensure_window()
if not on("game_menu", 3):
    sys.exit("le jeu n'est pas sur le menu : rien n'est fait")
drive.focus(cap)
time.sleep(1.0)
for _ in range(3):
    drive.press("X")
    if on("chest_screen", 3):
        break
else:
    sys.exit("coffre pas atteint")
time.sleep(1.0)
for _ in range(3):
    drive.press("RIGHT")
    if on("deck_screen", 2):
        break
else:
    sys.exit("deck pas atteint")
time.sleep(1.0)
for _ in range(4):
    drive.press("R1")
    time.sleep(1.0)
shots = []
for step in range(10):                       # 7 lignes jusqu'en bas + 3 de plus
    im = img()
    hl = ds.deck_highlight(im)
    rows = ds.deck_rows(im, reader.deck_digits)
    pos = rows.get(hl, (None,))[0] if hl is not None else None
    print(f"appui {step} : curseur sur la position {pos}, page {min((p for p, _ in rows.values()), default=None)}-"
          f"{max((p for p, _ in rows.values()), default=None)}")
    shots.append(cv2.resize(im, (320, 256)))
    drive.press("DOWN")
    time.sleep(0.7)
drive.press("O")
time.sleep(1.5)
while len(shots) % 5:
    shots.append(np.zeros_like(shots[0]))
cv2.imwrite(sys.argv[1], np.vstack([np.hstack(shots[i:i + 5]) for i in range(0, len(shots), 5)]))
