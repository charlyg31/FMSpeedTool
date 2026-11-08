"""Mots de passe des cartes utiles achetables (ecran PASSWORD du jeu), classes
selon les categories du calculateur Final 6 d'Exarion."""

import deckscreen as ds
from i18n import N_

NOT_FOR_SALE = 999999
MAX_COST = 100            # au-dela, trop cher pour une run


def useful_passwords(db):
    """[(section, nom, mot de passe, prix, detail)] tries par section puis prix."""
    out = []

    def add(section, cid, detail=""):
        card = db.cards.get(cid, {})
        cost = card.get("cost", NOT_FOR_SALE)
        if card.get("password") and cost <= MAX_COST:
            out.append((section, card["name"], card["password"], cost, detail))

    for cid, card in db.cards.items():
        if card.get("kind") != "Monster":
            continue
        atk = card.get("atk", 0)
        if card.get("type") == "Thunder":
            add("Thunders", cid, f"ATK {atk}")
        if cid == ds.THUNDER_DRAGON:
            continue                      # deja dans les Thunders (gros dragon + thunder)
        if (card.get("type") == "Dragon" or "Dragon" in card.get("secondary", [])) and cid != ds.MBD:
            add("Dragons < 1600" if atk < 1600 else "Dragons 1600+", cid, f"ATK {atk}")
    for cid in (ds.KAMINARI_ATTACK,):
        if not any(o[1] == db.name(cid) for o in out):
            add("Thunders", cid, "2 = 3 Thunders")
    for cid in (ds.UMI, ds.MOUNTAIN):     # seuls terrains utiles en run
        add("Terrains", cid)
    for cid in ds.EQUIP_IDS:
        add("Equipements", cid)
    for cid in (ds.MEGAMORPH, ds.USHI_ONI, ds.ZOA, ds.SKULL_KNIGHT, ds.DARK_MAGICIAN, ds.MBD,
                ds.WSR, ds.DCJ, ds.ATH, ds.CRUSH, ds.DARK_HOLE, ds.RAIGEKI):
        add("Autres cartes utiles", cid)
    # Noms de section traduits a l'affichage (_(section)).
    order = [N_("Thunders"), N_("Dragons < 1600"), N_("Dragons 1600+"), N_("Terrains"),
             N_("Equipements"), N_("Autres cartes utiles")]
    return sorted(out, key=lambda o: (order.index(o[0]), o[3], o[1]))


def format_password(pw):
    """'09430387' -> '0943 0387' (plus lisible a recopier)."""
    return f"{pw[:4]} {pw[4:]}"
