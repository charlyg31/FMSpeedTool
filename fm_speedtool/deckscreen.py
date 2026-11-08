"""Lecture des ecrans de construction du deck.

Ecran DECK  : 8 lignes "position (01..40) + numero de carte (001..722)",
              compteur du deck sous le titre DECK, ligne du curseur bordee de blanc.
Ecran CHEST : 8 lignes "numero de carte" + deux cases a droite : exemplaires
              dans le coffre / dans le deck, ligne du curseur bordee d'orange.
"""

import json
import os
from collections import Counter

import cv2
import numpy as np

ROW_Y0, ROW_STEP, ROWS = 84, 47, 8
CELL_W, CELL_H = 13, 16
DECK_POS_X = (34, 50)
DECK_ID_X = (74, 90, 106)
DECK_COUNT_CELLS = ((522, 51), (538, 51))
CHEST_ID_X = (10, 26, 42)
BOX_DY, BOX_IN_CHEST_X, BOX_IN_DECK_X, BOX_W = 16, 558, 596, 14
GLYPH = (8, 12)
DECK_SIZE = 40


def row_y(r):
    return ROW_Y0 + ROW_STEP * r


def _norm(mask):
    if mask.sum() < 6:
        return None
    ys, xs = np.nonzero(mask)
    m = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return cv2.resize(m.astype(np.float32), GLYPH, interpolation=cv2.INTER_AREA)


def white_glyph(c):
    """Chiffre blanc sur fond sombre : lignes de l'ecran DECK (seuil fixe)."""
    return _norm((c.min(axis=2) > 140).astype(np.uint8))


def white_glyph_rel(c):
    """Chiffre clair, seuil relatif : compteur du deck et numeros du coffre (la
    ligne sous le curseur du coffre a des chiffres estompes)."""
    g = c.min(axis=2)          # le cadre orange du curseur a un canal bleu faible
    top = int(g.max())
    if top < 90:
        return None
    return _norm((g > min(140, top * 0.6)).astype(np.uint8))


def dark_glyph(c):
    """Chiffre sombre sur case claire (exemplaires coffre / deck). Sur la ligne
    du curseur, la bordure orange (et le trait sombre dessous) passe en bas de
    la case : on coupe a partir de cette bande."""
    m = (c.max(axis=2) < 100).astype(np.uint8)
    c16 = c.astype(np.int16)
    orange = (c16[..., 2] > 130) & (c16[..., 2] > c16[..., 0] + 50)
    rows = np.nonzero(orange.mean(axis=1) > 0.4)[0]
    if rows.size:
        m[rows[0]:] = 0
    return _norm(m)


class Digits:
    def __init__(self, path, glyph_fn):
        self.glyph_fn = glyph_fn
        self._stack = None
        self.vecs, self.labels = [], []
        if os.path.exists(path):
            data = np.load(path)
            self.vecs = list(data["vecs"].astype(np.float32))
            self.labels = [str(x) for x in data["labels"]]

    def classify(self, c):
        vec = self.glyph_fn(c)
        if vec is None or not self.vecs:
            return None
        if self._stack is None:
            self._stack = np.stack(self.vecs)
        d = np.abs(self._stack - vec).mean(axis=(1, 2))   # tous les gabarits d'un coup
        i = int(np.argmin(d))
        return self.labels[i] if d[i] < 0.12 else None

    def read(self, img, cells, w=CELL_W, h=CELL_H):
        text = ""
        for x, y in cells:
            ch = self.classify(img[y:y + h, x:x + w])
            if ch is None:
                return None
            text += ch
        return int(text)


def deck_rows(img, digits):
    """{ligne: (position, numero)} coherents (positions consecutives)."""
    rows = {}
    for r in range(ROWS):
        y = row_y(r)
        pos = digits.read(img, [(x, y) for x in DECK_POS_X])
        cid = digits.read(img, [(x, y) for x in DECK_ID_X])
        if pos and cid and 1 <= pos <= DECK_SIZE and 1 <= cid <= 722:
            rows[r] = (pos, cid)
    if not rows:
        return {}
    offsets = [pos - r for r, (pos, _) in rows.items()]
    top = max(set(offsets), key=offsets.count)
    return {r: pc for r, pc in rows.items() if pc[0] - r == top}


