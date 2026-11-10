"""Rejoue les captures reelles d'ePSXe dans le Tracker.  python -m pytest tests"""

import os
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
import cv2  # noqa: E402
import pytest  # noqa: E402

import fmlogic  # noqa: E402

# Les captures d'ePSXe et les images de la video de run ne sont pas dans le
# depot (taille) : ces tests ne tournent que si le dossier captures/ existe.
pytestmark = pytest.mark.skipif(not os.path.isdir(os.path.join(ROOT, "captures")),
                                reason="dossier captures/ absent")
import tracker  # noqa: E402
import vision  # noqa: E402


def load(name):
    img = cv2.imread(os.path.join(ROOT, "captures", name + ".png"))
    assert img is not None, name
    return img


def make_tracker(events):
    tmp = tempfile.mkdtemp()
    digits = vision.DigitReader(os.path.join(tmp, "digits.json"),
                                os.path.join(ROOT, "fm_speedtool", "assets", "digits_default.json"))
    builtin = vision.TemplateLibrary(os.path.join(ROOT, "fm_speedtool", "assets", "builtin"))
    learned = vision.TemplateLibrary(os.path.join(tmp, "learned"))
    return tracker.Tracker(digits, builtin, learned, lambda t, m: events.append((t, m)))


def test_run_sequence():
    events = []
    tr = make_tracker(events)
    t = 0.0
    seq = ["title1", "ng2", "ng3", "boot_screen", "st1", "st1", "st1", "d1", "d1", "d2",
           "d6", "d6", "e1"]
    # Pose comptee 1 s apres la vue rapprochee, si l'ecran d'orientation ne revient pas.
    seq += ["e1"] * 6
    for name in seq:
        tr.process(load(name), now=t)
        t += 0.2
    kinds = [k for k, _ in events]
    assert kinds.count("new_run") == 1
    assert "duel_start" in kinds
    assert tr.stats["facedown"] == 1
    assert tr.stats["turns"] == 1           # un tour termine (passage YOU -> COM)
    assert tr.stats["lp"] == 8000
    assert tr.hud["you_deck"] == 34 and tr.stats["cards"] == 6
    # Toutes les captures etiquetees se lisent exactement, et une sauvegarde
    # chargee en plein duel (g3, loop*) aussi.
    truth = {"st1": (8000, 40, 35, 8000), "d6": (8000, 35, 35, 8000), "e1": (8000, 35, 34, 8000),
             "g3": (8000, 35, 34, 8000), "loop39": (8000, 35, 34, 8000)}
    for name, expected in truth.items():
        img = vision.normalize(load(name))
        for field, value in zip(("com_lp", "com_deck", "you_deck", "you_lp"), expected):
            assert tr.digits.read(img, field) == value, (name, field)
    # HUD absent plus de 8 s sans resultat : duel abandonne, sans split
    for _ in range(60):
        tr.process(load("title1"), now=t)
        t += 0.2
    assert not tr.in_duel
    assert "split" not in kinds


def test_rank_examples():
    s = dict(fusion=15, eff_atk=4, turns=9, lp=5000, cards=37, facedown=1, equip=1, trap=1, magic=1)
    assert fmlogic.band(fmlogic.score(s)) == "A-TEC"
    assert "atteint" in fmlogic.advice(s)
    fresh = {k: 0 for k in fmlogic.RANK_TABLE}
    fresh["lp"] = 8000
    assert fmlogic.band(fmlogic.score(fresh)) == "S-POW"


