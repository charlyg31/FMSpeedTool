"""Verification lente du deck sur ePSXe : depuis le menu (curseur sur BUILD DECK),
entre dans le deck, passe chaque page avec R1 en prenant son temps, capture
chaque page, puis calcule les compteurs du Final 6 a partir de ces pages.

python tools/deck_slow_check.py SORTIE.png
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
import fmlogic  # noqa: E402
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
time.sleep(1.5)
pages, rows_all = [], {}
for page in range(5):
    im = img()
    pages.append(im)
    rows_all.update(dict(ds.deck_rows(im, reader.deck_digits).values()))
    if page < 4:
        drive.press("R1")
        time.sleep(1.5)
count = ds.deck_count(pages[0], reader.count_digits)
drive.press("O")
time.sleep(1.5)

deck = [rows_all[p] for p in sorted(rows_all)]
print("compteur", count, "; positions lues", len(rows_all), sorted(set(range(1, 41)) - set(rows_all)) or "")
for p in sorted(rows_all):
    print(f"  {p:02d} {rows_all[p]:03d} {reader.db.name(rows_all[p])}")
counts, dh, eq = ds.f6_counts(deck, reader.db)
print("Final 6 :", {fmlogic.F6_LABELS[k].split(' (')[0]: v for k, v in counts.items() if v},
      "| Dark Hole" if dh else "| Raigeki", "|", {e: eq.count(e) for e in dict.fromkeys(eq)})
sheet = [cv2.resize(p, (480, 384)) for p in pages] + [np.zeros((384, 480, 3), np.uint8)]
cv2.imwrite(sys.argv[1], np.vstack([np.hstack(sheet[0:3]), np.hstack(sheet[3:6])]))