def deck_count(img, digits):
    return digits.read(img, DECK_COUNT_CELLS)


def _edge_highlight(img, test, minimum):
    scores = []
    for r in range(ROWS):
        y = row_y(r) - 4
        reg = img[y:y + 38, 600:640].astype(np.int16)
        scores.append(int(test(reg).sum()))
    r = int(np.argmax(scores))
    return r if scores[r] > minimum else None


def deck_highlight(img):
    """Ligne du curseur sur l'ecran DECK (bordure blanc-bleu)."""
    return _edge_highlight(img, lambda g: (g.min(axis=2) > 150) & (g[..., 0] > g[..., 2]), 30)


def chest_highlight(img):
    """Ligne du curseur sur l'ecran CHEST (bordure orange)."""
    return _edge_highlight(img, lambda g: (g[..., 2] > 170) & (g[..., 1] > 70) & (g[..., 1] < 170)
                           & (g[..., 0] < 90), 80)


def chest_rows(img, digits, box_digits):
    """{ligne: (numero, exemplaires dans le coffre, exemplaires dans le deck)}.
    digits : gabarits des numeros du coffre (police un peu differente du deck)."""
    rows = {}
    for r in range(ROWS):
        y = row_y(r)
        cid = digits.read(img, [(x, y) for x in CHEST_ID_X])
        if not cid or not 1 <= cid <= 722:
            continue
        in_chest = box_digits.read(img, [(BOX_IN_CHEST_X, y + BOX_DY)], w=BOX_W)
        in_deck = box_digits.read(img, [(BOX_IN_DECK_X, y + BOX_DY)], w=BOX_W)
        rows[r] = (cid, in_chest, in_deck)
    return rows


