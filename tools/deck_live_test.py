"""Test en direct de la lecture du deck sur ePSXe : le moteur tourne a 60 img/s
pendant qu'on fait defiler le deck rapidement, puis on relit lentement chaque
page pour la verite terrain.

Depart : ecran CHEST de BUILD DECK (le deck est a droite).
python tools/deck_live_test.py [delai_entre_touches_s]
"""

import os
import sys
import tempfile
import threading
import time

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
sys.path.insert(0, os.path.dirname(__file__))
import cv2  # noqa: E402

import capture  # noqa: E402
import deckscreen as ds  # noqa: E402
import drive  # noqa: E402
import tracker  # noqa: E402
import vision  # noqa: E402

GAP = float(sys.argv[1]) if len(sys.argv) > 1 else 0.05
assets = os.path.join(ROOT, "fm_speedtool", "assets")
tmp = tempfile.mkdtemp()
digits = vision.DigitReader(os.path.join(tmp, "d.json"), os.path.join(assets, "digits_default.json"))
reader = ds.DeckReader(assets)
events = []
tr = tracker.Tracker(digits, vision.TemplateLibrary(os.path.join(assets, "builtin")),
                     vision.TemplateLibrary(os.path.join(tmp, "l")),
                     lambda k, m: events.append((round(time.monotonic() - T0, 2), k, m)), deck=reader)
cap = capture.WindowCapture()
cap.ensure_window()
stop = threading.Event()
stats = {"frames": 0}
T0 = time.monotonic()


def engine():
    while not stop.is_set():
        t = time.monotonic()
        f = cap.grab()
        if f is not None:
            tr.process(f)
            stats["frames"] += 1
        time.sleep(max(0.0, 1 / 60 - (time.monotonic() - t)))


def press(k, gap=GAP):
    drive.press(k, hold=0.03)
    time.sleep(gap)


drive.focus(cap)
th = threading.Thread(target=engine, daemon=True)
th.start()
time.sleep(1.0)
press("RIGHT", 2.0)                # du coffre (CHEST) au deck, a droite
t_fast = time.monotonic()
for _ in range(42):                # defilement rapide jusqu'en bas
    press("DOWN")
time.sleep(0.6)
for _ in range(42):                # et retour en haut
    press("UP")
time.sleep(1.0)
fast_s = time.monotonic() - t_fast
stop.set()
th.join()
fps = stats["frames"] / (time.monotonic() - T0)
w = reader.watcher
fast_deck = sorted(w.cards())
print(f"moteur : {fps:.0f} img/s, defilement {fast_s:.1f} s (touche toutes les {GAP * 1000:.0f} ms)")
print("lu en defilant vite :", len(fast_deck), "cartes, complet =", w.complete, "compteur", w.count)

# Verite : relecture lente page par page (8 lignes par page)
truth = {}
for page in range(6):
    img = None
    while img is None:
        f = cap.grab()
        img = vision.normalize(tr.area.crop(f)) if f is not None else None
        time.sleep(0.2)
    rows = ds.deck_rows(img, reader.deck_digits)
    truth.update(dict(rows.values()))
    cv2.imwrite(os.path.join(ROOT, "captures", f"deck_live_p{page}.png"), img)
    for _ in range(8):
        press("DOWN", 0.12)
    time.sleep(0.5)
n = ds.deck_count(img, reader.count_digits) or 40
truth_deck = sorted(truth[p] for p in range(1, n + 1) if p in truth)
print("verite (lecture lente) :", len(truth_deck), "positions sur", n)
print("identique :", fast_deck == truth_deck)
if fast_deck != truth_deck:
    from collections import Counter
    a, b = Counter(fast_deck), Counter(truth_deck)
    print("  en trop :", dict(a - b), " manquant :", dict(b - a))
print("evenements :", [e for e in events if e[1] == "deck"][:10])
print("Final 6 :", {k: v for k, v in reader.f6()[0].items() if v}, reader.f6()[2])
