"""Regles du jeu : calcul du rang de duel et code de partage du calculateur Final 6."""


from i18n import N_, _

# Seuils (borne haute exclue) et points, d'apres le tableau de rang du jeu
# (gist cinoss "Battle Rank", identique a FMRankCalc de hippochan).
# Score = 50 + type de victoire + somme des points.
RANK_TABLE = {
    "turns":     [(5, 12), (9, 8), (29, 0), (33, -8), (None, -12)],
    "eff_atk":   [(2, 4), (4, 2), (10, 0), (20, -2), (None, -4)],
    "def_win":   [(2, 0), (6, -10), (10, -20), (15, -30), (None, -40)],
    "facedown":  [(1, 0), (11, -2), (21, -4), (31, -6), (None, -8)],
    "fusion":    [(1, 4), (5, 0), (10, -4), (15, -8), (None, -12)],
    "equip":     [(1, 4), (5, 0), (10, -4), (15, -8), (None, -12)],
    "magic":     [(1, 2), (4, -4), (7, -8), (10, -12), (None, -16)],
    "trap":      [(1, 2), (3, -8), (5, -16), (7, -24), (None, -32)],
    "cards":     [(9, 15), (13, 12), (33, 0), (37, -5), (None, -7)],
    "lp":        [(100, -7), (1000, -5), (7000, 0), (8000, 4), (None, 6)],
}
RANK_BASE = 50
# Type de victoire (FMRankCalc de hippochan) : normale +2, paquet adverse vide -40, Exodia +40.
VICTORY_POINTS = {"annihilation": 2, "attrition": -40, "exodia": 40}

STAT_LABELS = {
    "turns": N_("Tours"), "eff_atk": N_("Attaques efficaces"), "def_win": N_("Victoires en defense"),
    "facedown": N_("Poses face cachee"), "fusion": N_("Fusions"), "equip": N_("Equipements"),
    "magic": N_("Magies pures"), "trap": N_("Pieges declenches"), "cards": N_("Cartes utilisees"),
    "lp": N_("LP restants"),
}

# Bandes de rang : (score min, score max, nom)
BANDS = [(-999, 9, "S-TEC"), (10, 19, "A-TEC"), (20, 29, "B-TEC"), (30, 39, "C-TEC"),
         (40, 49, "D-TEC"), (50, 59, "D-POW"), (60, 69, "C-POW"), (70, 79, "B-POW"),
         (80, 89, "A-POW"), (90, 999, "S-POW")]


def stat_points(stat, value):
    for upper, pts in RANK_TABLE[stat]:
        if upper is None or value < upper:
            return pts
    return 0


def next_threshold(stat, value):
    """(valeur a atteindre, points apres) pour le palier suivant, ou None."""
    for upper, _pts in RANK_TABLE[stat]:
        if upper is not None and value < upper:
            return upper, stat_points(stat, upper)
    return None


def score(stats):
    victory = VICTORY_POINTS[stats.get("victory", "annihilation")]
    return RANK_BASE + victory + sum(stat_points(k, stats.get(k, 0)) for k in RANK_TABLE)


def band(total):
    for lo, hi, name in BANDS:
        if lo <= total <= hi:
            return name
    return "?"


def band_range(name):
    for lo, hi, n in BANDS:
        if n == name:
            return lo, hi
    raise KeyError(name)


def advice(stats, target="A-TEC"):
    """Conseils pour amener le score dans la bande visee."""
    total = score(stats)
    lo, hi = band_range(target)
    if lo <= total <= hi:
        return _("{target} atteint ({score}). Garde ces stats.", target=target, score=total)
    need = total - hi if total > hi else total - lo
    lines = []
    shown, b = max(0, min(99, total)), band(total)
    if total > hi:
        lines.append(_("Score {score} ({band}) : il faut baisser de {n}.", score=shown, band=b, n=abs(need)))
    else:
        lines.append(_("Score {score} ({band}) : il faut monter de {n}.", score=shown, band=b, n=abs(need)))
    for stat in ("fusion", "facedown", "equip", "magic", "trap", "eff_atk", "turns", "cards"):
        nt = next_threshold(stat, stats.get(stat, 0))
        if not nt:
            continue
        upto, pts_after = nt
        delta = pts_after - stat_points(stat, stats.get(stat, 0))
        if (delta < 0 and total > hi) or (delta > 0 and total < lo):
            more = upto - stats.get(stat, 0)
            lines.append(f"  {_(STAT_LABELS[stat])} : +{more} -> {delta:+d}")
    return "\n".join(lines)


# --- Final 6 (tableur d'Exarion) ---------------------------------------------------

F6_FIELDS = ["dragonsUnder1600", "dragons1600Plus", "thunderDragons", "thunders", "umi",
             "wsr", "mm", "mbd", "skullKnight", "darkMagician", "zoa", "ushiOni",
             "mountain", "fields", "dcj", "ath", "crushCard"]
def best_equips(equips, n=6):
    """Le tableur d'Exarion a 6 cases d'equipement (Megamorph a part) et fait la
    moyenne de leur valeur : au-dela de 6, on garde les 6 meilleurs d'apres sa
    table (Bright Castle > Dragon Treasure = Beast Fangs > Dark Energy >
    Invigoration > Horn of Light)."""
    order = ["Bright Castle", "Dragon Treasure", "Beast Fangs", "Dark Energy", "Invigoration", "Horn of Light"]
    eq = [e for e in equips if e in order]
    return sorted(eq, key=order.index)[:n]


F6_EQUIPS = ["Bright Castle", "Dragon Treasure", "Dark Energy", "Beast Fangs",
             "Invigoration", "Horn of Light", "N/A"]
F6_LABELS = {
    "dragonsUnder1600": "Dragons < 1600", "dragons1600Plus": "Dragons 1600+",
    "thunderDragons": "Thunder Dragon", "thunders": "Thunders", "umi": "Umi",
    "wsr": "Widespread Ruin", "mm": "Megamorph", "mbd": "Meteor B. Dragon",
    "skullKnight": "Skull Knight", "darkMagician": "Dark Magician", "zoa": "Zoa",
    "ushiOni": "Ushi Oni", "mountain": "Mountain", "fields": "Fields (Forest/Wasteland/Sogen)",
    "dcj": "Dragon Capture Jar", "ath": "Acid Trap Hole", "crushCard": "Crush Card",
}
