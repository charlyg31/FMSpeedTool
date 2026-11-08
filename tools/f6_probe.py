"""Essai : calcul du tableur d'Exarion avec la bibliotheque formulas."""

import os
import sys
import time

import formulas

path = sys.argv[1]
t = time.time()
xl = formulas.ExcelModel().loads(path).finish()
print("chargement", round(time.time() - t, 1), "s")
t = time.time()
sol = xl.calculate()
print("calcul", round(time.time() - t, 1), "s")
name = os.path.basename(path).upper()
for k, v in sol.items():
    ku = k.upper()
    if f"[{name}]LIVE DECK'!" in ku and ku.split("!")[1] in ("A1", "D2", "E2", "F2", "G2", "H2", "I2"):
        print(k.split("!")[1], v.value)
