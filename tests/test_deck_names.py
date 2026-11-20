"""Ecran DECK : numero controle par le nom de la carte, tri de la liste (bouton ORDER)."""

import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
import cv2  # noqa: E402

import deckscreen as ds  # noqa: E402
import vision  # noqa: E402

ASSETS = os.path.join(ROOT, "fm_speedtool", "assets")
CAPTURE = os.path.join(ROOT, "captures", "deck_live_p0.png")
needs_capture = pytest.mark.skipif(not os.path.exists(CAPTURE), reason="capture absente")


@needs_capture
def test_numero_corrige_par_le_nom():
    """Lignes 01 004 Baby Dragon et 06 034 Saggi the Dark Clown : un chiffre mal lu
    (005, 035 = Dark Magician) est corrige par le nom ; un numero juste ne bouge pas."""
    img = vision.normalize(cv2.imread(CAPTURE))
    reader = ds.DeckReader(ASSETS)
    y0, y5 = ds.row_y(0) + ds.NAME_DY, ds.row_y(5) + ds.NAME_DY
    assert reader.names.fix(img, ds.NAME_X_DECK, y0, 4) == 4
    assert reader.names.fix(img, ds.NAME_X_DECK, y0, 5) == 4
    assert reader.names.fix(img, ds.NAME_X_DECK, y5, 35) == 34
    assert reader.names.fix(img, ds.NAME_X_DECK, y5, 34) == 34


@needs_capture
def test_tri_de_la_liste():
    assert ds.deck_sort(vision.normalize(cv2.imread(CAPTURE))) == 0      # tri par numero (NO.)


def test_tri_change_oublie_les_positions():
    w = ds.DeckWatcher()
    w.slots = {1: 4, 2: 4, 3: 10}
    w._sort = 0
    img = vision.normalize(cv2.imread(CAPTURE)) if os.path.exists(CAPTURE) else None
    if img is None:
        pytest.skip("capture absente")
    img = img.copy()
    # Icone NO. eteinte, 6e icone allumee : autre tri
    y0, y1 = ds.SORT_ICONS_Y
    x = int(ds.SORT_ICONS_X0)
    img[y0:y1, x - 12:x + 12] = 15
    x5 = int(ds.SORT_ICONS_X0 + ds.SORT_ICONS_STEP * 5)
    img[y0:y1, x5 - 12:x5 + 12] = 90
    assert ds.deck_sort(img) == 5
    w.deck_frame(img, ds.Digits(os.path.join(ASSETS, "deck_digits.npz"), ds.white_glyph),
                 ds.Digits(os.path.join(ASSETS, "deck_digits.npz"), ds.white_glyph_rel))
    assert w._sort == 5 and 3 not in w.slots
