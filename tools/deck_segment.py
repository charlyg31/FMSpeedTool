"""Lit un passage de video a pleine cadence avec le lecteur de deck et affiche le
deck reconstitue et les compteurs du Final 6.

python tools/deck_segment.py VIDEO X Y W H DEBUT_S FIN_S [dy sy]
dy sy : cadrage PS2 a appliquer (sinon aucun).
"""

import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
import cv2  # noqa: E402
import numpy as np  # noqa: E402

import deckscreen as ds  # noqa: E402
import vision  # noqa: E402

a = sys.argv[1:]
video, x, y, w, h = a[0], *map(int, a[1:5])
t0, t1 = float(a[5]), float(a[6])
assets = os.path.join(ROOT, "fm_speedtool", "assets")
framing = None
if len(a) > 8:
    framing = vision.Framing(os.path.join(assets, "hud_ref.png"), float(a[7]), float(a[8]), locked=True)
lib = vision.TemplateLibrary(os.path.join(assets, "builtin"))
reader = ds.DeckReader(assets)
cap = cv2.VideoCapture(video)
cap.set(cv2.CAP_PROP_POS_MSEC, t0 * 1000)
vh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
n_deck = 0
while cap.get(cv2.CAP_PROP_POS_MSEC) < t1 * 1000:
    ok, f = cap.read()
    if not ok:
        break
    pad = np.zeros((h, w, 3), np.uint8)
    lo, hi = max(0, y), min(vh, y + h)
    pad[lo - y:hi - y] = f[lo:hi, x:x + w]
    img = vision.normalize(pad)
    if framing is not None:
        img = framing.apply(img)
    acts = {t.action for t in lib.matching(img, vision.prepare(img))}
    screen = "deck" if "deck_screen" in acts else "chest" if "chest_screen" in acts else None
    n_deck += screen == "deck"
    for kind, card in reader.frame(screen, img):
        print("  evenement", kind, card)
w_ = reader.watcher
print(f"images DECK reconnues : {n_deck} ; compteur {w_.count} ; complet {w_.complete} ; "
      f"positions lues {len(w_.slots)}")
counts, dh, eq = reader.f6()
print("Final 6 :", {k: v for k, v in counts.items() if v}, "Dark Hole" if dh else "", eq)
for p in sorted(w_.slots):
    print(f"  {p:02d} {w_.slots[p]:03d} {reader.db.name(w_.slots[p])}")
