"""Lecture du deck a la cadence reelle de la video (comme en direct), sur les
passages par les ecrans DECK/CHEST reperes dans les images a 4/s.

python tools/deck_check_full.py VIDEO DOSSIER_4FPS X Y W H [PS2] > log
Ecrit, a la fin de chaque visite, le deck reconstitue (numeros) + les evenements.
"""

import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
import cv2  # noqa: E402
import numpy as np  # noqa: E402

import deckscreen as ds  # noqa: E402
import vision  # noqa: E402


def main(video, folder, x, y, w, h, ps2=False):
    assets = os.path.join(ROOT, "fm_speedtool", "assets")
    lib = vision.TemplateLibrary(os.path.join(assets, "builtin"))
    framing = vision.Framing(os.path.join(assets, "hud_ref.png")) if ps2 else None
    # 1) ecrans de deck reperes a 4 images/s
    names = sorted(os.listdir(os.path.join(folder, "frames")))
    deck_idx = set()
    for n in names:
        im = cv2.imread(os.path.join(folder, "frames", n))
        if framing is not None:
            if not framing.locked:
                framing.calibrate(im)
            im = framing.apply(im)
        acts = {t.action for t in lib.matching(im, vision.prepare(im))}
        if "deck_screen" in acts or "chest_screen" in acts:
            deck_idx.add(int(n[:6]))
    print(len(deck_idx), "images de deck a 4/s", flush=True)
    # 2) relecture a pleine cadence sur ces passages
    reader = ds.DeckReader(assets)
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    k, last = 0, None
    vh, vw = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    while True:
        i4 = int(k / fps * 4)
        near = any(j in deck_idx for j in range(i4 - 2, i4 + 3))
        if not near:
            ok = cap.grab()
            k += 1
            if not ok:
                break
            if last:
                n, comp = reader.watcher.summary()
                counts, dark_hole, equips = reader.f6()
                f6 = {k: v for k, v in counts.items() if v}
                print(f"{i4:6d} fin de visite : {n}/40 complet={comp} F6={f6} equips={equips} "
                      f"deck={sorted(reader.watcher.cards())}", flush=True)
                last = None
            reader.frame(None, None) if False else reader.watcher.other_frame()
            continue
        ok, frame = cap.read()
        k += 1
        if not ok:
            break
        pad = np.zeros((h, w, 3), np.uint8)
        a, b = max(0, y), min(vh, y + h)
        pad[a - y:b - y] = frame[a:b, x:x + w]
        img = vision.normalize(pad)
        if framing is not None:
            img = framing.apply(img)
        acts = {t.action for t in lib.matching(img, vision.prepare(img))}
        screen = "deck" if "deck_screen" in acts else "chest" if "chest_screen" in acts else None
        for kind, card in reader.frame(screen, img):
            print(f"{i4:6d} {kind} {card}", flush=True)
        last = last or screen
    cap.release()


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], *(int(v) for v in a[2:6]), ps2=len(a) > 6)
