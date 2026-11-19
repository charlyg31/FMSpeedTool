"""Adversaire de chaque duel.

Free Duel : nom ecrit dans la barre du bas de l'ecran Free Duel, lu lettre par lettre
(police des noms de cartes de l'ecran DECK, meme taille, meme pas) puis rapproche
des 39 adversaires.
Campagne : portrait (personnage et decor) du dialogue juste avant le duel.
"""

import json
import os

import cv2
import numpy as np

# Noms affiches par le jeu (ecran Free Duel), dans l'ordre de la liste.
FREE_DUEL_NAMES = (
    "Simon Muran", "Teana", "Jono", "Villager1", "Villager2", "Villager3", "Seto",
    "Heishin", "Rex Raptor", "Weevil Underwood", "Mai Valentine", "Bandit Keith", "Shadi",
    "Yami Bakura", "Pegasus", "Isis", "Kaiba", "Mage Soldier", "Jono 2nd", "Teana 2nd",
    "Ocean Mage", "High Mage Secmeton", "Forest Mage", "High Mage Anubisius",
    "Mountain Mage", "High Mage Atenza", "Desert Mage", "High Mage Martis", "Meadow Mage",
    "High Mage Kepura", "Labyrinth Mage", "Seto 2nd", "Guardian Sebek", "Guardian Neku",
    "Heishin 2nd", "Seto 3rd", "DarkNite", "Nitemare", "Duel Master K")
# Ecriture alternative possible -> nom affiche dans l'historique
SPELLINGS = {n: n for n in FREE_DUEL_NAMES}
SPELLINGS.update({f"Villager {i}": f"Villager{i}" for i in (1, 2, 3)})
DISPLAY = {f"Villager{i}": f"Villager {i}" for i in (1, 2, 3)}

PITCH = 16.25                 # pas des lettres (ecran DECK et Free Duel)
CELL_W, CELL_H = 16, 28       # case d'une lettre, 4 px au-dessus des majuscules
GLYPH = (8, 14)
FREE_NAME_AT = (32, 431)      # premiere case du nom sur l'ecran Free Duel
MAX_CHARS = 19
LIT_MIN = 6                   # pixels allumes pour qu'une case ne soit pas vide


def load(assets):
    """(NameReader, Portraits) du dossier assets, None pour ce qui manque."""
    names = os.path.join(assets, "name_glyphs.npz")
    portraits = os.path.join(assets, "portraits")
    return (NameReader(names) if os.path.exists(names) else None,
            Portraits(portraits) if os.path.isdir(portraits) else None)


def display_name(name):
    return DISPLAY.get(name, name)


def _threshold(line):
    return max(60.0, 0.8 * float(np.percentile(line, 99.5)))   # relatif : ecran en fondu


def _prepare(line):
    """Ligne de texte (minimum des 3 couleurs) : (gris doux 0..1, masque des lettres)."""
    line = line.astype(np.float32)
    t = _threshold(line)
    return np.clip((line - 0.6 * t) / (0.4 * t), 0, 1), (line >= t).astype(np.uint8)


def _cell(soft, lit, k, dx=0):
    """Lettre de la case k (vecteur norme), None si la case est vide ou hors de l'image."""
    x = int(round(k * PITCH)) + dx
    if x < 0 or x + CELL_W > soft.shape[1]:
        return None
    if cv2.countNonZero(lit[:, x:x + CELL_W]) < LIT_MIN:
        return None
    g = cv2.resize(soft[:, x:x + CELL_W], GLYPH, interpolation=cv2.INTER_AREA)
    g -= g.mean()
    n = float(np.linalg.norm(g))
    return g / n if n > 1e-6 else None


def name_cells(line, n):
    """Lettres d'une ligne de texte, case k a k * PITCH : n vecteurs (None : case vide)."""
    soft, lit = _prepare(line)
    return [_cell(soft, lit, k) for k in range(n)]


