"""Verifie la lecture (HUD, ecrans) pour des fenetres ePSXe de tailles et de
formats differents, a partir des captures reelles.

python tools/size_check.py
"""

import os
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
import cv2  # noqa: E402
import numpy as np  # noqa: E402

import vision  # noqa: E402

ASSETS = os.path.join(ROOT, "fm_speedtool", "assets")
# (nom, taille de la zone de jeu, bandes noires gauche/droite, haut/bas)
VARIANTS = [
    ("1920x1536 (actuel)", (1920, 1536), 0, 0),
    ("640x480", (640, 480), 0, 0),
    ("800x600", (800, 600), 0, 0),
    ("1024x768", (1024, 768), 0, 0),
    ("1280x960", (1280, 960), 0, 0),
    ("2560x1920", (2560, 1920), 0, 0),
    ("16:9 bandes laterales", (1440, 1080), 240, 0),
    ("4:3 dans 5:4 (bandes haut/bas)", (1280, 960), 0, 64),
]


def variant(img, size, side, top):
    game = cv2.resize(img, size, interpolation=cv2.INTER_AREA if size[0] < img.shape[1] else cv2.INTER_LINEAR)
    return cv2.copyMakeBorder(game, top, top, side, side, cv2.BORDER_CONSTANT, value=(0, 0, 0))


def check(make_prepare):
    """make_prepare() -> fonction image -> image normalisee (une par format,
    pour garder l'etat de la detection d'un ecran a l'autre comme en vrai)."""
    digits = vision.DigitReader(os.path.join(tempfile.mkdtemp(), "d.json"),
                                os.path.join(ASSETS, "digits_default.json"))
    lib = vision.TemplateLibrary(os.path.join(ASSETS, "builtin"))
    hud_img = cv2.imread(os.path.join(ROOT, "captures", "live1.png"))
    screens = {"title_newgame": "title1.png", "password_screen": "password.png",
               "orient_back": "d1.png", "new_run": "ng2.png"}
    # Ecran d'orientation (dos de carte) : detecteurs dedies, pas des gabarits.
    special = {"orient_back": lambda f: vision.orient_arrows(f) >= 0.65 and vision.card_back(f) >= 0.75}
    ok_all = True
    for name, size, side, top in VARIANTS:
        prepare_frame = make_prepare()
        prepare_frame(variant(cv2.imread(os.path.join(ROOT, "captures", "title1.png")), size, side, top))
        frame = prepare_frame(variant(hud_img, size, side, top))
        hud = {k: digits.read(frame, k) for k in vision.HUD_CELLS}
        good_hud = hud == {"com_lp": 8000, "com_deck": 40, "you_deck": 35, "you_lp": 8000}
        found = []
        for action, file in screens.items():
            f = prepare_frame(variant(cv2.imread(os.path.join(ROOT, "captures", file)), size, side, top))
            found.append(special[action](f) if action in special else
                         any(t.action == action for t in lib.matching(f)))
        ok = good_hud and all(found)
        ok_all &= ok
        print(f"{name:32s} HUD {'OK' if good_hud else hud}  ecrans {sum(found)}/{len(found)}  {'OK' if ok else 'ECHEC'}")
    return ok_all


def with_area():
    area = vision.GameArea()
    return lambda f: vision.normalize(area.crop(f))


if __name__ == "__main__":
    print("== sans recadrage (avant)")
    check(lambda: vision.normalize)
    print("== avec detection de la zone de jeu")
    sys.exit(0 if check(with_area) else 1)
