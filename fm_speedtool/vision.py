"""Analyse d'image de Yu-Gi-Oh! Forbidden Memories.

Toutes les coordonnees sont dans une image normalisee 640x512 (sortie 4:3/5:4
d'ePSXe redimensionnee), quelle que soit la taille de la fenetre.
"""

import json
import os
import sys

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


class Framing:
    """Cadrage de l'image du jeu (fenetre ePSXe, ou PS2 + carte d'acquisition).

    Selon le reglage d'ePSXe (resolution, recadrage, plugin video), la console, la
    carte d'acquisition et OBS, l'image du jeu est un peu decalee ou etiree par
    rapport aux positions attendues : 4 pixels suffisent a ne plus lire les chiffres
    du deck. On cherche donc la correction (dx, dy, sx, sy) : sortie = s * entree + d.

    Calage complet sur deux ecrans, avec des reperes fixes loin des bords (qu'un zoom
    d'ePSXe peut couper), pris sur des captures directes d'ePSXe :
    - l'ecran titre (NEW GAME / LOAD...), qui passe avant chaque run : le debut et la
      fin du logo FORBIDDEN MEMORIES, le copyright en bas et les hieroglyphes en haut
      (pas les boutons du menu, dont le surlignage suit le curseur) ;
    - l'ecran du deck : le mot ORDER et le mot DECK en haut, le bas du cadre de la
      liste (sous le surlignage du curseur).
    Les positions trouvees donnent la largeur et la hauteur (moindres carres).
    PS2 en attendant : panneau LP/COM/YOU ou menu titre, calage vertical seulement.
    Un reglage n'est retenu qu'apres une mesure tres sure ou plusieurs concordantes, et
    il est garde d'une session a l'autre. Une fois cale, ces ecrans restent surveilles
    (de temps en temps) : si le reglage d'ePSXe change, le cadrage suit."""

    REFS = (("hud_ref.png", (490, 25, 140, 90)), ("title_ref.png", (230, 140, 180, 260)))
    SCALES = [round(0.86 + 0.02 * i, 2) for i in range(15)]       # 0,86 .. 1,14
    OFFSETS = list(range(-40, 41, 2))                              # pixels (image 640x512)
    # Reperes du calage complet : coin haut gauche a leur place attendue.
    SCREENS = (
        ("title", (("title_ref_a.png", (30, 215)), ("title_ref_b.png", (515, 235)),
                   ("title_ref_c.png", (120, 416)), ("title_ref_d.png", (10, 12)))),
        ("deck", (("deck_ref_a.png", (132, 20)), ("deck_ref_b.png", (486, 10)), ("deck_ref_c.png", (130, 449)))),
    )
    DECK_OFF = 64                                                   # recherche a +-64 px
    MIN_REF = 0.7                                                   # repere retenu pour l'ajustement
    SCALE_LIMIT = (0.84, 1.16)
    GOOD = 0.85                                                     # correlation minimale
    SURE = 0.93                                                     # une seule mesure suffit
    DECK_SURE = 0.95
    DEAD_ZONE = 2.5         # correction plus petite (coins) : image laissee telle quelle
    # Image tres etiree : reperes cherches aussi a ces echelles (largeur, hauteur), les plus
    # proches de 1 d'abord. Une seule par mesure en plus de 1 x 1 (~7 ms chacune).
    PAIRS = sorted(((a, b) for a in (1.0, 0.94, 1.06, 0.88, 1.12) for b in (1.0, 0.94, 1.06, 0.88, 1.12)),
                   key=lambda p: abs(p[0] - 1) + abs(p[1] - 1))
    VOTES = 3

    def __init__(self, ref_path, dy=0.0, sy=1.0, locked=False, dx=0.0, sx=1.0, full=False,
                 vertical=True):
        folder = os.path.dirname(ref_path)
        self.refs = []
        if vertical:                      # PS2 : calage vertical sur le panneau LP / menu titre
            for name, rect in self.REFS:
                ref = cv2.imread(os.path.join(folder, name), cv2.IMREAD_GRAYSCALE)
                if ref is not None:
                    self.refs.append((rect, ref.astype(np.float32)))
        self.screens = []
        for screen, names in self.SCREENS:
            refs = []
            for name, (x, y) in names:
                ref = cv2.imread(os.path.join(folder, name), cv2.IMREAD_GRAYSCALE)
                if ref is not None:
                    refs.append(((x, y), ref.astype(np.float32)))
            if len(refs) == len(names):
                self.screens.append((screen, refs))
        self.ref = self.refs[0][1] if self.refs else None
        self.dx, self.dy, self.sx, self.sy = float(dx), float(dy), float(sx), float(sy)
        self.full = bool(full) and bool(locked) and bool(self.screens)
        self.locked = bool(locked) and bool(self.refs or self.full)
        self.votes = []
        self.full_votes = []
        self.pair_next = 1                # prochaine echelle essayee en plus de 1 x 1
        self.pair_hit = None              # echelle qui a deja donne une mesure : reessayee
        self.last_pair = None
        self.score = 0.0

    @property
    def done(self):
        """Calage complet, ou vertical sans reperes complets : il reste seulement a surveiller."""
        return self.full or (self.locked and not self.screens)

    @staticmethod
    def _shift(m):
        """Deplacement maximal (px) d'un bord de l'image par la correction m (score, dx, dy, sx, sy)."""
        return max([abs((m[3] - 1) * x + m[1]) for x in (0, W)] + [abs((m[4] - 1) * y + m[2]) for y in (0, H)])

    def differs(self, m, tol=1.5):
        """Le reglage mesure m deplace-t-il un bord de l'image de plus de tol px par rapport a l'actuel ?"""
        return (any(abs((m[3] - self.sx) * x + m[1] - self.dx) > tol for x in (0, W))
                or any(abs((m[4] - self.sy) * y + m[2] - self.dy) > tol for y in (0, H)))

    def reset(self):
        self.dx, self.dy, self.sx, self.sy = 0.0, 0.0, 1.0, 1.0
        self.locked = self.full = False
        self.votes, self.full_votes, self.score = [], [], 0.0

    def values(self):
        """Pour la configuration : [dy, sy, dx, sx, complet]."""
        return [self.dy, self.sy, self.dx, self.sx, self.full]

    @classmethod
    def from_values(cls, ref_path, saved, vertical=True):
        """Reglage garde dans la configuration ([dy, sy] des versions precedentes accepte)."""
        if not saved:
            return cls(ref_path, vertical=vertical)
        v = list(saved) + [None] * 5
        return cls(ref_path, v[0], v[1], True, v[2] or 0.0, v[3] or 1.0, bool(v[4]), vertical=vertical)

    def apply(self, img):
        if self.dx == 0 and self.dy == 0 and self.sx == 1.0 and self.sy == 1.0:
            return img
        m = np.float32([[self.sx, 0, self.dx], [0, self.sy, self.dy]])
        return cv2.warpAffine(img, m, (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))

    # --- calage complet (ecran titre, ecran du deck) ---------------------------------

    @staticmethod
    def _find(gray, x, y, ref, off):
        """Position (score, x, y) du repere cherche autour de (x, y), a +-off pixels."""
        h, w = ref.shape
        pad = cv2.copyMakeBorder(gray, off, off, off, off, cv2.BORDER_CONSTANT, value=0)
        win = pad[y:y + h + 2 * off, x:x + w + 2 * off]
        if win.shape[0] < h or win.shape[1] < w:
            return 0.0, x, y
        r = cv2.matchTemplate(win, ref, cv2.TM_CCOEFF_NORMED)
        _, m, _, loc = cv2.minMaxLoc(r)
        return float(m), x - off + loc[0], y - off + loc[1]

    def _found(self, refs, gray, sx, sy, off):
        found = []
        for (x, y), ref in refs:
            if (sx, sy) != (1.0, 1.0):
                h, w = ref.shape
                ref = cv2.resize(ref, (max(8, int(round(w / sx))), max(8, int(round(h / sy)))),
                                 interpolation=cv2.INTER_AREA)
                x, y = int(round(x / sx)), int(round(y / sy))
            found.append(self._find(gray, x, y, ref, off))
        return found

    @staticmethod
    def _quality(found):
        """Score du 3e meilleur repere (il en faut au moins trois)."""
        return sorted(f[0] for f in found)[-3]

    def _measure_screen(self, refs, gray0, pairs):
        t = (0.0, 0.0, 1.0, 1.0)
        score = 0.0
        for off in (self.DECK_OFF, 6, 3):
            dx, dy, sx, sy = t
            if off == self.DECK_OFF:
                # Reperes a leur taille, puis (image tres etiree) a d'autres echelles.
                found = pair = None
                for psx, psy in pairs:
                    f = self._found(refs, gray0, psx, psy, off)
                    if found is None or self._quality(f) > self._quality(found):
                        found, pair = f, (psx, psy)
                    if self._quality(found) >= 0.9:
                        break
            else:
                gray = cv2.warpAffine(gray0, np.float32([[sx, 0, dx], [0, sy, dy]]), (W, H),
                                      flags=cv2.INTER_LINEAR)
                found = self._found(refs, gray, 1.0, 1.0, off)
            used = [(p, f) for (p, _), f in zip(refs, found) if f[0] >= self.MIN_REF]
            if len(used) < 3:
                return None
            score = float(np.mean([f[0] for _, f in used]))   # chacun >= MIN_REF
            fx = np.array([f[1] for _, f in used], np.float64)
            fy = np.array([f[2] for _, f in used], np.float64)
            rx = np.array([p[0] for p, _ in used], np.float64)
            ry = np.array([p[1] for p, _ in used], np.float64)
            if np.ptp(fx) < 250 or np.ptp(fy) < 180:
                return None
            # Correction de l'image deja corrigee : u -> k * u + e (moindres carres).
            kx, ex = np.polyfit(fx, rx, 1)
            ky, ey = np.polyfit(fy, ry, 1)
            t = (kx * dx + ex, ky * dy + ey, kx * sx, ky * sy)
        dx, dy, sx, sy = (float(v) for v in t)
        lo, hi = self.SCALE_LIMIT
        if not (lo <= sx <= hi and lo <= sy <= hi):
            return None
        return score, round(dx, 1), round(dy, 1), round(sx, 4), round(sy, 4), pair

    def measure_full(self, img, pairs=None):
        """(score, dx, dy, sx, sy) qui ramenent les reperes de l'ecran titre ou de l'ecran
        du deck a leur place, ou None. Puis deux passes sur l'image deja corrigee, pour affiner.
        pairs : echelles essayees pour la premiere recherche (toutes par defaut)."""
        if not self.screens:
            return None
        gray0 = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
        best = None
        for _, refs in self.screens:
            m = self._measure_screen(refs, gray0, self.PAIRS if pairs is None else pairs)
            if m is not None and (best is None or m[0] > best[0]):
                best = m
        if best is None:
            return None
        self.last_pair = best[5]
        return best[:5]

    # --- PS2 : calage vertical (panneau LP / menu titre) ----------------------------

    def measure(self, img):
        """Meilleur (score, dy, sy) pour cette image, ou None si pas de panneau."""
        if not self.refs:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
        best = None
        lo, hi = self.OFFSETS[0], self.OFFSETS[-1]
        for (x, y, w, h), ref in self.refs:
            band = gray[:, x:x + w]
            for sy in self.SCALES:
                # image etiree par sy : la ligne source s arrive en s * sy ; avec le
                # decalage dy, la reference (lignes y..y+h) tombe en y - dy. Une seule
                # recherche couvre tous les decalages de lo a hi.
                scaled = cv2.resize(band, (w, int(round(H * sy))), interpolation=cv2.INTER_LINEAR)
                top, bot = max(0, y - hi), min(scaled.shape[0], y + h - lo)
                if bot - top < h:
                    continue
                r = cv2.matchTemplate(scaled[top:bot], ref, cv2.TM_CCOEFF_NORMED)
                _, m, _, loc = cv2.minMaxLoc(r)
                dy = y - (top + loc[1])
                if best is None or m > best[0]:
                    best = (float(m), int(dy), sy)
        return best

    def calibrate(self, img):
        """A appeler de temps en temps sur une image normalisee (non corrigee) ;
        True si le reglage change. Une fois cale : surveillance (ecran titre, ecran du deck)."""
        # Deja cale : mesure rapide (sans recherche d'echelle), un changement doit etre
        # confirme par plusieurs mesures.
        pairs = [(1.0, 1.0)]
        if not self.full:
            if self.pair_hit not in (None, (1.0, 1.0)):
                pairs.append(self.pair_hit)
            pairs.append(self.PAIRS[self.pair_next])
            self.pair_next = self.pair_next % (len(self.PAIRS) - 1) + 1
        m = self.measure_full(img, pairs)
        if m is not None and m[0] >= self.GOOD:
            self.pair_hit = self.last_pair
            key = tuple(int(round(v)) for v in (m[1], m[2], m[3] * 640, m[4] * 512))
            close = [k for k in self.full_votes if max(abs(a - b) for a, b in zip(k, key)) <= 1]
            self.full_votes = (close + [key])[-self.VOTES:]
            # Premier calage : deux mesures concordantes (l'ecran titre passe vite) ;
            # deja cale : trois, pour ne pas suivre une mesure isolee.
            need = self.VOTES if self.full else 2
            sure = len(self.full_votes) >= need or (m[0] >= self.DECK_SURE and not self.full)
            if sure:
                # Decalage de 2 px ou moins : les lectures le tolerent deja (+-2 px), et
                # corriger ne ferait que retoucher l'image d'un reglage qui marche.
                if self._shift(m) <= self.DEAD_ZONE:
                    m = (m[0], 0.0, 0.0, 1.0, 1.0)
            if sure and (not self.full or self.differs(m)):
                self.dx, self.dy, self.sx, self.sy = m[1], m[2], m[3], m[4]
                self.score, self.locked, self.full = m[0], True, True
                self.full_votes = []
                return True
            return False
        if self.full:
            return False
        if self.locked or not self.refs:
            return False
        m = self.measure(img)
        if m is None or m[0] < self.GOOD:
            return False
        self.votes = (self.votes + [(m[1], m[2])])[-self.VOTES:]
        # Correspondance tres forte (menu titre, panneau du duel) : une mesure suffit,
        # le menu titre ne reste qu'une a deux secondes a l'ecran.
        if m[0] >= self.SURE or (len(self.votes) == self.VOTES and len(set(self.votes)) == 1):
            self.dy, self.sy = float(m[1]), float(m[2])
            self.score, self.locked = m[0], True
            return True
        return False


