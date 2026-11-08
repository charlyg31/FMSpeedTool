"""% de victoire contre le Final 6, calcule par les formules du tableur
"FM win rate calculator 2.1" d'Exarion (assets/f6_model.xlsx, extrait par
tools/make_f6_model.py)."""

import os

import fmlogic

DUELISTS = ["Sebek", "Neku", "Heishin", "Seto 3", "DarkNite", "Nitemare"]
OUT_CELLS = ["D2", "E2", "F2", "G2", "H2", "I2", "A1"]

# Champ du logiciel -> case de la feuille "Live deck"
FIELD_CELLS = {
    "dragonsUnder1600": "A7", "dragons1600Plus": "B7", "thunderDragons": "C7", "thunders": "A9",
    "umi": "A11", "wsr": "A12", "mm": "A13", "mbd": "C8", "skullKnight": "C9",
    "darkMagician": "C10", "mountain": "C11", "fields": "C12", "dcj": "C13",
    "ath": "E9", "zoa": "E10", "ushiOni": "E12", "crushCard": "E13",
}
DARK_HOLE_CELL = "E8"
EQUIP_CELLS = ["A14", "B14", "C14", "D14", "E14", "F14"]


def _register_combin(formulas):
    """COMBIN n'existe pas dans la bibliotheque formulas : version Excel."""
    import math

    import numpy as np
    from formulas.functions import Error

    def combin(n, k):
        # Une reference de cellule arrive sous forme d'objet Ranges (.value).
        a = np.asarray(getattr(n, "value", n), object).ravel()[0]
        b = np.asarray(getattr(k, "value", k), object).ravel()[0]
        try:
            a, b = int(float(a)), int(float(b))
        except (TypeError, ValueError):
            return Error.errors["#VALUE!"]
        if a < 0 or b < 0 or a < b:
            return Error.errors["#NUM!"]
        return float(math.comb(a, b))

    formulas.get_functions()["COMBIN"] = combin


class F6Calculator:
    def __init__(self, model_path):
        self.model_path = model_path
        self.func = None
        self.error = None

    def _key(self, cell):
        name = os.path.basename(self.model_path)  # le moteur garde la casse du fichier
        return f"'[{name}]LIVE DECK'!{cell}"

    def load(self):
        """Lent (quelques secondes) : a lancer dans un thread au demarrage."""
        try:
            import formulas
            _register_combin(formulas)
            xl = formulas.ExcelModel().loads(self.model_path).finish()
            inputs = [self._key(c) for c in list(FIELD_CELLS.values()) + [DARK_HOLE_CELL] + EQUIP_CELLS]
            outputs = [self._key(c) for c in OUT_CELLS]
            self.func = xl.compile(inputs=inputs, outputs=outputs)
        except Exception as e:  # le calcul reste possible via le site
            import traceback
            self.error = f"{type(e).__name__}: {e}"
            self.traceback = traceback.format_exc()

    @property
    def ready(self):
        return self.func is not None

    def compute(self, counts, dark_hole, equips):
        """counts : champs fmlogic.F6_FIELDS ; equips : noms (6 max).
        Retourne {duelliste: proba, ..., "Final 6": proba}."""
        eq = [e for e in equips if e in fmlogic.F6_EQUIPS and e != "N/A"][:6]
        eq += ["N/A"] * (6 - len(eq))
        args = [int(counts.get(f, 0)) for f in FIELD_CELLS] + [1 if dark_hole else 0] + eq
        res = self.func(*args)
        vals = []
        for r in res:
            v = getattr(r, "value", r)
            while hasattr(v, "__len__") and not isinstance(v, str):
                v = v[0]
            vals.append(float(v))
        return dict(zip(DUELISTS + ["Final 6"], vals))
