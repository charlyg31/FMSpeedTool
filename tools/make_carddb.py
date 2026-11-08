"""Convertit la base de cartes de YGO-FM-FusionCalc
(https://github.com/CathodeRaymond/YGO-FM-FusionCalc) en fm_speedtool/assets/cards.json.

python tools/make_carddb.py chemin/ygo_fm_cardDB.csv chemin/ygo_fm_secondaryDB.txt
"""

import csv
import difflib
import json
import os
import sys

OUT = os.path.join(os.path.dirname(__file__), "..", "fm_speedtool", "assets", "cards.json")

cards = {}
with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
    for row in csv.reader(f, delimiter=";"):
        if not row:
            continue
        cid, name, kind = int(row[0]), row[1], row[2]
        card = {"name": name, "kind": kind}
        # Mot de passe et prix en etoiles (999 999 = non achetable)
        cost = row[-1].replace(",", "")
        if row[-2].isdigit() and cost.isdigit():
            card.update(password=row[-2], cost=int(cost))
        if kind == "Monster" and (row[3] == "" or row[4] in ("Serpent", "Beast")):
            # Lignes decalees dans la source : type vide (Metal Dragon) ou type en deux
            # morceaux ("Sea;Serpent", "Winged;Beast"), et une etoile gardienne manque.
            monster_type = row[4] if row[3] == "" else f"{row[3]} {row[4]}"
            row = row[:3] + [monster_type, row[5], "", row[7]] + row[8:]
        if kind == "Monster":
            card.update(type=row[3], atk=int(row[7]), defense=int(row[8]))
        cards[cid] = card
assert len(cards) == 722, len(cards)

# Types secondaires de fusion ("Dragon Statue | Dragon")
by_name = {c["name"].lower(): c for c in cards.values()}
with open(sys.argv[2], encoding="utf-8", errors="replace") as f:
    for line in f:
        if "|" not in line:
            continue
        name, types = (s.strip() for s in line.split("|", 1))
        key = name.lower()
        if key not in by_name:
            # Orthographes differentes entre les deux fichiers ("Sorceror"/"Sorcerer")
            close = difflib.get_close_matches(key, by_name, n=1, cutoff=0.85)
            if not close:
                print("sans correspondance :", name)
                continue
            key = close[0]
        by_name[key]["secondary"] = [t.strip() for t in types.split(",") if t.strip()]

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(cards, f, ensure_ascii=False)
print(len(cards), "cartes ->", OUT)
