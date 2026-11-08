"""Trouve les cellules en erreur du modele Final 6 pour un deck donne."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fm_speedtool"))
import formulas  # noqa: E402
import openpyxl  # noqa: E402

import f6calc  # noqa: E402

path = os.path.join(os.path.dirname(__file__), "..", "fm_speedtool", "assets", "f6_model.xlsx")
f6calc._register_combin(formulas)
xl = formulas.ExcelModel().loads(path).finish()
name = os.path.basename(path)
deck = dict(dragonsUnder1600=10, dragons1600Plus=8, thunders=10, umi=3, wsr=3, mm=2)
inputs = {f"'[{name}]LIVE DECK'!{c}": deck.get(f, 0) for f, c in f6calc.FIELD_CELLS.items()}
inputs[f"'[{name}]LIVE DECK'!E8"] = 1
for c, e in zip(f6calc.EQUIP_CELLS, ["Bright Castle", "Dragon Treasure"] * 3):
    inputs[f"'[{name}]LIVE DECK'!{c}"] = e
sol = xl.calculate(inputs=inputs)
ws = openpyxl.load_workbook(path)["Live deck"]
bad = []
for k, v in sol.items():
    if f"[{name}]LIVE DECK'!" not in k or ":" in k:
        continue
    val = getattr(v, "value", v)
    try:
        s = str(val.ravel()[0])
    except AttributeError:
        s = str(val)
    if s.startswith("#"):
        cell = k.split("!")[1]
        bad.append((cell, s, str(ws[cell].value)[:120]))
for cell in ["A158", "B158", "C158", "D158", "E158", "B159", "C159", "D159", "E159", "D160", "E160",
             "E145", "F145", "C145", "E152", "F152"]:
    v = sol.get(f"'[{name}]LIVE DECK'!{cell}")
    print(cell, getattr(v, "value", v), ws[cell].value)
for b in sorted(bad, key=lambda b: (int("".join(filter(str.isdigit, b[0]))), b[0]))[:25]:
    print(b)
