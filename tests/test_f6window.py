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


def test_reglages_completes():
    """Reglages enregistres incomplets ou d'une ancienne version : completes, cases inconnues retirees."""
    v = f6window.clean_view({"layout": "inconnue", "scale": 33, "order": ["mbd", "zzz"], "hidden": ["zzz", "zoa"]})
    assert v["layout"] == "horizontal" and v["scale"] == 100
    assert v["order"][0] == "mbd" and sorted(v["order"]) == sorted(f6window.TILES)
    assert v["hidden"] == ["zoa"] and v["boss_order"] == f6window.BOSSES


def test_reglages_du_rang():
    """Couleurs, fond et position de la fenetre du rang : valeurs invalides remplacees."""
    v = f6window.clean_view({"rank_color": "rouge", "score_color": "#00FFaa", "rank_bg": "bleu",
                             "rank_scale": 7, "rank_pos": "+12-30", "rank_window": True})
    assert v["rank_color"] == f6window.DEFAULT_VIEW["rank_color"] and v["score_color"] == "#00FFaa"
    assert v["rank_bg"] == "dark" and v["rank_scale"] == 100 and v["rank_pos"] == "+12-30"
    assert f6window.clean_view({"rank_pos": "800x600"})["rank_pos"] == ""