NOT_A_NAME = "Build Deck"     # autre choix de l'ecran Free Duel, ecrit au meme endroit


class NameReader:
    def __init__(self, path):
        data = np.load(path)
        self.glyphs = {str(c): v.astype(np.float32) for c, v in zip(data["labels"], data["vecs"])}

    def _cost(self, cells, ch):
        # Case a +-1 px : flou d'un stream, cadrage au pixel pres.
        if ch == " ":
            return 0.0 if not cells else 1.0
        if not cells:
            return 1.0
        ref = self.glyphs.get(ch)
        if ref is None:
            return 0.3                # lettre jamais vue : ni pour ni contre
        return min(1.0 - float((g * ref).sum()) for g in cells)

    def scores(self, img):
        x, y = FREE_NAME_AT
        soft, lit = _prepare(img[y:y + CELL_H, x:x + int(PITCH * (MAX_CHARS + 2)) + 2].min(axis=2))
        cells = [[g for g in (_cell(soft, lit, k, dx) for dx in (0, -1, 1)) if g is not None]
                 for k in range(MAX_CHARS + 2)]
        out = {}
        for spelled, name in list(SPELLINGS.items()) + [(NOT_A_NAME, NOT_A_NAME)]:
            text = spelled + "  "         # deux cases vides apres le nom
            cost = sum(self._cost(cells[k], ch) for k, ch in enumerate(text)) / len(text)
            out[name] = min(out.get(name, 9.0), cost)
        return out

    def read(self, img):
        """Nom de l'adversaire choisi sur l'ecran Free Duel, ou None (incertain, Build Deck)."""
        s = sorted(self.scores(img).items(), key=lambda kv: kv[1])
        (best, c1), (_, c2) = s[0], s[1]
        if best == NOT_A_NAME or c1 > 0.3 or c2 - c1 < 0.06:
            return None
        return best


# --- campagne : portrait du dialogue ------------------------------------------------

BAND_Y = (340, 396)           # bande de pierre gravee en haut de la boite de dialogue
SCENE_Y = 340                 # personnage et decor au-dessus
FEATURE = (48, 26)


def _feature(img):
    f = cv2.resize(img[:SCENE_Y], FEATURE, interpolation=cv2.INTER_AREA).astype(np.float32)
    f -= f.mean()
    n = float(np.linalg.norm(f))
    return f / n if n > 1e-3 else None


class Portraits:
    def __init__(self, folder):
        self.band = cv2.imread(os.path.join(folder, "dialog_band.png"), cv2.IMREAD_GRAYSCALE)
        with open(os.path.join(folder, "index.json"), encoding="utf-8") as f:
            entries = json.load(f)
        self.names, feats = [], []
        for e in entries:
            img = cv2.imread(os.path.join(folder, e["file"]))
            self.names.append(e["name"])
            feats.append(_feature(cv2.resize(img, (640, SCENE_Y))))
        self.feats = np.stack(feats)

    def dialog(self, img):
        """Boite de dialogue du jeu a l'ecran (bande de pierre gravee)."""
        g = cv2.cvtColor(img[BAND_Y[0]:BAND_Y[1]], cv2.COLOR_BGR2GRAY)
        return float(cv2.matchTemplate(g, self.band, cv2.TM_CCOEFF_NORMED).max()) > 0.7

    def identify(self, img):
        """Adversaire de campagne dont le portrait est affiche, ou None."""
        if not self.dialog(img) or img[20:SCENE_Y].mean() < 15:
            return None
        f = _feature(img)
        if f is None:
            return None
        sims = self.feats.reshape(len(self.names), -1) @ f.reshape(-1)
        order = np.argsort(-sims)
        best = order[0]
        other = next((i for i in order[1:] if self.names[i] != self.names[best]), None)
        if sims[best] < 0.55 or (other is not None and sims[best] - sims[other] < 0.06):
            return None
        return self.names[best]
