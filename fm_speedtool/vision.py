"""Analyse d'image de Yu-Gi-Oh! Forbidden Memories.

Toutes les coordonnees sont dans une image normalisee 640x512 (sortie 4:3/5:4
d'ePSXe redimensionnee), quelle que soit la taille de la fenetre.
"""

import json
import os

import cv2
import numpy as np

W, H = 640, 512

# Cases des chiffres du HUD (x, y, largeur, hauteur), droite = unites.
HUD_CELLS = {
    "com_lp":   [(556 + 16 * i, 33, 14, 16) for i in range(4)],
    "com_deck": [(590 + 16 * i, 50, 14, 16) for i in range(2)],
    "you_deck": [(590 + 16 * i, 71, 14, 16) for i in range(2)],
    "you_lp":   [(556 + 16 * i, 88, 14, 16) for i in range(4)],
}
COM_PANEL = (562, 36, 56, 26)   # fond bleu du panneau COM
YOU_PANEL = (562, 74, 56, 28)   # fond rouge du panneau YOU
GLYPH = (10, 12)


class GameArea:
    """Zone de jeu dans la fenetre ePSXe, sans les bandes noires.

    Toutes les tailles de fenetre fonctionnent deja (l'image est ramenee en
    640x512). Mais si ePSXe garde les proportions, des bandes noires entourent
    le jeu : il faut les retirer, sinon tout est decale. Une zone candidate
    (4:3 ou 5:4, centree) n'est retenue que si son exterieur est TOUJOURS reste
    noir et que du contenu a deja touche ses deux bords opposes ; sinon on
    garde la fenetre entiere (les bords du jeu sont souvent noirs en duel)."""

    ASPECTS = (4 / 3, 5 / 4)
    BLACK = 16
    STEP = 4                      # sous-echantillonnage pour la vitesse

    def __init__(self):
        self.size = None
        self.cands = []

    def _reset(self, w, h):
        self.size = (w, h)
        self.cands = []
        for aspect in self.ASPECTS:
            if w / h > aspect * 1.02:            # bandes a gauche et a droite
                gw = int(round(h * aspect))
                box = ((w - gw) // 2, 0, gw, h)
            elif w / h < aspect / 1.02:          # bandes en haut et en bas
                gh = int(round(w / aspect))
                box = (0, (h - gh) // 2, w, gh)
            else:
                continue
            self.cands.append({"box": box, "alive": True, "edge_a": False, "edge_b": False})

    def crop(self, frame):
        h, w = frame.shape[:2]
        if self.size != (w, h):
            self._reset(w, h)
        s = self.STEP
        lit = frame[::s, ::s].max(axis=2) > self.BLACK
        for c in self.cands:
            if not c["alive"]:
                continue
            x, y, gw, gh = (v // s for v in c["box"])
            inside = np.zeros_like(lit)
            inside[y:y + gh, x:x + gw] = True
            if (lit & ~inside).any():
                c["alive"] = False               # du contenu hors de la zone : pas de bandes
                continue
            if x > 0:                            # bandes laterales : bords gauche/droit
                c["edge_a"] |= bool(lit[y:y + gh, x:x + 2].any())
                c["edge_b"] |= bool(lit[y:y + gh, x + gw - 2:x + gw].any())
            else:                                # bandes haut/bas
                c["edge_a"] |= bool(lit[y:y + 2, x:x + gw].any())
                c["edge_b"] |= bool(lit[y + gh - 2:y + gh, x:x + gw].any())
        proven = [c for c in self.cands if c["alive"] and c["edge_a"] and c["edge_b"]]
        if not proven:
            return frame
        x, y, gw, gh = max(proven, key=lambda c: c["box"][2] * c["box"][3])["box"]
        return frame[y:y + gh, x:x + gw]


def normalize(frame):
    if frame is None:
        return None
    return cv2.resize(frame, (W, H), interpolation=cv2.INTER_AREA)


def crop(img, rect):
    x, y, w, h = rect
    return img[y:y + h, x:x + w]


def _glyph_mask(cell):
    """Chiffres gris sur fond colore : seuil d'Otsu sur la 'grisaille'
    (luminosite x desaturation), donc insensible au panneau allume ou eteint."""
    hsv = cv2.cvtColor(cell, cv2.COLOR_BGR2HSV).astype(np.float32)
    grey = hsv[..., 2] * (1.0 - hsv[..., 1] / 255.0)
    if grey.max() < 35:
        return None
    g8 = np.clip(grey * 255.0 / grey.max(), 0, 255).astype(np.uint8)
    _, m = cv2.threshold(g8, 0, 1, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Retire les bouts du contour du panneau qui depassent sur les bords.
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=4)
    w = m.shape[1]
    for i in range(1, n):
        x, _, cw, _, area = st[i]
        on_edge = x == 0 or x + cw >= w
        if area < 3 or (on_edge and cw <= 3):
            m[lab == i] = 0
    return m


def glyph_vector(cell):
    """Glyphe binarise et recadre, ou None si la case est vide."""
    m = _glyph_mask(cell)
    if m is None or m.sum() < 12:
        return None
    ys, xs = np.nonzero(m)
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return cv2.resize(m.astype(np.float32), GLYPH, interpolation=cv2.INTER_AREA)


def _panel_strength(img, rect, channel):
    """Intensite du canal de couleur du panneau (eclaire = joueur actif)."""
    patch = crop(img, rect).astype(int)
    others = [c for c in range(3) if c != channel]
    dom = patch[..., channel] - patch[..., others].max(axis=-1)
    sel = patch[..., channel][dom > 30]
    return float(np.median(sel)) if sel.size > 40 else 0.0


class DigitReader:
    """Reconnaissance des chiffres du HUD par gabarits appris.

    Part des chiffres integres (captures etiquetees), s'enrichit tout seul aux
    changements de tour, et met de cote les chiffres inconnus pour que
    l'utilisateur les nomme une fois (onglet Chiffres).
    """

    def __init__(self, path, defaults=None):
        self.path = path
        self.defaults = defaults  # chiffres integres, utilises au premier lancement
        self.templates = {}   # chiffre -> liste de vecteurs
        self.unknown = []     # (vecteur, apercu BGR)
        self.load()

    def load(self):
        self._cache_n = -1
        src = self.path if os.path.exists(self.path) else self.defaults
        if src and os.path.exists(src):
            with open(src, encoding="utf-8") as f:
                data = json.load(f)
            self.templates = {d: [np.array(v, dtype=np.float32).reshape(GLYPH[::-1]) for v in vs]
                              for d, vs in data.items()}

    def save(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({d: [v.round(3).ravel().tolist() for v in vs]
                       for d, vs in self.templates.items()}, f)

    def known_digits(self):
        return "".join(sorted(self.templates))

    def add(self, digit, vec):
        vs = self.templates.setdefault(digit, [])
        if all(np.abs(v - vec).mean() > 0.04 for v in vs) and len(vs) < 12:
            vs.append(vec)
            return True
        return False

    def classify(self, vec):
        # Comparaison a tous les gabarits d'un coup (le cache suit les ajouts).
        n = sum(len(vs) for vs in self.templates.values())
        if not n:
            return None, 1e9
        if getattr(self, "_cache_n", -1) != n:
            self._labels = [d for d, vs in self.templates.items() for _ in vs]
            self._stack = np.stack([v for vs in self.templates.values() for v in vs])
            self._cache_n = n
        dist = np.abs(self._stack - vec).mean(axis=(1, 2))
        i = int(np.argmin(dist))
        best_d = float(dist[i])
        return (self._labels[i], best_d) if best_d < 0.10 else (None, best_d)

    def read(self, img, field):
        """Valeur entiere, ou None si un chiffre est inconnu/illisible."""
        text = ""
        for rect in HUD_CELLS[field]:
            cell = crop(img, rect)
            vec = glyph_vector(cell)
            if vec is None:
                if text:
                    return None  # trou au milieu du nombre
                continue
            d, _ = self.classify(vec)
            if d is None:
                if len(self.unknown) < 30 and all(np.abs(u - vec).mean() > 0.06 for u, _ in self.unknown):
                    self.unknown.append((vec, cv2.resize(cell, (42, 48), interpolation=cv2.INTER_NEAREST)))
                return None
            text += d
        return int(text) if text else None

    def bootstrap(self, img, expected):
        """Apprend les chiffres d'un ecran dont les valeurs sont connues."""
        learned = False
        for field, value in expected.items():
            cells = HUD_CELLS[field]
            text = str(value).rjust(len(cells))
            for rect, ch in zip(cells, text):
                if ch == " ":
                    continue
                vec = glyph_vector(crop(img, rect))
                if vec is not None:
                    learned |= self.add(ch, vec)
        if learned:
            self.save()
        return learned


FLASH_RECT = (120, 100, 400, 300)    # zone du flash de fusion / equipement
BATTLE_ART_X = (51, 372)             # fenetres d'illustration en combat (gauche, droite)
ART_Y, ART_SIZE = 140, 214


def equip_glow(img):
    """Halo violet-magenta d'un equipement (5000 a 25000 px selon l'instant ;
    < 3000 sinon avec le HUD affiche)."""
    r = img[60:460, 60:580].astype(np.int16)
    b, g, red = r[..., 0], r[..., 1], r[..., 2]
    return int(((red > 150) & (b > 150) & (g < red - 50) & (g < b - 50)).sum())


def white_flash(img):
    """Nombre de pixels quasi blancs au centre (flash de fusion/equipement)."""
    return int((crop(img, FLASH_RECT).min(axis=2) > 225).sum())


def _art_windows(img):
    """Cadres gris des illustrations de grandes cartes : liste (x, y, w, h)."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 1] < 45) & (hsv[..., 2] > 90) & (hsv[..., 2] < 200)).astype(np.uint8)
    m[:120, 450:] = 0  # HUD
    _, _, st, _ = cv2.connectedComponentsWithStats(m)
    return [tuple(s[:4]) for s in st[1:] if 195 <= s[2] <= 235 and 195 <= s[3] <= 235]


def board_zoom(img):
    """Vue rapprochee du terrain apres une pose validee : le haut de l'ecran
    (noir pendant le choix de la carte) est rempli par le terrain.
    Video : 0,05 avant, 0,6 a 0,98 apres une pose, 0,06 si la pose est annulee."""
    return float((img[60:150, 100:540].max(axis=2) > 60).mean()) > 0.5


def reveal_card(img):
    """Grande carte revelee : (x, y, illustration, case ATK/DFD en gris) ou None."""
    wins = _art_windows(img)
    if len(wins) != 1:
        return None
    x, y, w, h = wins[0]
    art = img[y + 8:y + h - 8, x + 8:x + w - 8].astype(np.float32)
    stats = cv2.cvtColor(img[y + h - 4:y + h + 50, x + 110:x + w + 12], cv2.COLOR_BGR2GRAY).astype(np.float32)
    return x, y, art, stats


def card_compare(ref, cur):
    """'counting' : meme carte au meme endroit dont l'ATK/DFD defile (equipement) ;
    'same' : meme carte, chiffres fixes ; 'other' : autre carte ou plus de carte.
    Mesure sur la video : fusion < 1,2 ; equipement 1,7 a 4,8 (compteur qui monte)."""
    if ref is None or cur is None or abs(ref[0] - cur[0]) > 4 or abs(ref[1] - cur[1]) > 4:
        return "other"
    if ref[2].shape != cur[2].shape or ref[3].shape != cur[3].shape:
        return "other"
    if float(np.abs(ref[2] - cur[2]).mean()) > 3.0:
        return "other"
    d = float(np.abs(ref[3] - cur[3]).mean())
    return "counting" if 1.5 <= d < 12 else "same"


def reveal_art(img):
    """Illustration (48x48) de la grande carte revelee apres une fusion ou un
    equipement, ou None."""
    wins = _art_windows(img)
    if len(wins) != 1:
        return None
    x, y, w, h = wins[0]
    return cv2.resize(img[y + 8:y + h - 8, x + 8:x + w - 8], (48, 48),
                      interpolation=cv2.INTER_AREA).astype(np.float32)


def battle_cards(img):
    """En combat (2 grandes cartes a gauche/droite) : liste des cotes presents."""
    sides = []
    for x, y, w, h in _art_windows(img):
        if abs(y - ART_Y) < 12:
            if abs(x - BATTLE_ART_X[0]) < 15:
                sides.append("left")
            elif abs(x - BATTLE_ART_X[1]) < 15:
                sides.append("right")
    return sides


def card_in_defense(img, side):
    """Le texte de la stat active est noir : DFD plus sombre que ATK = defense."""
    x = BATTLE_ART_X[0 if side == "left" else 1]
    atk = img[378:395, x + 110:x + 213].max(axis=2)
    dfd = img[405:423, x + 110:x + 213].max(axis=2)
    return int((dfd < 70).sum()) > int((atk < 70).sum()) + 20


def _frame_colors(region):
    r = region.astype(int)
    b, g, red = r[..., 0], r[..., 1], r[..., 2]
    green = float(((g > red + 30) & (g > b + 20)).mean())
    magenta = float(((red > g + 50) & (b > g + 20)).mean())
    return green, magenta


def trap_card_right(img):
    """En combat, la carte de droite est un piege (cadre magenta)."""
    return _frame_colors(img[40:470, 345:620])[1] > 0.2


def magic_card_shown(img):
    """Grande carte magie (cadre vert, souvent en rotation) : la zone verte
    forme un bloc plus haut que large. Un terrain Foret/Prairie donne une large
    bande, les cartes de la main sont petites."""
    full = img.astype(np.int16)
    green = (full[..., 1] > full[..., 2] + 30) & (full[..., 1] > full[..., 0] + 20)
    # Sur un terrain vert (Foret, Prairie) la carte se confond avec le terrain :
    # au-dessus du terrain (fond noir), seule la carte est verte, en bloc central,
    # et son illustration (en dessous du cadre vert) ne l'est pas. Camera
    # reculee : le terrain, lui, reste vert jusqu'en bas.
    band = green[60:130]
    if (band[:, 200:440].mean() > 0.5
            and np.r_[band[:, 90:160].ravel(), band[:, 480:550].ravel()].mean() < 0.15
            and green[150:200, 200:440].mean() < 0.35):
        return True
    m = green[120:, 100:540].astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    _, _, st, _ = cv2.connectedComponentsWithStats(m)
    parts = [s for s in st[1:] if s[4] > 2500]
    if not parts:
        return False
    x0 = min(s[0] for s in parts)
    y0 = min(s[1] for s in parts)
    x1 = max(s[0] + s[2] for s in parts)
    y1 = max(s[1] + s[3] for s in parts)
    w, h = x1 - x0, y1 - y0
    return h >= 200 and h >= w and sum(s[4] for s in parts) > 12000


def card_burning(img, side):
    """Flammes (jaune/blanc tres lumineux) sur la carte."""
    x = BATTLE_ART_X[0 if side == "left" else 1]
    region = img[60:470, max(0, x - 40):x + 260]
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    fire = (hsv[..., 2] > 200) & (hsv[..., 0] < 35) & (hsv[..., 1] > 90)
    return float(fire.mean()) > 0.10


def hud_present(img):
    """Le panneau LP/cartes du duel est-il a l'ecran ?"""
    blue = _panel_strength(img, COM_PANEL, 0)
    red = _panel_strength(img, YOU_PANEL, 2)
    if not (blue > 90 and red > 80):
        return False
    # Encadre "FIELD" bleu marine en haut a gauche (absent des decors bleu/rouge).
    box = img[40:92, 28:132].astype(int)
    navy = ((box[..., 0] > box[..., 2] + 30) & (box[..., 0] > box[..., 1] + 15)).mean()
    return navy > 0.25  # ~0.8 sans terrain, ~0.43 avec "FIELD MOUNTAIN"


def active_player(img):
    """'you', 'com' ou None, d'apres le panneau eclaire."""
    blue = _panel_strength(img, COM_PANEL, 0) / 205.0
    red = _panel_strength(img, YOU_PANEL, 2) / 193.0
    if min(blue, red) <= 0:
        return None
    if red > blue * 1.35:
        return "you"
    if blue > red * 1.35:
        return "com"
    return None


# --- Ecrans appris (mode apprentissage) --------------------------------------

class ScreenTemplate:
    def __init__(self, name, action, rect, image, threshold=0.85, pad=6):
        self.name = name
        self.action = action
        self.rect = tuple(rect)
        self.image = image          # BGR, deja recadre dans l'image normalisee
        self.threshold = threshold
        self.pad = pad              # decalage tolere autour de la zone (pixels)
        self.gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        self.mean_color = image.mean((0, 1))
        x, y, w, h = self.rect
        # Grande zone de recherche : on cherche a demi-resolution (4x plus rapide).
        self.half = (w + 2 * pad) * (h + 2 * pad) > 15000 and min(w, h) >= 24
        self.gray_half = cv2.resize(self.gray, (w // 2, h // 2), interpolation=cv2.INTER_AREA)

    def score(self, img, prep=None):
        """prep : prepare(img), pour ne convertir l'image qu'une fois par image."""
        gray, gray_half = prep if prep is not None else prepare(img)
        x, y, w, h = self.rect
        pad = self.pad
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(W, x + w + pad), min(H, y + h + pad)
        if self.half:
            region = gray_half[y0 // 2:y1 // 2, x0 // 2:x1 // 2]
            tpl = self.gray_half
        else:
            region = gray[y0:y1, x0:x1]
            tpl = self.gray
        if region.shape[0] < tpl.shape[0] or region.shape[1] < tpl.shape[1]:
            return 0.0
        res = cv2.matchTemplate(region, tpl, cv2.TM_CCOEFF_NORMED)
        _, best, _, (bx, by) = cv2.minMaxLoc(res)
        if self.half:
            bx, by = bx * 2 + (x0 % 2), by * 2 + (y0 % 2)
        # Couleur moyenne : evite qu'un ecran de meme forme mais d'une autre teinte matche.
        found = img[y0 + by:y0 + by + h, x0 + bx:x0 + bx + w]
        if found.size == 0:
            return 0.0
        color_ok = np.abs(found.mean((0, 1)) - self.mean_color).max() < 40
        return float(best) if color_ok else 0.0

    def matches(self, img, prep=None):
        return self.score(img, prep) >= self.threshold


def prepare(img):
    """Image en gris, pleine et demi-resolution (partagees par tous les gabarits)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return gray, cv2.resize(gray, (W // 2, H // 2), interpolation=cv2.INTER_AREA)


class TemplateLibrary:
    def __init__(self, folder):
        self.folder = folder
        self.items = []
        self.load()

    def load(self):
        self.items = []
        index = os.path.join(self.folder, "index.json")
        if not os.path.exists(index):
            return
        with open(index, encoding="utf-8") as f:
            for e in json.load(f):
                img = cv2.imread(os.path.join(self.folder, e["file"]))
                if img is not None:
                    self.items.append(ScreenTemplate(e["name"], e["action"], e["rect"], img,
                                                     e.get("threshold", 0.85), e.get("pad", 6)))

    def save(self):
        os.makedirs(self.folder, exist_ok=True)
        entries = []
        for i, t in enumerate(self.items):
            fname = f"t{i:02d}_{t.action}.png"
            cv2.imwrite(os.path.join(self.folder, fname), t.image)
            entries.append({"name": t.name, "action": t.action, "rect": list(t.rect),
                            "file": fname, "threshold": t.threshold, "pad": t.pad})
        with open(os.path.join(self.folder, "index.json"), "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=1, ensure_ascii=False)

    def add(self, name, action, rect, img, threshold=0.85, pad=6):
        t = ScreenTemplate(name, action, rect, crop(img, rect).copy(), threshold, pad)
        self.items.append(t)
        self.save()
        return t

    def remove(self, index):
        del self.items[index]
        for f in os.listdir(self.folder):
            if f.endswith(".png"):
                os.remove(os.path.join(self.folder, f))
        self.save()

    def matching(self, img, prep=None):
        prep = prep if prep is not None else prepare(img)
        return [t for t in self.items if t.matches(img, prep)]
