"""Seule la 1re defaite de campagne splitte.  python -m pytest tests"""

import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
import tracker  # noqa: E402


class _NoTemplates:
    def matching(self, img, prep=None):
        return []


def lose(tr, now, free=False):
    tr.in_duel = True
    tr.free_duel = free
    tr._end_duel("loss", now)
    split = tr.pending_split
    tr.pending_split = None
    return split


def make():
    return tracker.Tracker(None, _NoTemplates(), None, lambda k, m: None)


def test_only_first_campaign_loss_splits():
    tr = make()
    assert lose(tr, 1.0) is not None           # Heishin 1
    assert lose(tr, 2.0) is None               # mort plus tard
    assert lose(tr, 3.0) is None


def test_free_duel_loss_does_not_count():
    tr = make()
    assert lose(tr, 1.0, free=True) is None    # defaite en Free Duel avant Heishin
    assert lose(tr, 2.0) is not None           # Heishin 1 splitte quand meme
