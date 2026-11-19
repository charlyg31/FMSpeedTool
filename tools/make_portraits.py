"""Portraits des adversaires de campagne : dernier dialogue avant chaque duel d'une run
All Duelists (YouTube NzFnsCr3ENc, images extraites par extract_any.py, x 425 y 0 855x684).

python tools/make_portraits.py DOSSIER_VIDEO
Sortie : fm_speedtool/assets/portraits/ (index.json, une image par adversaire, bande du dialogue)
"""

import json
import os
import shutil
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
import cv2  # noqa: E402

import opponents  # noqa: E402
import vision  # noqa: E402

OUT = os.path.join(ROOT, "fm_speedtool", "assets", "portraits")
BAND_FRAME = 940              # "Prepare yourself!" de Simon Muran : bande de pierre nette
# Debut de chaque duel de campagne dans la video (indice d'image a 4 img/s), adversaire.
DUELS = [
    (966, "Simon Muran"), (1400, "Teana"), (1804, "Villager 1"), (2254, "Villager 2"),
    (2738, "Villager 3"), (3320, "Jono"), (3723, "Seto"), (4440, "Heishin"),
    (4913, "Rex Raptor"), (5385, "Weevil Underwood"), (5807, "Mai Valentine"),
    (6248, "Bandit Keith"), (6981, "Shadi"), (7498, "Yami Bakura"), (8068, "Pegasus"),
    (9438, "Isis"), (10010, "Kaiba"), (10724, "Jono 2nd"), (11108, "Teana 2nd"),
    (11482, "Mage Soldier"), (12057, "Ocean Mage"), (12499, "High Mage Secmeton"),
    (12859, "Desert Mage"), (13231, "High Mage Martis"), (13723, "Forest Mage"),
    (14061, "High Mage Anubisius"), (15184, "Labyrinth Mage"), (15750, "Seto 2nd"),
    (16248, "Meadow Mage"), (16646, "High Mage Kepura"), (17087, "Mountain Mage"),
    (17410, "High Mage Atenza"), (18078, "Guardian Sebek"), (18405, "Guardian Neku"),
    (18826, "Heishin 2nd"), (19318, "Seto 3rd"), (20575, "DarkNite"), (21306, "Nitemare"),
]
SIZE = (192, 102)             # image gardee (la comparaison se fait en 48x26)


def main(folder):
    # Images recadrees comme dans le logiciel (cadrage trouve sur l'ecran titre).
    framing = vision.Framing(os.path.join(ROOT, "fm_speedtool", "assets", "hud_ref.png"), vertical=False)
    for i in range(400):
        framing.calibrate(cv2.imread(os.path.join(folder, "frames", f"{i:06d}.jpg")))
        if framing.done:
            break
    print("cadrage", framing.values())
    frame = lambda i: framing.apply(cv2.imread(os.path.join(folder, "frames", f"{i:06d}.jpg")))  # noqa: E731
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    y0, y1 = opponents.BAND_Y
    band = cv2.cvtColor(frame(BAND_FRAME)[y0 + 10:y1 - 10, 20:620], cv2.COLOR_BGR2GRAY)
    cv2.imwrite(os.path.join(OUT, "dialog_band.png"), band)
    portraits = opponents.Portraits.__new__(opponents.Portraits)
    portraits.band = band
    entries = []
    for start, name in DUELS:
        # Dernier bloc de dialogue avant le duel : sa derniere image claire (avant le fondu ;
        # le debut du bloc peut montrer le decor seul, avant l'arrivee du personnage).
        block = []
        for i in range(start, start - 600, -1):
            img = frame(i)
            if portraits.dialog(img) and img[20:opponents.SCENE_Y].mean() > 15:
                block.append((float(img[:opponents.SCENE_Y].mean()), i, img))
                if len(block) == 12:
                    break
            elif block:
                break
        top = max(b[0] for b in block)
        _b, i, img = next(b for b in block if b[0] >= 0.85 * top)   # block : de la fin au debut
        fname = f"p{len(entries):02d}.png"
        cv2.imwrite(os.path.join(OUT, fname),
                    cv2.resize(img[:opponents.SCENE_Y], SIZE, interpolation=cv2.INTER_AREA))
        entries.append({"name": name, "file": fname, "frame": i})
        print(name, i)
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[1])
