"""Planche : rang estime (journal du rejeu) a cote du badge de rang affiche par le jeu.

python tools/rank_check.py DOSSIER JOURNAL SORTIE.png
"""

import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
import cv2  # noqa: E402
import numpy as np  # noqa: E402

import vision  # noqa: E402

BADGE = (370, 255, 200, 110)  # POW/TEC + lettre du rang (ecran RESULTS OF DUEL)


def main(folder, log, out):
    lib = vision.TemplateLibrary(os.path.join(ROOT, "fm_speedtool", "assets", "builtin"))
    winner = [t for t in lib.items if t.action in ("winner_you", "winner_com")]
    rows = []
    for line in open(log, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*(\d+)\s+[\d.]+min\s+info\s+(Victoire|Defaite)(.*)", line)
        if not m:
            continue
        i = int(m.group(1))
        est = re.search(r"rang estime (\S+) \((\d+)\)", line)
        label = f"{i} {est.group(1)} {est.group(2)}" if est else f"{i} {m.group(2)}"
        badge = None
        for j in range(i, i + 80):
            img = cv2.imread(os.path.join(folder, "frames", f"{j:06d}.jpg"))
            if img is not None and any(t.matches(img) for t in winner):
                badge = vision.crop(cv2.imread(os.path.join(folder, "frames", f"{j + 2:06d}.jpg")), BADGE)
                break
        if badge is None:
            badge = np.zeros((BADGE[3], BADGE[2], 3), np.uint8)
        tile = np.zeros((BADGE[3], BADGE[2] + 230, 3), np.uint8)
        tile[:, :BADGE[2]] = badge
        cv2.putText(tile, label, (BADGE[2] + 5, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
        rows.append(tile)
    half = (len(rows) + 1) // 2
    left, right = rows[:half], rows[half:]
    while len(right) < len(left):
        right.append(np.zeros_like(left[0]))
    cv2.imwrite(out, np.vstack([np.hstack(p) for p in zip(left, right)]))
    print(len(rows), "duels")


if __name__ == "__main__":
    main(*sys.argv[1:4])
