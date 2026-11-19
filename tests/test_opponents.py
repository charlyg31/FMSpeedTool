"""Adversaire de chaque duel : nom de l'ecran Free Duel, portrait de campagne, option All Duelists."""

import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
import cv2  # noqa: E402

import opponents  # noqa: E402
import tracker  # noqa: E402
import vision  # noqa: E402

ASSETS = os.path.join(ROOT, "fm_speedtool", "assets")
CAPTURES = os.path.join(ROOT, "captures")
needs_captures = pytest.mark.skipif(not os.path.isdir(CAPTURES), reason="dossier captures/ absent")


def _img(name):
    return vision.normalize(cv2.imread(os.path.join(CAPTURES, name)))


@needs_captures
@pytest.mark.parametrize("capture, name", [
    ("video/v001060.jpg", "Duel Master K"), ("video/v013141.jpg", "Isis"),
    ("video/v014957.jpg", "Pegasus"), ("fd_build_deck.jpg", None)])
def test_nom_free_duel(capture, name):
    reader, _p = opponents.load(ASSETS)
    assert reader.read(_img(capture)) == name


@needs_captures
@pytest.mark.parametrize("capture, name", [
    ("portrait_tw_rex.jpg", "Rex Raptor"), ("portrait_tw_seto3.jpg", "Seto 3rd"),
    ("portrait_tw_sebek.jpg", "Guardian Sebek"), ("portrait_tw_martis.jpg", "High Mage Martis")])
def test_portrait_campagne(capture, name):
    """Images d'une autre run (autre joueur, autre cadrage) que celle des references."""
    _r, portraits = opponents.load(ASSETS)
    assert portraits.identify(cv2.imread(os.path.join(CAPTURES, capture))) == name


@needs_captures
def test_pas_de_portrait_hors_dialogue():
    _r, portraits = opponents.load(ASSETS)
    for name in ("e1", "d3", "title1", "deck_live_p0"):
        assert portraits.identify(_img(name + ".png")) is None, name


class _NoTemplates:
    def matching(self, img, prep=None):
        return []


def _win(tr, now, opponent, free=True):
    tr.in_duel, tr.free_duel, tr.opponent = True, free, opponent
    tr._end_duel("win", now)
    split, tr.pending_split = tr.pending_split, None
    return split


def test_all_duelists_dmk_et_heishin():
    tr = tracker.Tracker(None, _NoTemplates(), None, lambda k, m: None)
    tr.options["all_duelists"] = True
    assert _win(tr, 1.0, "Duel Master K")[2] == tracker.SPLIT_WIN
    assert tr.free_wins == 0                       # pas un duel du farm
    assert _win(tr, 2.0, "Duel Master K") is None  # les suivants : farm
    assert tr.free_wins == 1
    assert _win(tr, 3.0, "Pegasus") is None        # autre adversaire en Free Duel : farm
    assert _win(tr, 4.0, "Heishin")[2] == tracker.SPLIT_WIN   # Heishin 1, perdu en campagne
    assert _win(tr, 5.0, "Heishin") is None
    assert [d["opponent"] for d in tr.history] == ["Duel Master K"] * 2 + ["Pegasus"] + ["Heishin"] * 2


def test_all_duelists_coupee():
    tr = tracker.Tracker(None, _NoTemplates(), None, lambda k, m: None)
    assert _win(tr, 1.0, "Duel Master K") is None
    assert _win(tr, 2.0, "Heishin") is None
    assert tr.free_wins == 2 and len(tr.history) == 2


def _tracker_hud():
    import tempfile
    digits = vision.DigitReader(os.path.join(tempfile.mkdtemp(), "d.json"),
                                os.path.join(ASSETS, "digits_default.json"))
    return tracker.Tracker(digits, _NoTemplates(), None, lambda k, m: None)


@needs_captures
def test_hud_cache_longtemps_meme_duel():
    """Suite de combats : HUD absent ~10 s en plein duel (stream). Il revient avec les LP
    du duel en cours : meme duel, pas un nouveau."""
    tr = _tracker_hud()
    assert not tr._new_duel_hud(cv2.imread(os.path.join(CAPTURES, "tw_hud_after_gap.jpg")))
    assert tr._new_duel_hud(_img("d6.png"))          # 8000 / 8000 : nouveau duel
    tr.decided = "win"
    assert tr._new_duel_hud(cv2.imread(os.path.join(CAPTURES, "tw_hud_after_gap.jpg")))