def test_f6_matches_excel():
    """Deck d'exemple du tableur : valeurs calculees par Excel (enregistrees dans le .xlsx)."""
    import f6calc
    calc = f6calc.F6Calculator(os.path.join(ROOT, "fm_speedtool", "assets", "f6_model.xlsx"))
    calc.load()
    assert calc.error is None
    deck = dict(dragonsUnder1600=7, dragons1600Plus=5, thunders=10, umi=2, wsr=3, mm=2, dcj=1)
    r = calc.compute(deck, False, ["Dark Energy", "Dragon Treasure", "Dragon Treasure"])
    excel = [0.9892611614989095, 0.9208130451851264, 0.8134673349618422,
             0.644445680812814, 0.9651100390209291, 0.7163207126985004, 0.33013623969175626]
    for name, value in zip(f6calc.DUELISTS + ["Final 6"], excel):
        assert abs(r[name] - value) < 1e-9, name
    # 3 equipements ou plus passe par COMBIN (absent de la bibliotheque, ajoute a la main)
    r = calc.compute(dict(deck, mm=2), True, ["Bright Castle", "Dragon Treasure"] * 3)
    assert 0 < r["Final 6"] < 1


def test_deck_screen_reading():
    """Ecran DECK de la video : lecture de la page et retrait de Muse-A (592)."""
    import deckscreen
    reader = deckscreen.DeckReader(os.path.join(ROOT, "fm_speedtool", "assets"))
    page1 = cv2.imread(os.path.join(ROOT, "captures", "video", "v007940.jpg"))
    rows = deckscreen.deck_rows(page1, reader.deck_digits)
    assert [cid for _, cid in sorted(rows.values())] == [168, 168, 200, 190, 190, 387, 34, 268]
    assert deckscreen.deck_count(page1, reader.count_digits) == 40
    before = cv2.imread(os.path.join(ROOT, "captures", "video", "v007978.jpg"))
    after = cv2.imread(os.path.join(ROOT, "captures", "video", "v008004.jpg"))
    events = []
    for img in (before, before, after, after):
        events += reader.frame("deck", img)
    assert events == [("-", "Muse-A")]
    chest = cv2.imread(os.path.join(ROOT, "captures", "video", "v007920.jpg"))
    rows = deckscreen.chest_rows(chest, reader.chest_digits, reader.box_digits)
    assert rows[3][0] == 190 and rows[3][2] == 2   # Akakieisu (sous le curseur) : 2 dans le deck
    # Classement du tableur : Thunder Dragon compte a part et dans les Thunders.
    counts, _, _ = deckscreen.f6_counts([425, 211, 168, 1, 138, 97, 713], reader.db)
    assert counts["thunders"] == 2 and counts["thunderDragons"] == 1
    # Petits : Darkfire Dragon, Dragon Statue (Guerrier, Dragon en type secondaire).
    # Gros : Blue-Eyes, Dragon Zombie (Zombie, Dragon secondaire). MBD a sa propre case.
    assert counts["dragonsUnder1600"] == 2 and counts["dragons1600Plus"] == 2
    assert counts["mbd"] == 1
    umi = cv2.imread(os.path.join(ROOT, "captures", "video", "v007988.jpg"))
    assert deckscreen.chest_rows(umi, reader.chest_digits, reader.box_digits)[5] == (334, 0, 1)


def test_starting_deck_pages():
    """Deck de depart de la video : pages verifiees a l'oeil."""
    import deckscreen
    reader = deckscreen.DeckReader(os.path.join(ROOT, "fm_speedtool", "assets"))
    expected = {
        "v000504": {8: 469, 9: 586, 10: 250, 11: 635, 12: 3, 13: 159, 14: 527, 15: 504},
        "v000509": {12: 3, 13: 159, 14: 527, 15: 504, 16: 402, 17: 261, 18: 198, 19: 198},
        "v000496": {33: 199, 34: 558, 35: 123, 36: 547, 37: 510, 38: 336, 39: 330, 40: 322},
    }
    for name, page in expected.items():
        img = cv2.imread(os.path.join(ROOT, "captures", "video", name + ".jpg"))
        assert dict(deckscreen.deck_rows(img, reader.deck_digits).values()) == page, name


def test_window_sizes_and_black_bars():
    """Fenetres de 640x480 a 2560x1920, et bandes noires (16:9, 4:3 dans 5:4)."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import size_check
    assert size_check.check(size_check.with_area)


def test_hud_negatives():
    for name in ("title1", "ng2", "boot_screen", "boot1"):
        assert not vision.hud_present(vision.normalize(load(name)))

