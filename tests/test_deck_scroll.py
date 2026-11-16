"""Lecture de la liste du deck pendant un defilement R1 (lignes lues simulees)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fm_speedtool"))
import deckscreen as ds  # noqa: E402


def run(pages, monkeypatch):
    """pages : liste de {ligne: (position, carte)}, une par image."""
    it = iter(pages)
    monkeypatch.setattr(ds, "deck_rows", lambda img, d: next(it))
    monkeypatch.setattr(ds, "deck_count", lambda img, d: 40)
    monkeypatch.setattr(ds, "deck_highlight", lambda img: None)
    w = ds.DeckWatcher()
    for _ in pages:
        w.deck_frame(None, None, None)
    return w


def page(first, card=lambda p: 100 + p):
    return {r: (first + r, card(first + r)) for r in range(ds.ROWS)}


def test_first_page_shown_once(monkeypatch):
    # R1 des l'arrivee : la page 1 n'est affichee qu'une image, puis la liste glisse.
    frames = [page(1)] + [page(p) for p in (2, 2, 4, 5, 7, 7, 9, 10, 12, 12, 14, 15, 17, 17, 19,
                                            20, 22, 22, 24, 25, 27, 27, 29, 30, 32, 33, 33)] + [page(33)] * 3
    w = run(frames, monkeypatch)
    assert w.complete
    assert w.slots == {p: 100 + p for p in range(1, 41)}


def test_single_frame_misread_not_kept(monkeypatch):
    # Image isolee avec une ligne mal lue, encore visible a l'image suivante : rien n'en est garde.
    bad = page(1)
    bad[3] = (4, 999)
    w = run([bad, page(2)], monkeypatch)
    assert 1 not in w.slots and 4 not in w.slots
