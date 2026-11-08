"""Test de la lecture du deck sur une video : pour chaque passage sur l'ecran
DECK ou CHEST, ecrit une planche (image du jeu + ce que le logiciel lit) pour
verifier a l'oeil, et le deck reconstitue a la fin de chaque visite.

python tools/deck_check.py DOSSIER SORTIE_DIR [PS2]
"""

import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
import cv2  # noqa: E402
import numpy as np  # noqa: E402

import deckscreen as ds  # noqa: E402
import vision  # noqa: E402


def main(folder, out, ps2=False):
    os.makedirs(out, exist_ok=True)
    assets = os.path.join(ROOT, "fm_speedtool", "assets")
    lib = vision.TemplateLibrary(os.path.join(assets, "builtin"))
    reader = ds.DeckReader(assets)
    framing = vision.Framing(os.path.join(assets, "hud_ref.png")) if ps2 else None
    frames = sorted(os.listdir(os.path.join(folder, "frames")))
    visit, last_screen, shots, log = 0, None, 0, []
    for name in frames:
        img = cv2.imread(os.path.join(folder, "frames", name))
        if framing is not None:
            if not framing.locked:
                framing.calibrate(img)
            img = framing.apply(img)
        acts = {t.action for t in lib.matching(img, vision.prepare(img))}
        screen = "deck" if "deck_screen" in acts else "chest" if "chest_screen" in acts else None
        events = reader.frame(screen, img)
        i = int(name[:6])
        for kind, card in events:
            log.append(f"{i:6d} {'+' if kind == '+' else '-'} {card}")
        if screen and screen != last_screen:
            visit += 1
        if screen and shots < 400 and i % 6 == 0:
            if screen == "deck":
                rows = ds.deck_rows(img, reader.deck_digits)
                count = ds.deck_count(img, reader.count_digits)
                txt = [f"compteur {count}"] + [f"{p:02d}: {c:03d} {reader.db.name(c)[:16]}"
                                                for _, (p, c) in sorted(rows.items())]
            else:
                rows = ds.chest_rows(img, reader.chest_digits, reader.box_digits)
                txt = [f"{c:03d} coffre {a} deck {b} {reader.db.name(c)[:12]}" for c, a, b in rows.values()]
            panel = np.zeros((512, 360, 3), np.uint8)
            for k, t in enumerate(txt[:12]):
                cv2.putText(panel, t, (6, 24 + 34 * k), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            cv2.putText(panel, f"{i} visite {visit}", (6, 500), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.imwrite(os.path.join(out, f"{i:06d}_{screen}.jpg"), np.hstack([img, panel]))
            shots += 1
        if last_screen and not screen:
            n, complete = reader.watcher.summary()
            log.append(f"{i:6d} fin de visite {visit} : deck {n}/40 complet={complete} "
                       f"ajouts={len(reader.watcher.added)} retraits={len(reader.watcher.removed)}")
        last_screen = screen
    with open(os.path.join(out, "log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(log) + "\n\nDeck final :\n")
        for cid in reader.watcher.cards():
            f.write(f"  {cid:03d} {reader.db.name(cid)}\n")
    print(visit, "visites,", shots, "planches")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], len(sys.argv) > 3)