class DeckWatcher:
    """Composition du deck et ajouts/retraits, a partir des ecrans DECK et CHEST.

    Trois signaux, croises pour ne jamais compter deux fois un changement :
    - CHEST : la case "dans le deck" de chaque ligne visible donne le nombre
      exact d'exemplaires ; s'il differe de ce qu'on sait du deck -> ajout/retrait.
    - DECK : une page deja vue qui reapparait decalee d'un cran -> la carte
      disparue a ete retiree (ou celle apparue ajoutee).
    - DECK : le compteur baisse de 1 -> la carte sous le curseur est retiree.
    Les positions 1..40 lues (et recalees a chaque changement) fixent le deck.
    Chaque lecture doit etre identique sur 2 images de suite (defilement, clignotement)."""

    def __init__(self):
        self.deck = Counter()     # numero -> exemplaires (meilleure connaissance)
        self.known = set()        # cartes dont le nombre dans le deck est sur
        self.complete = False     # deck entierement lu au moins une fois
        self.added = []
        self.removed = []
        self.count = None         # compteur affiche sur l'ecran DECK
        self.slots = {}           # position -> numero (ecran DECK, recale)
        self.seen_at = {}         # numero -> derniere observation (tic)
        self.tick = 0
        self._prev = None
        self._deck_hl_card = None

    def reset(self):
        self.__init__()

    def _stable(self, key, value):
        same = self._prev == (key, value)
        self._prev = (key, value)
        if same:
            self.tick += 1
        return same

    def _seen(self, cid):
        self.seen_at[cid] = self.tick

    def _apply(self, kind, cid, n=1):
        """Enregistre n ajouts/retraits de cid et met le deck a jour."""
        events = []
        self._seen(cid)
        for _ in range(n):
            if kind == "+":
                self.deck[cid] += 1
                self.added.append(cid)
            else:
                self.deck[cid] = max(0, self.deck[cid] - 1)
                self.removed.append(cid)
            events.append((kind, cid))
        return events

    def deck_frame(self, img, digits, count_digits):
        rows = deck_rows(img, digits)
        count = deck_count(img, count_digits)
        hl = deck_highlight(img)
        if not self._stable("deck", (tuple(sorted(rows.items())), count, hl)):
            return []
        events = []
        visible = dict(rows.values())
        # Page deja vue mais decalee d'un cran ?
        for pos in sorted(visible):
            old = self.slots.get(pos)
            if old is None or old == visible[pos]:
                continue
            if self.slots.get(pos + 1) == visible[pos]:
                # Tout est remonte : 'old' a quitte le deck (s'il n'est pas deja compte).
                if not self.known or old not in self.known or self.deck[old] > 0:
                    events += self._apply("-", old)
                self.slots = {p - (p > pos): c for p, c in self.slots.items() if p != pos}
            elif visible.get(pos + 1) == old:
                events += self._apply("+", visible[pos])
                self.slots = {p + (p >= pos): c for p, c in self.slots.items()}
            else:
                self.slots = {}   # liste retriee ou lecture inattendue : on relit
            break
        if count is not None:
            if self.count is not None and count == self.count - 1 and self._deck_hl_card and not events:
                events += self._apply("-", self._deck_hl_card)
            self.count = count
        if hl is not None and hl in rows:
            self._deck_hl_card = rows[hl][1]
        self.slots.update(visible)
        for cid in visible.values():
            self._seen(cid)
            if self.deck[cid] == 0:
                self.deck[cid] = 1    # carte vue dans le deck : au moins un exemplaire
        if self.count == DECK_SIZE and all(p in self.slots for p in range(1, DECK_SIZE + 1)):
            self.deck = Counter(self.slots[p] for p in range(1, DECK_SIZE + 1))
            self.known = set(self.deck)
            self.complete = True
        return events

    def chest_frame(self, img, digits, box_digits):
        rows = chest_rows(img, digits, box_digits)
        hl = chest_highlight(img)
        if not self._stable("chest", (tuple(sorted(rows.items())), hl)):
            return []
        events = []
        for cid, _, in_deck in rows.values():
            if in_deck is None:
                continue
            if self.complete or cid in self.known:
                diff = in_deck - self.deck[cid]
                if diff:
                    events += self._apply("+" if diff > 0 else "-", cid, abs(diff))
                    self.slots = {}   # position inconnue : la liste devra etre relue
            self.deck[cid] = in_deck
            self.known.add(cid)
            self._seen(cid)
        return events

    def other_frame(self):
        self._prev = None

    def cards(self):
        """Deck estime, 40 cartes au plus : si on en connait trop (retraits jamais
        observes), on ecarte d'abord les cartes vues il y a le plus longtemps."""
        deck = Counter({c: n for c, n in self.deck.items() if n > 0})
        size = self.count or DECK_SIZE
        for cid in sorted(deck, key=lambda c: self.seen_at.get(c, -1)):
            excess = sum(deck.values()) - size
            if excess <= 0:
                break
            deck[cid] -= min(excess, deck[cid])
        return list(deck.elements())

    def summary(self):
        """(cartes identifiees, deck entierement lu au moins une fois)."""
        return len(self.cards()), self.complete


class DeckReader:
    """Regroupe les gabarits, la base de cartes et le suivi du deck."""

    def __init__(self, assets):
        self.deck_digits = Digits(os.path.join(assets, "deck_digits.npz"), white_glyph)
        self.count_digits = Digits(os.path.join(assets, "deck_digits.npz"), white_glyph_rel)
        self.chest_digits = Digits(os.path.join(assets, "chest_digits.npz"), white_glyph_rel)
        self.box_digits = Digits(os.path.join(assets, "box_digits.npz"), dark_glyph)
        self.db = CardDB(os.path.join(assets, "cards.json"))
        self.watcher = DeckWatcher()
        self.version = 0          # change a chaque modification du deck connu

    def frame(self, screen, img):
        """screen : 'deck', 'chest' ou None. Retourne [('+'|'-', nom)]."""
        before = Counter(self.watcher.deck)
        if screen == "deck":
            events = self.watcher.deck_frame(img, self.deck_digits, self.count_digits)
        elif screen == "chest":
            events = self.watcher.chest_frame(img, self.chest_digits, self.box_digits)
        else:
            self.watcher.other_frame()
            events = []
        if self.watcher.deck != before:
            self.version += 1
        return [(k, self.db.name(c)) for k, c in events]

    def f6(self):
        return f6_counts(self.watcher.cards(), self.db)

    def reset(self):
        self.watcher.reset()
        self.version += 1


