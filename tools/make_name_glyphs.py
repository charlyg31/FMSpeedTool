"""Lettres de la police des noms (ecran Free Duel) apprises sur les noms de cartes de
l'ecran DECK : meme police, meme pas. Le numero de la ligne donne le nom de la carte
(cards.json), donc le texte de chaque case.

python tools/make_name_glyphs.py DOSSIER_VIDEO [...]   (dossiers frames/ de extract_any.py)
Sortie : fm_speedtool/assets/name_glyphs.npz
"""

import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
import cv2  # noqa: E402
import numpy as np  # noqa: E402

import deckscreen  # noqa: E402
import opponents  # noqa: E402
import vision  # noqa: E402

ASSETS = os.path.join(ROOT, "fm_speedtool", "assets")
TEXT_X, TEXT_DY = 133, 3     # texte du nom de carte dans une ligne du deck
# Ecrans Free Duel (captures/) : lettres absentes des noms de cartes (chiffres...).
FREE_DUEL_BARS = {"fd_jono2nd.jpg": "Jono 2nd"}


def main(folders):
    cards = json.load(open(os.path.join(ASSETS, "cards.json"), encoding="utf-8"))
    digits = deckscreen.Digits(os.path.join(ASSETS, "deck_digits.npz"), deckscreen.white_glyph)
    deck_tpl = [t for t in vision.TemplateLibrary(os.path.join(ASSETS, "builtin")).items
                if t.action == "deck_screen"][0]
    images = [os.path.join(ROOT, "captures", f) for f in os.listdir(os.path.join(ROOT, "captures"))
              if f.startswith("deck_live_p")]
    for folder in folders:
        frames = os.path.join(folder, "frames")
        images += [os.path.join(frames, f) for f in sorted(os.listdir(frames))[::3]]
    per_char = {}
    seen = {}
    for path in images:
        img = cv2.imread(path)
        if img is None:
            continue
        if img.shape[:2] != (vision.H, vision.W):
            img = vision.normalize(img)
        if not deck_tpl.matches(img):
            continue
        for r, (_pos, cid) in deckscreen.deck_rows(img, digits).items():
            if seen.get(cid, 0) >= 3 or str(cid) not in cards:
                continue
            seen[cid] = seen.get(cid, 0) + 1
            y = deckscreen.row_y(r) + TEXT_DY
            line = img[y:y + opponents.CELL_H, TEXT_X:TEXT_X + 200].min(axis=2)
            name = cards[str(cid)]["name"][:12]
            for k, ch in enumerate(opponents.name_cells(line, len(name))):
                if name[k] != " " and ch is not None:
                    per_char.setdefault(name[k], []).append(ch)
    for f, text in FREE_DUEL_BARS.items():
        img = vision.normalize(cv2.imread(os.path.join(ROOT, "captures", f)))
        x, y = opponents.FREE_NAME_AT
        line = img[y:y + opponents.CELL_H, x:x + 330].min(axis=2)
        for k, ch in enumerate(opponents.name_cells(line, len(text))):
            if text[k] != " " and ch is not None and text[k] not in per_char:
                per_char.setdefault(text[k] + "*", []).append(ch)
    for c in [c for c in per_char if c.endswith("*")]:
        per_char[c[0]] = per_char.pop(c)
    labels, vecs = [], []
    for c, gl in sorted(per_char.items()):
        stack = np.stack(gl)
        med = np.median(stack, axis=0)
        # Echantillons proches de la mediane seulement (lignes mal lues, curseur...).
        d = np.abs(stack - med).mean(axis=(1, 2))
        good = stack[d <= np.percentile(d, 75) + 1e-6]
        v = good.mean(axis=0)
        labels.append(c)
        vecs.append(v / (np.linalg.norm(v) + 1e-6))
        print(repr(c), len(gl))
    np.savez_compressed(os.path.join(ASSETS, "name_glyphs.npz"), labels=np.array(labels),
                        vecs=np.stack(vecs).astype(np.float32))
    print(len(labels), "lettres :", "".join(labels))


if __name__ == "__main__":
    main(sys.argv[1:])
