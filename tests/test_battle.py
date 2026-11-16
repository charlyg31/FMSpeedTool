"""Fin d'un combat : attaque efficace ou destruction des deux monstres (images simulees).
Chaque image : cartes vues ("LR", "L", "R", "-") et '*' si la carte de gauche flashe."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fm_speedtool"))
import tracker  # noqa: E402
import vision  # noqa: E402

A = os.path.join(os.path.dirname(__file__), "..", "fm_speedtool", "assets")


def eff_attacks(frames, monkeypatch):
    it = iter(frames)
    cur = {}
    monkeypatch.setattr(vision, "battle_cards", lambda img: [s for s, c in (("left", "L"), ("right", "R")) if c in cur["f"]])
    monkeypatch.setattr(vision, "card_flash", lambda img, side="left": "*" in cur["f"])
    monkeypatch.setattr(vision, "card_in_defense", lambda img, side: False)
    monkeypatch.setattr(vision, "trap_card_right", lambda img: False)
    tr = tracker.Tracker(vision.DigitReader(os.path.join(tempfile.mkdtemp(), "d.json"),
                                            os.path.join(A, "digits_default.json")),
                         vision.TemplateLibrary(os.path.join(A, "builtin")), None, lambda k, m: None)
    tr.active = "you"
    for f in list(it) + ["HUD"]:
        cur["f"] = f
        tr._battle(None, f == "HUD")
    return tr.stats["eff_atk"]


def frames(s):
    return s.split()


def test_effective_attack(monkeypatch):
    assert eff_attacks(frames("LR LR LR -* -* LR LR L L L L L - -"), monkeypatch) == 1


def test_both_destroyed(monkeypatch):
    # Combat contre Pegasus (2100 contre 2100) : la droite brule, puis la gauche flashe et brule.
    seq = "LR LR L L L - - L L L LR LR -* -* -* L* L LR LR LR L L L L L L - -* -* -* L L L L - - -"
    assert eff_attacks(frames(seq), monkeypatch) == 0


def test_hit_flash_after_hidden_defender(monkeypatch):
    # Defenseur cache un instant (eclat) avant le flash du coup : attaque efficace quand meme.
    seq = "LR LR L L L LR LR -* -* L* L LR LR L L L L L L - -"
    assert eff_attacks(frames(seq), monkeypatch) == 1