class CardDB:
    def __init__(self, path):
        with open(path, encoding="utf-8") as f:
            self.cards = {int(k): v for k, v in json.load(f).items()}

    def name(self, cid):
        return self.cards.get(cid, {}).get("name", f"#{cid}")


# Numeros des cartes utiles au calcul du Final 6 (base FusionCalc, verifiee).
MBD, SKULL_KNIGHT, DARK_MAGICIAN, ZOA, USHI_ONI = 713, 707, 35, 391, 401
THUNDER_DRAGON, KAMINARI_ATTACK = 425, 458
UMI, MOUNTAIN, FIELDS = 334, 332, (330, 331, 333)
WSR, ATH, DCJ, MEGAMORPH, CRUSH = 686, 685, 329, 657, 661
DARK_HOLE, RAIGEKI = 336, 337
EQUIP_IDS = {668: "Bright Castle", 315: "Dragon Treasure", 303: "Dark Energy",
             308: "Beast Fangs", 324: "Invigoration", 313: "Horn of Light"}


def f6_counts(deck_ids, db):
    """Comptes du tableur d'Exarion a partir des numeros de cartes du deck."""
    c = {k: 0 for k in ("dragonsUnder1600", "dragons1600Plus", "thunderDragons", "thunders", "umi",
                        "wsr", "mm", "mbd", "skullKnight", "darkMagician", "zoa", "ushiOni",
                        "mountain", "fields", "dcj", "ath", "crushCard")}
    equips = []
    kaminari = raigeki = dark_hole = 0
    simple = {UMI: "umi", WSR: "wsr", MEGAMORPH: "mm", MBD: "mbd", SKULL_KNIGHT: "skullKnight",
              DARK_MAGICIAN: "darkMagician", ZOA: "zoa", USHI_ONI: "ushiOni", MOUNTAIN: "mountain",
              DCJ: "dcj", ATH: "ath", CRUSH: "crushCard"}
    for cid in deck_ids:
        card = db.cards.get(cid, {})
        if cid in simple:
            c[simple[cid]] += 1
        if cid in FIELDS:
            c["fields"] += 1
        if cid in EQUIP_IDS:
            equips.append(EQUIP_IDS[cid])
        raigeki += cid == RAIGEKI
        dark_hole += cid == DARK_HOLE
        kaminari += cid == KAMINARI_ATTACK
        if card.get("kind") == "Monster":
            if card.get("type") == "Thunder":
                c["thunders"] += 1
            # Dragon = type Dragon ou type secondaire Dragon (Dragon Statue, Dragon
            # Zombie, Crawling Dragon #2...) ; Thunder Dragon et MBD ont leur case.
            is_dragon = card.get("type") == "Dragon" or "Dragon" in card.get("secondary", [])
            if cid == THUNDER_DRAGON:
                c["thunderDragons"] += 1
            elif is_dragon and cid != MBD:
                c["dragonsUnder1600" if card.get("atk", 0) < 1600 else "dragons1600Plus"] += 1
    # 2 Kaminari Attack comptent comme 3 Thunders (regle du tableur).
    c["thunders"] += kaminari // 2
    # Le tableur suppose un Raigeki ; les Raigeki/Dark Hole en plus sont des Crush Card.
    starts_dark_hole = dark_hole > 0 and raigeki == 0
    c["crushCard"] += max(0, raigeki + dark_hole - 1)
    return c, starts_dark_hole, equips[:6]
