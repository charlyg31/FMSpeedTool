"""Genere les gabarits integres a partir des captures faites sur ePSXe."""

import os
import shutil
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
import cv2  # noqa: E402
import numpy as np  # noqa: E402

import vision  # noqa: E402

OUT = os.path.join(ROOT, "fm_speedtool", "assets", "builtin")

SPECS = [
    # (capture, nom, action, rect) ; "video/..." = image extraite de la video de run
    ("ng2", "Nouvelle partie (Input your NAME!)", "new_run", (110, 385, 260, 30)),
    ("d1", "Orientation : fleche gauche", "orient_left", (217, 247, 26, 28), 90),
    ("d1", "Orientation : fleche droite", "orient_right", (390, 247, 26, 28), 90),
    ("d1", "Orientation : dos de carte", "orient_back", (272, 185, 96, 140), 90),
    ("title1", "Titre : NEW GAME surligne", "title_newgame", (215, 62, 210, 66)),
    ("video/v000276", "Titre : NEW GAME surligne (video)", "title_newgame", (215, 62, 210, 66)),
    ("video/v001060", "Ecran Free Duel", "free_duel", (170, 25, 300, 35)),
    ("video/v001528", "YOU WIN!", "you_win", (170, 80, 280, 190)),
    ("video/v002340", "YOU LOSE", "you_lose", (150, 80, 330, 200)),
    ("video/v001060", "Duel Master K", "opponent", (25, 428, 230, 34)),
    ("video/v014957", "Pegasus", "opponent", (25, 428, 230, 34)),
    ("video/v013141", "Isis", "opponent", (25, 428, 230, 34)),
    ("video/v007890", "Pegasus", "opponent", (100, 40, 150, 200), 90),  # portrait qui glisse
    ("video/v002342", "RESULTS OF DUEL", "results", (130, 18, 375, 46)),
    ("video/v002342", "WINNER --- COM", "winner_com", (520, 226, 65, 28)),
    ("video/v003962", "WINNER --- YOU", "winner_you", (520, 226, 65, 28)),
    ("video/v001576", "Menu du jeu (PASSWORD / SAVE)", "game_menu", (235, 330, 165, 120)),
    ("video/v007940", "Ecran DECK", "deck_screen", (490, 12, 125, 48)),
    ("video/v007920", "Ecran CHEST", "chest_screen", (15, 12, 135, 40)),
    ("password", "Ecran PASSWORD (STARCHIP)", "password_screen", (305, 74, 250, 36)),
    # Seul le premier mot ("SAVE" / "LOAD") : "COMPLETE!" est commun aux deux.
    ("save_done", "SAVE COMPLETE!", "save_done", (204, 190, 72, 28)),
    ("load_done", "LOAD COMPLETE!", "load_done", (204, 190, 72, 28)),
]


def load(cap):
    for ext in (".png", ".jpg"):
        img = cv2.imread(os.path.join(ROOT, "captures", cap + ext))
        if img is not None:
            return vision.normalize(img)
    raise FileNotFoundError(cap)


if os.path.isdir(OUT):
    shutil.rmtree(OUT)
lib = vision.TemplateLibrary(OUT)
for cap, name, action, rect, *pad in SPECS:
    lib.add(name, action, rect, load(cap), pad=pad[0] if pad else 6)
print(f"{len(lib.items)} gabarits -> {OUT}")

# Chiffres du HUD : valeurs reelles de captures connues (panneaux allumes et eteints).
LABELED = {
    "st1": {"com_lp": 8000, "com_deck": 40, "you_deck": 35, "you_lp": 8000},
    "d6": {"com_lp": 8000, "com_deck": 35, "you_deck": 35, "you_lp": 8000},
    "e1": {"com_lp": 8000, "com_deck": 35, "you_deck": 34, "you_lp": 8000},
    "live1": {"com_lp": 8000, "com_deck": 40, "you_deck": 35, "you_lp": 8000},
}
DIGITS = os.path.join(ROOT, "fm_speedtool", "assets", "digits_default.json")
if os.path.exists(DIGITS):
    os.remove(DIGITS)
reader = vision.DigitReader(DIGITS)
for cap, values in LABELED.items():
    reader.bootstrap(vision.normalize(cv2.imread(os.path.join(ROOT, "captures", cap + ".png"))), values)

# Chiffres vus dans la video de run (regroupes puis nommes a la main) :
# captures/video/digits.npz = vecteurs + etiquettes.
VIDEO_DIGITS = os.path.join(ROOT, "captures", "video", "digits.npz")
if os.path.exists(VIDEO_DIGITS):
    data = np.load(VIDEO_DIGITS)
    for vec, label in zip(data["vecs"], data["labels"]):
        reader.add(str(label), vec.astype(np.float32))
    reader.save()
print("chiffres integres :", reader.known_digits(),
      {d: len(v) for d, v in reader.templates.items()})
