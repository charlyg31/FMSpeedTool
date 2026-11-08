"""Mesure le temps de traitement d'une image (objectif 60 img/s = 16,7 ms)."""

import cProfile
import os
import pstats
import sys
import tempfile
import time

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
import cv2  # noqa: E402

import deckscreen  # noqa: E402
import tracker  # noqa: E402
import vision  # noqa: E402

tmp = tempfile.mkdtemp()
assets = os.path.join(ROOT, "fm_speedtool", "assets")
tr = tracker.Tracker(vision.DigitReader(os.path.join(tmp, "d.json"), os.path.join(assets, "digits_default.json")),
                     vision.TemplateLibrary(os.path.join(assets, "builtin")),
                     vision.TemplateLibrary(os.path.join(tmp, "l")), lambda k, m: None,
                     deck=deckscreen.DeckReader(assets))
frames = [cv2.imread(os.path.join(ROOT, "captures", f)) for f in ("st1.png", "d1.png", "title1.png", "e1.png")]
frames += [cv2.imread(os.path.join(ROOT, "captures", "video", f)) for f in ("v007940.jpg", "v007920.jpg")]

for f in frames:   # chauffe
    tr.process(f, now=0)
t0 = time.perf_counter()
n = 0
for k in range(30):
    for f in frames:
        tr.process(f, now=k)
        n += 1
dt = (time.perf_counter() - t0) / n * 1000
print(f"traitement : {dt:.1f} ms / image  ({1000 / dt:.0f} img/s possibles)")
if "-p" in sys.argv:
    pr = cProfile.Profile()
    pr.enable()
    for k in range(10):
        for f in frames:
            tr.process(f, now=k)
    pr.disable()
    pstats.Stats(pr).sort_stats("cumulative").print_stats(18)
