"""Cadrage de l'image sur l'ecran titre et l'ecran du deck (ePSXe decale, etire ou zoome)."""

import os
import sys

import numpy as np
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
import cv2  # noqa: E402

import deckscreen  # noqa: E402
import vision  # noqa: E402

CAPTURE = os.path.join(ROOT, "captures", "deck_live_p0.png")
TITLE = os.path.join(ROOT, "captures", "title1.png")          # ecran titre, ePSXe 1920x1536
pytestmark = pytest.mark.skipif(not os.path.exists(CAPTURE), reason="dossier captures/ absent")
REF = os.path.join(ROOT, "fm_speedtool", "assets", "hud_ref.png")
WARPS = [(4, 0, 1, 1), (0, -6, 1, 1), (-10, 0, 1.03, 1), (10, 8, 0.97, 0.97),
         (-19, 15, 1.06, 0.95), (30, -20, 0.9, 1.1)]


def _warp(img, dx, dy, sx, sy):
    return cv2.warpAffine(img, np.float32([[sx, 0, dx], [0, sy, dy]]), (640, 512))


def _calibrate(fr, img, tries=30):
    """Mesures successives (une echelle de plus essayee a chaque fois) jusqu'au calage."""
    return any(fr.calibrate(img) for _ in range(tries))


def _title():
    return vision.normalize(vision.GameArea().crop(cv2.imread(TITLE)))


def _rows(img):
    digits = deckscreen.Digits(os.path.join(ROOT, "fm_speedtool", "assets", "deck_digits.npz"),
                               deckscreen.white_glyph)
    return deckscreen.deck_rows(img, digits)


def test_capture_epsxe_inchangee():
    """Une capture directe d'ePSXe n'est pas deplacee."""
    fr = vision.Framing(REF, vertical=False)
    assert fr.calibrate(cv2.imread(CAPTURE))
    assert (fr.dx, fr.dy, fr.sx, fr.sy) == (0.0, 0.0, 1.0, 1.0)


@pytest.mark.parametrize("warp", WARPS)
def test_image_decalee_recalee(warp):
    img = cv2.imread(CAPTURE)
    moved = _warp(img, *warp)
    fr = vision.Framing(REF, vertical=False)
    assert _calibrate(fr, moved)
    dx, dy, sx, sy = warp
    for p in (0, 640):
        assert abs(fr.sx * (sx * p + dx) + fr.dx - p) < 0.5
    for p in (0, 512):
        assert abs(fr.sy * (sy * p + dy) + fr.dy - p) < 0.5
    # Les lignes du deck se relisent comme sur l'image d'origine (au-dela de 6 %, la double
    # mise a l'echelle du test floute trop les chiffres).
    if max(abs(sx - 1), abs(sy - 1)) <= 0.06:
        assert _rows(fr.apply(moved)) == _rows(img)


def test_petit_ecart_immediat():
    """Ecart courant (decalage, 3 %) : cale des la premiere mesure."""
    for warp in WARPS[:4]:
        fr = vision.Framing(REF, vertical=False)
        assert fr.calibrate(_warp(cv2.imread(CAPTURE), *warp)), warp


def test_ecran_titre_inchange():
    fr = vision.Framing(REF, vertical=False)
    assert fr.calibrate(_title())
    assert (fr.dx, fr.dy, fr.sx, fr.sy) == (0.0, 0.0, 1.0, 1.0)


@pytest.mark.parametrize("warp", WARPS[:4] + [(-38, -26, 1.12, 1.1)])
def test_ecran_titre_recale(warp):
    moved = _warp(_title(), *warp)
    fr = vision.Framing(REF, vertical=False)
    assert _calibrate(fr, moved)
    dx, dy, sx, sy = warp
    for p in (0, 640):
        assert abs(fr.sx * (sx * p + dx) + fr.dx - p) < 0.5
    for p in (0, 512):
        assert abs(fr.sy * (sy * p + dy) + fr.dy - p) < 0.5


def test_rien_hors_titre_et_deck():
    """Duel, carte posee... : aucun calage."""
    for name in ("e1", "d3", "k2", "fd2"):
        img = vision.normalize(vision.GameArea().crop(cv2.imread(os.path.join(ROOT, "captures", name + ".png"))))
        assert not _calibrate(vision.Framing(REF, vertical=False), img, 5), name


def test_epsxe_calage_en_hauteur_neutre():
    """ePSXe utilise aussi le calage en hauteur d'attente (panneau LP/COM/YOU) : sur une
    capture directe d'ePSXe, il ne decale ni n'etire rien."""
    for name in ("e1", "d3", "k2"):
        img = vision.normalize(vision.GameArea().crop(cv2.imread(os.path.join(ROOT, "captures", name + ".png"))))
        fr = vision.Framing(REF, vertical=True)
        _calibrate(fr, img, 5)
        assert fr.values()[:4] == [0.0, 1.0, 0.0, 1.0], name


def test_surveillance_suit_un_changement():
    """Deja cale : un autre reglage d'ePSXe est suivi apres plusieurs mesures concordantes."""
    img = cv2.imread(CAPTURE)
    fr = vision.Framing(REF, vertical=False)
    assert fr.calibrate(img)
    moved = _warp(img, 6, 0, 1, 1)
    results = [fr.calibrate(moved) for _ in range(fr.VOTES)]
    assert results[-1] and not any(results[:-1])
    for p in (0, 640):                     # au demi-pixel pres
        assert abs(fr.sx * (p + 6) + fr.dx - p) < 0.5
    assert not fr.calibrate(moved)


def test_reglage_garde():
    fr = vision.Framing(REF, vertical=False)
    fr.calibrate(_warp(cv2.imread(CAPTURE), 4, 0, 1, 1))
    again = vision.Framing.from_values(REF, fr.values(), vertical=False)
    assert again.full and again.done and (again.dx, again.sx) == (fr.dx, fr.sx)
    old = vision.Framing.from_values(REF, [3.0, 1.02], vertical=True)   # ancien format PS2
    assert old.locked and not old.full and (old.dy, old.sy, old.dx, old.sx) == (3.0, 1.02, 0.0, 1.0)
