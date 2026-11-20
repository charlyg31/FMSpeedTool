"""Fenetre Final 6 : une image (prise dans le jeu) pour chaque case et chaque boss."""

import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
import f6window  # noqa: E402

F6 = os.path.join(ROOT, "fm_speedtool", "assets", "f6")


def test_images_presentes():
    names = [f6window.tile_file(k) for k in f6window.TILES if k != f6window.RAIGEKI]
    names += ["raigeki", "dark_hole"] + list(f6window.BOSS_FILES.values())
    for n in names:
        assert os.path.exists(os.path.join(F6, n + ".png")), n


def test_couleur_pourcentage():
    assert f6window.pct_color(0.18) != f6window.pct_color(0.96)
