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


def _register_exact_match():
    """RECHERCHEV(...; FAUX) : Excel compare les nombres a 15 chiffres pres, la
    bibliotheque formulas au bit pres. La cle cherchee par le tableur est une somme
    de parts du deck (6 Thunders x 0,1 = 0,6000000000000001) : sans tolerance, elle
    n'est pas trouvee dans la table et tout le calcul finit en #N/A."""
    import numpy as np
    from formulas.functions import look

    if getattr(look.xmatch, "_tolerant", False):
        return
    exact = look.xmatch

    def xmatch(lookup_value_type, lookup_value, lookup_value_raw, lookup_array_index,
               lookup_array_type, lookup_array, lookup_array_raw, match_type=1):
        if match_type == 0 and isinstance(lookup_value, (int, float, np.number)) \
                and not isinstance(lookup_value, bool):
            b = lookup_value_type == lookup_array_type
            index, array = lookup_array_index[b], lookup_array[b]
            try:
                values = array.astype(float)
            except (TypeError, ValueError):
                values = None
            if values is not None and len(values):
                close = np.abs(values - float(lookup_value)) <= 1e-12 * max(1.0, abs(float(lookup_value)))
                if close.any():
                    return index[close][0]
        return exact(lookup_value_type, lookup_value, lookup_value_raw, lookup_array_index,
                     lookup_array_type, lookup_array, lookup_array_raw, match_type)

    xmatch._tolerant = True
    look.xmatch = xmatch


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
            _register_exact_match()
            xl = formulas.ExcelModel().loads(self.model_path).finish()
            inputs = [self._key(c) for c in list(FIELD_CELLS.values()) + [DARK_HOLE_CELL] + EQUIP_CELLS]
            outputs = [self._key(c) for c in OUT_CELLS]
            self.func = xl.compile(inputs=inputs, outputs=outputs)
            # Le modele complet du classeur ne sert plus (seule la fonction compilee reste) :
            # ~250 Mo rendus tout de suite au lieu de rester occupes.
            del xl
            import gc
            gc.collect()
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
        eq = fmlogic.best_equips(equips)
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


def _serve(model_path, requests, results):
    """Processus a part : charge le tableur puis calcule a la demande (le dernier
    deck demande seulement). Le chargement accapare Python une quinzaine de secondes :
    dans le processus du logiciel, il figeait l'interface par a-coups d'une seconde."""
    import sys
    for name in ("stdout", "stderr"):       # .exe sans console
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
    calc = F6Calculator(model_path)
    calc.load()
    results.put(("ready", calc.error, getattr(calc, "traceback", None)))
    while True:
        req = requests.get()
        while not requests.empty():         # demandes en retard : seule la derniere compte
            req = requests.get()
        if req is None:
            return
        try:
            results.put(("result", calc.compute(*req), None))
        except Exception as e:
            results.put(("result", None, f"{type(e).__name__}: {e}"))


class F6Process:
    """Meme calcul que F6Calculator, dans un processus a part (interface toujours fluide).
    request() envoie un deck ; poll() rend les messages arrives : ("ready", erreur, trace)
    puis ("result", {duelliste: proba}, erreur)."""

    def __init__(self, model_path):
        import multiprocessing
        ctx = multiprocessing.get_context("spawn")
        self.requests, self.results = ctx.Queue(), ctx.Queue()
        self.proc = ctx.Process(target=_serve, args=(model_path, self.requests, self.results), daemon=True)
        self.proc.start()
        self.ready = False
        self.error = None
        self.traceback = None

    def request(self, counts, dark_hole, equips):
        self.requests.put((dict(counts), bool(dark_hole), list(equips)))

    def poll(self):
        import queue
        out = []
        while True:
            try:
                msg = self.results.get_nowait()
            except queue.Empty:
                break
            if msg[0] == "ready":
                self.error, self.traceback = msg[1], msg[2]
                self.ready = msg[1] is None
            out.append(msg)
        if not self.ready and self.error is None and not self.proc.is_alive():
            self.error = "processus du tableur arrete"
            out.append(("ready", self.error, None))
        return out

    def close(self):
        try:
            self.requests.put(None)
            self.proc.join(0.5)
        except Exception:
            pass
        if self.proc.is_alive():
            self.proc.terminate()
