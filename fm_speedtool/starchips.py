"""Total d'etoiles (starchips) affiche sur l'ecran PASSWORD : "STARCHIP  * x 87".

Chiffres blancs de la meme police que le mot de passe tape en dessous ; gabarits pris sur
ces chiffres (tous les 10 y passent). Pendant un achat le total defile (87, 84, 80... 57) :
seule une valeur restee affichee un moment compte.
"""

import os

import numpy as np

import deckscreen as ds

TOTAL_RECT = (400, 108, 200, 36)   # a droite du "x" (image 640x512)
MAX_DIST = 0.2                     # chiffres reconnus : <= 0,07 ; au-dela, lecture refusee


def _glyphs(mask_cols):
    """Colonnes allumees -> chiffres (x0, x1). Un trou de 3 px au plus reste dans le meme
    chiffre (la diagonale du 7 se coupe en deux)."""
    out, x, n = [], 0, len(mask_cols)
    while x < n:
        if mask_cols[x]:
            x0 = x
            while x < n and (mask_cols[x] or mask_cols[x + 1:x + 4].any()):
                x += 1
            if x - x0 >= 4:
                out.append((x0, x))
        x += 1
    return out


class TotalReader:
    def __init__(self, assets):
        self.digits = ds.Digits(os.path.join(assets, "starchip_digits.npz"), ds.white_glyph)

    def read(self, img):
        """Total lu (int) ou None."""
        if not self.digits.vecs:
            return None
        x, y, w, h = TOTAL_RECT
        reg = img[y:y + h, x:x + w]
        cols = (reg.min(axis=2) > 150).any(axis=0)
        parts = _glyphs(np.asarray(cols))
        if not parts or len(parts) > 6:
            return None
        txt = ""
        for a, b in parts:
            label, dist = self.digits._nearest(reg[:, a:b], ds.white_glyph)
            if label is None or dist > MAX_DIST:
                return None
            txt += label
        return int(txt)
