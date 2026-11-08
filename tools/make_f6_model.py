"""Extrait du tableur d'Exarion (FM win rate calculator 2.1) les seules cellules
utiles au calcul du Final 6, dans un petit classeur fm_speedtool/assets/f6_model.xlsx.

python tools/make_f6_model.py "FM win rate calculator 2.1.xlsx"
"""

import os
import re
import sys

import openpyxl
from openpyxl.utils import column_index_from_string, get_column_letter, range_boundaries

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "fm_speedtool", "assets", "f6_model.xlsx")
MAIN = "Live deck"
OUTPUTS = ["A1", "D2", "E2", "F2", "G2", "H2", "I2"]
INPUTS = ["A7", "B7", "C7", "A9", "A11", "A12", "A13", "C8", "C9", "C10", "C11", "C12", "C13",
          "E8", "E9", "E10", "E12", "E13", "A14", "B14", "C14", "D14", "E14", "F14"]

REF = re.compile(r"(?:'([^']+)'|([A-Za-z][\w ]*?))?!?\$?([A-Z]{1,3})\$?(\d+)(?::\$?([A-Z]{1,3})\$?(\d+))?")
TOKEN = re.compile(r"(?:(?:'[^']+'|[A-Za-z_][\w]*)!)?\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?")


def refs(formula, sheet):
    """Cellules referencees par une formule : (feuille, 'A1')."""
    out = []
    for tok in TOKEN.findall(formula.replace('""', "")):
        if "!" in tok:
            sh, rng = tok.rsplit("!", 1)
            sh = sh.strip("'")
        else:
            sh, rng = sheet, tok
        rng = rng.replace("$", "")
        if not re.fullmatch(r"[A-Z]{1,3}\d+(:[A-Z]{1,3}\d+)?", rng):
            continue
        c1, r1, c2, r2 = range_boundaries(rng if ":" in rng else f"{rng}:{rng}")
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                out.append((sh, f"{get_column_letter(c)}{r}"))
    return out


def main(src):
    wb = openpyxl.load_workbook(src)
    todo = [(MAIN, c) for c in OUTPUTS + INPUTS]
    keep = set()
    while todo:
        sh, addr = todo.pop()
        if (sh, addr) in keep or sh not in wb.sheetnames:
            continue
        keep.add((sh, addr))
        v = wb[sh][addr].value
        if isinstance(v, str) and v.startswith("="):
            # retire les chaines entre guillemets avant de chercher les references
            todo += refs(re.sub(r'"[^"]*"', '""', v), sh)
    # Les feuilles annexes qui ne lisent jamais "Live deck" ne dependent pas du
    # deck saisi : on les fige avec les valeurs calculees par Excel.
    cached = openpyxl.load_workbook(src, data_only=True)
    static = set()
    for sh in wb.sheetnames:
        if sh == MAIN:
            continue
        cells = [a for s, a in keep if s == sh]
        if not any(s == MAIN for a in cells
                   for s, _ in refs(re.sub(r'"[^"]*"', '""', str(wb[sh][a].value or "")), sh)
                   if str(wb[sh][a].value or "").startswith("=")):
            static.add(sh)
    out = openpyxl.Workbook()
    out.remove(out.active)
    for sh in wb.sheetnames:
        cells = sorted(a for s, a in keep if s == sh)
        if not cells:
            continue
        ws = out.create_sheet(sh)
        src_ws = cached[sh] if sh in static else wb[sh]
        for addr in cells:
            ws[addr] = src_ws[addr].value
    print("feuilles figees :", sorted(static))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.save(OUT)
    print(len(keep), "cellules ->", OUT)


if __name__ == "__main__":
    main(sys.argv[1])
