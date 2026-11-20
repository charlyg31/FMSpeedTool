"""Fenetre Final 6 : boss et % de victoire en haut, cartes du deck en images dessous.
Se remplit toute seule avec le deck lu et le calcul du panneau Final 6 (capturable dans OBS)."""

import os
import tkinter as tk

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageTk

import f6calc
import fmlogic
from i18n import _

BG, TILE_BG, BORDER = "#111214", "#1c1d21", "#3a3b40"
TEXT, DIM = "#e8e8ea", "#9a9ba0"
EQUIPS = [e for e in fmlogic.F6_EQUIPS if e != "N/A"]
RAIGEKI = "raigeki"
# Cases de cartes, dans l'ordre d'affichage (8 par ligne)
TILES = fmlogic.F6_FIELDS[:8] + fmlogic.F6_FIELDS[8:] + [RAIGEKI] + EQUIPS
BOSS_FILES = {"Sebek": "boss_sebek", "Neku": "boss_neku", "Heishin": "boss_heishin",
              "Seto 3": "boss_seto3", "DarkNite": "boss_darknite", "Nitemare": "boss_nitemare",
              "Final 6": "boss_final6"}
CARD_W, CARD_H = 104, 96
BOSS = 84


def tile_file(key):
    return "equip_" + key.lower().replace(" ", "_") if key in EQUIPS else key


def pct_color(p):
    """Rouge sous 50 %, orange jusqu'a 80 %, vert au-dessus."""
    return "#e05a5a" if p < 0.5 else "#e0a64a" if p < 0.8 else "#5ac46e"


def _font(size):
    for name in ("segoeuib.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


class F6Window:
    def __init__(self, root, folder, on_dark_hole, on_close, geometry=None):
        self.folder = folder
        self.on_dark_hole = on_dark_hole
        self.on_close = on_close
        self.win = tk.Toplevel(root, bg=BG)
        self.win.title("Final 6")
        if geometry:
            self.win.geometry(geometry)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.font = _font(20)
        self.cache = {}
        self.last = None

        top = tk.Frame(self.win, bg=BG)
        top.pack(padx=10, pady=(10, 6))
        self.boss_pct = {}
        for i, name in enumerate(list(BOSS_FILES)):
            f = tk.Frame(top, bg=TILE_BG, highlightbackground=BORDER, highlightthickness=2)
            f.grid(row=0, column=i, padx=4)
            img = self._image(BOSS_FILES[name], (BOSS, BOSS))
            tk.Label(f, image=img, bg=TILE_BG).pack(padx=8, pady=(8, 2))
            tk.Label(f, text=name, fg=TEXT, bg=TILE_BG, font=("Segoe UI", 10, "bold")).pack()
            v = tk.Label(f, text="-", fg=DIM, bg=TILE_BG, font=("Segoe UI", 15, "bold"))
            v.pack(pady=(0, 6))
            self.boss_pct[name] = v

        totals = tk.Frame(self.win, bg=BG)
        totals.pack(fill="x", padx=10, pady=4)
        self.totals = {}
        for i, (key, label) in enumerate((("dragons", _("Dragons")), ("equips", _("Equipements")),
                                          ("magic", "Raigeki / Dark Hole"))):
            f = tk.Frame(totals, bg=TILE_BG, highlightbackground=BORDER, highlightthickness=1)
            f.grid(row=0, column=i, sticky="ew", padx=2)
            totals.columnconfigure(i, weight=1)
            tk.Label(f, text=label, fg=TEXT, bg=TILE_BG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=8, pady=4)
            v = tk.Label(f, text="0", fg=TEXT, bg=TILE_BG, font=("Segoe UI", 12, "bold"))
            v.pack(side="right", padx=8)
            self.totals[key] = v

        grid = tk.Frame(self.win, bg=BG)
        grid.pack(padx=10, pady=(4, 10))
        self.tiles = {}
        for i, key in enumerate(TILES):
            lab = tk.Label(grid, bg=BG, bd=0, highlightbackground=BORDER, highlightthickness=1)
            lab.grid(row=i // 8, column=i % 8, padx=2, pady=2)
            if key == RAIGEKI:
                lab.bind("<Button-1>", lambda e: self.on_dark_hole())
                lab.configure(cursor="hand2")
            self.tiles[key] = lab
        self.update({f: 0 for f in fmlogic.F6_FIELDS}, False, [], None)

    # --- images ---------------------------------------------------------------------------

    def _load(self, name):
        path = os.path.join(self.folder, name + ".png")
        if os.path.exists(path):
            return Image.open(path).convert("RGB")
        return Image.new("RGB", (82, 76), "#30313a")

    def _image(self, name, size):
        key = (name, size)
        if key not in self.cache:
            self.cache[key] = ImageTk.PhotoImage(self._load(name).resize(size, Image.LANCZOS))
        return self.cache[key]

    def _tile(self, name, badge, active):
        key = (name, badge, active)
        if key not in self.cache:
            img = self._load(name).resize((CARD_W, CARD_H), Image.LANCZOS)
            if not active:
                img = ImageOps.grayscale(img).point(lambda v: int(v * 0.55)).convert("RGB")
            d = ImageDraw.Draw(img)
            w = max(26, int(d.textlength(badge, font=self.font)) + 10)
            d.rectangle((CARD_W - w - 3, CARD_H - 31, CARD_W - 3, CARD_H - 3), fill="#111214")
            d.text((CARD_W - 3 - w / 2, CARD_H - 17), badge, font=self.font, fill="#ffffff", anchor="mm")
            self.cache[key] = ImageTk.PhotoImage(img)
        return self.cache[key]

    # --- mise a jour ------------------------------------------------------------------------

    def update(self, counts, dark_hole, equips, result):
        state = (tuple(sorted(counts.items())), dark_hole, tuple(sorted(equips)),
                 None if result is None else tuple(sorted(result.items())))
        if state == self.last or not self.win.winfo_exists():
            return
        self.last = state
        for key, lab in self.tiles.items():
            if key == RAIGEKI:
                img = self._tile("dark_hole" if dark_hole else "raigeki", "DH" if dark_hole else "R", True)
            else:
                n = equips.count(key) if key in EQUIPS else int(counts.get(key, 0))
                img = self._tile(tile_file(key), str(n), n > 0)
            lab.configure(image=img)
        for name, lab in self.boss_pct.items():
            if result is None or name not in result:
                lab.configure(text="-", fg=DIM)
            else:
                p = result[name]
                lab.configure(text=f"{p * 100:.2f}%", fg=pct_color(p))
        self.totals["dragons"].configure(text=str(counts.get("dragonsUnder1600", 0) + counts.get("dragons1600Plus", 0)
                                                  + counts.get("thunderDragons", 0) + counts.get("mbd", 0)))
        self.totals["equips"].configure(text=str(len(equips) + counts.get("mm", 0)))
        self.totals["magic"].configure(text="Dark Hole" if dark_hole else "Raigeki")

    def geometry(self):
        return self.win.geometry() if self.win.winfo_exists() else None

    def close(self):
        geo = self.geometry()
        self.win.destroy()
        self.on_close(geo)


assert len(TILES) == 24 and set(f6calc.DUELISTS) <= set(BOSS_FILES)