_TITLE_REF = None
_ORIENT = None
ORIENT_BOXES = ((217, 250), (390, 250))   # fleches gauche / droite (28x28) de l'ecran d'orientation
CARD_BACK_AT = (282, 197)                 # interieur du dos de carte au centre de cet ecran


def _asset(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return cv2.imread(os.path.join(base, "assets", name))


def _arrow_features(img):
    """Carre vert fonce (+1) et fleche jaune (-1) : ne depend pas de la couleur du terrain."""
    b, g, r = [img[..., k].astype(np.int16) for k in range(3)]
    green = (g > r + 20) & (g > b + 15) & (g > 30) & (g < 170)
    yellow = (r > 140) & (g > 130) & (b < 120)
    return green.astype(np.float32) - yellow.astype(np.float32)


def _orient_refs():
    global _ORIENT
    if _ORIENT is None:
        arrows, back = _asset("orient_arrows.png"), _asset("card_back.png")
        _ORIENT = (_arrow_features(arrows[:, :28]), _arrow_features(arrows[:, 28:]),
                   cv2.cvtColor(back, cv2.COLOR_BGR2GRAY))
    return _ORIENT


def orient_arrows(img, pad=14):
    """Ecran d'orientation d'une carte posee (fleches jaunes sur carres verts de part et
    d'autre de la carte) : plus petit des deux scores. Sur 4 videos : >= 0,7 sur cet
    ecran, <= 0,6 ailleurs (seuil 0,65). Le gabarit gris d'avant tombait a 0,72 sur le terrain DARK
    (Heishin 1, mages...) : les poses face cachee n'y etaient pas comptees."""
    left, right, _back = _orient_refs()
    scores = []
    for (x, y), tpl in zip(ORIENT_BOXES, (left, right)):
        reg = _arrow_features(img[y - pad:y + 28 + pad, x - pad:x + 28 + pad])
        scores.append(float(cv2.matchTemplate(reg, tpl, cv2.TM_CCOEFF_NORMED).max()))
    return min(scores)


def card_back(img, pad=40):
    """Dos de carte sur l'ecran d'orientation (interieur seul, sans le terrain autour) :
    >= 0,8 dos de carte, <= 0,65 carte face visible, sur 4 videos."""
    tpl = _orient_refs()[2]
    x, y = CARD_BACK_AT
    h, w = tpl.shape
    gray = cv2.cvtColor(img[y - pad:y + h + pad, x - pad:x + w + pad], cv2.COLOR_BGR2GRAY)
    return float(cv2.matchTemplate(gray, tpl, cv2.TM_CCOEFF_NORMED).max())


def title_menu_score(img):
    """Correlation des boutons LOAD / 2P DUEL / TRADE / OPTION de l'ecran titre avec
    leur place normale : 0,63 a 0,85 menu en place, ~0,2 des que le menu s'en va
    (appui sur NEW GAME)."""
    global _TITLE_REF
    if _TITLE_REF is None:
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        ref = cv2.imread(os.path.join(base, "assets", "title_ref.png"), cv2.IMREAD_GRAYSCALE)
        _TITLE_REF = ref.astype(np.float32) if ref is not None else False
    if _TITLE_REF is False:
        return 1.0
    gray = cv2.cvtColor(img[140:400, 230:410], cv2.COLOR_BGR2GRAY).astype(np.float32)
    return float(cv2.matchTemplate(gray, _TITLE_REF, cv2.TM_CCOEFF_NORMED)[0, 0])


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
        if all(np.abs(v - vec).mean() > 0.04 for v in vs) and len(vs) < 40:   # place pour d autres sources (console)
            vs.append(vec)
            return True
        return False

    def classify(self, vec):
        # Comparaison a tous les gabarits d'un coup (le cache suit les ajouts).
        n = sum(len(vs) for vs in self.templates.values())
        if not n:
            return None, 1e9
        if getattr(self, "_cache_n", -1) != n:
            self._labels = np.array([d for d, vs in self.templates.items() for _ in vs])
            self._stack = np.stack([v for vs in self.templates.values() for v in vs])
            self._cache_n = n
        dist = np.abs(self._stack - vec).mean(axis=(1, 2))
        i = int(np.argmin(dist))
        best_d, label = float(dist[i]), str(self._labels[i])
        if best_d < 0.10:
            return label, best_d
        # Un peu plus loin (autre eclairage du panneau, image plus floue) : accepte
        # si aucun autre chiffre n'est proche. Pas pour le "1" : toute barre fine
        # (bord du panneau qui glisse) lui ressemble.
        other = dist[self._labels != label]
        second = float(other.min()) if other.size else 1e9
        if best_d < 0.18 and second > best_d * 1.5 and label != "1":
            return label, best_d
        return None, best_d

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
    # La compression d'une video/d'un stream coupe parfois le cadre en morceaux : on
    # referme les petites coupures (sans effet sur une capture nette).
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    _, _, st, _ = cv2.connectedComponentsWithStats(m)
    return [tuple(s[:4]) for s in st[1:] if 195 <= s[2] <= 235 and 195 <= s[3] <= 235]


def board_zoom(img):
    """Vue rapprochee du terrain apres une pose validee : le haut de l'ecran
    (noir pendant le choix de la carte) est rempli par le terrain.
    Video : 0,05 avant, 0,6 a 0,98 apres une pose, 0,06 si la pose est annulee."""
    return float((img[60:150, 100:540].max(axis=2) > 60).mean()) > 0.5


def reveal_card(img):
    """Grande carte revelee apres une fusion/un equipement (a y ~ 127 ; les cartes
    d'un combat sont plus bas, a y ~ 140) : (x, y, illustration, case ATK/DFD) ou None.
    La case ATK/DFD est prise avec 3 px de marge pour la comparer a +-3 px pres."""
    wins = [w for w in _art_windows(img) if 118 <= w[1] <= 134]
    if len(wins) != 1:
        return None
    x, y, w, h = wins[0]
    art = cv2.resize(img[y + 8:y + h - 8, x + 8:x + w - 8], (96, 96),
                     interpolation=cv2.INTER_AREA).astype(np.float32)
    stats = cv2.cvtColor(img[y + 210:y + 264, x + 110:x + 226], cv2.COLOR_BGR2GRAY).astype(np.float32)
    return x, y, art, stats


def card_compare(ref, cur):
    """'counting' : meme carte au meme endroit dont l'ATK/DFD defile (equipement) ;
    'same' : meme carte, chiffres fixes ; 'other' : autre carte ou plus de carte.
    La case ATK/DFD est recalee a +-3 px (une carte bouge parfois d'un pixel, ce qui
    suffirait a faire croire que le texte change). Mesure sur trois videos : meme
    carte fixe <= 2,0 ; ATK qui defile >= 8."""
    if ref is None or cur is None or abs(ref[0] - cur[0]) > 4 or abs(ref[1] - cur[1]) > 4:
        return "other"
    if ref[3].shape != (54, 116) or cur[3].shape != (54, 116):
        return "other"
    # Meme illustration : < 1,3 sur une capture nette, jusqu'a 4,1 sur un stream compresse.
    if float(np.abs(ref[2] - cur[2]).mean()) > 4.5:
        return "other"
    inner = ref[3][3:-3, 3:-3]
    r = cv2.matchTemplate(cur[3], inner, cv2.TM_SQDIFF)
    d = float(np.sqrt(r.min() / inner.size))
    return "counting" if d >= 5.0 else "same"


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


def card_flash(img, side="left"):
    """Illustration de la carte de combat blanchie par le flash d'une destruction."""
    x = BATTLE_ART_X[0 if side == "left" else 1]
    art = img[ART_Y:ART_Y + ART_SIZE, x:x + ART_SIZE]
    return float((art.min(axis=2) > 210).mean()) > 0.2


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


def hud_panels(img):
    """Panneaux COM (bleu) et YOU (rouge) visibles, sans regarder l'encadre FIELD."""
    return _panel_strength(img, COM_PANEL, 0) > 90 and _panel_strength(img, YOU_PANEL, 2) > 80


def hud_present(img):
    """Le panneau LP/cartes du duel est-il a l'ecran ?"""
    blue = _panel_strength(img, COM_PANEL, 0)
    red = _panel_strength(img, YOU_PANEL, 2)
    if not (blue > 90 and red > 80):
        return False
    # Encadre "FIELD" bleu marine en haut a gauche (absent des decors bleu/rouge).
    box = img[40:92, 28:132].astype(int)
    navy = ((box[..., 0] > box[..., 2] + 30) & (box[..., 0] > box[..., 1] + 15)).mean()
    if navy <= 0.25:     # ~0.8 sans terrain, ~0.43 avec "FIELD MOUNTAIN", 0,25-0,35 en stream / PS2
        return False
    # Peu de bleu marine : il faut aussi le texte blanc "FIELD" (~4 %). Le film d'intro
    # (oeil bleu et orange, joue au demarrage et sur l'ecran titre inactif) n'en a pas.
    return navy > 0.5 or (box.min(axis=2) > 170).mean() > 0.005


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
        x, y, w, h = self.rect
        pad = self.pad
        # Pre-test tres rapide : couleur moyenne a la place prevue trop differente, ce n'est
        # pas cet ecran (sur 27 000 images de runs, les vrais ecrans restent a 40 au plus).
        if pad <= 20 and max(abs(a - b) for a, b in zip(cv2.mean(img[y:y + h, x:x + w])[:3], self.mean_color)) > 60:
            return 0.0
        gray, gray_half = prep if prep is not None else prepare(img)
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
