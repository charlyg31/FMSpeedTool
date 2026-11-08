"""Rejoue les images extraites d'une video de run dans le Tracker.

python tools/replay_video.py DOSSIER [debut] [fin]
Affiche chaque evenement (avec l'indice d'image) et les splits LiveSplit reels.
"""

import csv
import os
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
import cv2  # noqa: E402

import tracker  # noqa: E402
import vision  # noqa: E402

FPS = 4


def main(folder, start=0, end=10 ** 9):
    tmp = tempfile.mkdtemp()
    # FM_DIGITS : chiffres appris pour cette source (ex. console), sinon ceux livres.
    digits = vision.DigitReader(os.path.join(tmp, "d.json"),
                                os.environ.get("FM_DIGITS") or
                                (os.path.join(ROOT, "fm_speedtool", "assets", "digits_ps2_default.json")
                                 if os.environ.get("FM_PS2") else None) or
                                os.path.join(ROOT, "fm_speedtool", "assets", "digits_default.json"))
    builtin = vision.TemplateLibrary(os.path.join(ROOT, "fm_speedtool", "assets", "builtin"))
    learned = vision.TemplateLibrary(os.path.join(tmp, "learned"))
    state = {"i": 0}

    def on_event(kind, msg):
        print(f"{state['i']:6d} {state['i'] / FPS / 60:6.1f}min  {kind:10s} {msg}")
        if msg.startswith(("Victoire", "Defaite")):
            print("        stats:", tr.rank_stats())

    tr = tracker.Tracker(digits, builtin, learned, on_event)
    if os.environ.get("FM_PS2"):
        # Mode PS2 : chiffres PS2 livres + calage automatique du cadrage.
        tr.framing = vision.Framing(os.path.join(ROOT, "fm_speedtool", "assets", "hud_ref.png"))
    real = {}
    with open(os.path.join(folder, "index.csv")) as f:
        prev = None
        for r in csv.DictReader(f):
            v = int(r["split_row"])
            if v != -1 and prev is not None and v != prev:
                real[int(r["i"])] = v
            if v != -1:
                prev = v
    i = start
    while i < end:
        img = cv2.imread(os.path.join(folder, "frames", f"{i:06d}.jpg"))
        if img is None:
            break
        state["i"] = i
        if i in real:
            print(f"{i:6d} {i / FPS / 60:6.1f}min  ---------- SPLIT LIVESPLIT REEL")
        tr.process(img, now=i / FPS, normalized=True)
        i += 1


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], *(int(x) for x in a[1:]))
