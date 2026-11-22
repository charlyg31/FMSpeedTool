"""Fenetre Final 6 : boss et % de victoire, recap, cartes du deck en images.
Se remplit toute seule avec le deck lu et le calcul du panneau Final 6 (capturable dans OBS).

Personnalisable au clic droit : disposition, taille, parties affichees, cartes a 0 masquees,
cases masquees une par une ; les cartes se deplacent en les faisant glisser sur une autre
(les boss restent dans l'ordre du jeu)."""

import os
import re
import tkinter as tk
from tkinter import colorchooser

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageTk

import f6calc
import fmlogic
from i18n import N_, _

BG, TILE_BG, BORDER = "#111214", "#1c1d21", "#3a3b40"
TEXT, DIM, DROP = "#e8e8ea", "#9a9ba0", "#e0a64a"
EQUIPS = [e for e in fmlogic.F6_EQUIPS if e != "N/A"]
RAIGEKI = "raigeki"
TILES = fmlogic.F6_FIELDS + [RAIGEKI] + EQUIPS            # cases de cartes (ordre par defaut)
BOSS_FILES = {"Sebek": "boss_sebek", "Neku": "boss_neku", "Heishin": "boss_heishin",
              "Seto 3": "boss_seto3", "DarkNite": "boss_darknite", "Nitemare": "boss_nitemare",
              "Final 6": "boss_final6"}
BOSSES = list(BOSS_FILES)
CARD_W, CARD_H, BOSS = 104, 96, 84                          # tailles a 100 %

# Dispositions : (colonnes de boss, colonnes de cartes, boss en haut ou a gauche)
LAYOUTS = {"horizontal": (7, 8, "top"), "wide": (7, 12, "top"), "square": (4, 5, "top"),
           "vertical": (2, 3, "top"), "column": (2, 2, "top"), "side": (2, 6, "left")}
LAYOUT_NAMES = {"horizontal": N_("Horizontale (8 cartes par ligne)"), "wide": N_("Large (12 cartes par ligne)"),
                "square": N_("Carree (5 cartes par ligne)"), "vertical": N_("Verticale (3 cartes par ligne)"),
                "column": N_("Colonne etroite (2 cartes par ligne)"), "side": N_("Boss a gauche, cartes a droite")}
RANK = "rank"                                              # case du rang du duel en cours
STARS = "stars"                                            # case du total d'etoiles de la run
SHOW_NAMES = (("show_bosses", N_("Boss")), ("show_rank", N_("Rang du duel en cours")), ("show_stars", N_("Etoiles")),
              ("show_rates", N_("Taux de victoire")),
              ("show_names", N_("Noms des boss")), ("show_totals", N_("Recap (Dragons, Equipements...)")),
              ("show_cards", N_("Cartes")), ("hide_zero", N_("Masquer les cartes a 0")),
              ("topmost", N_("Toujours au premier plan")))
SCALES = (50, 60, 75, 90, 100, 125, 150)
# Fond de la fenetre : vert uni pour le rendre transparent dans OBS (filtre Cle chromatique)
BACKGROUNDS = {"dark": (BG, N_("Sombre")), "green": ("#00ff00", N_("Vert (cle chromatique OBS)"))}
DEFAULT_VIEW = {"layout": "horizontal", "scale": 100, "show_bosses": True, "show_rank": True, "show_stars": True,
                "show_rates": True,
                "show_names": True, "show_totals": True, "show_cards": True, "hide_zero": False,
                "topmost": False, "bg": "dark", "order": list(TILES), "boss_order": list(BOSSES), "hidden": [],
                # Rang du duel en cours : dans la fenetre ou dans sa propre fenetre, couleurs, fond
                "rank_window": False, "rank_color": TEXT, "score_color": DIM, "ok_color": "#5ac46e",
                "ok_on": True, "rank_bg": "dark", "rank_scale": 100, "rank_pos": ""}
COLOR_KEYS = ("rank_color", "score_color", "ok_color")


def tile_file(key):
    return "equip_" + key.lower().replace(" ", "_") if key in EQUIPS else key


def pct_color(p):
    """Rouge sous 50 %, orange jusqu'a 80 %, vert au-dessus."""
    return "#e05a5a" if p < 0.5 else "#e0a64a" if p < 0.8 else "#5ac46e"


def clean_view(view):
    """Reglages enregistres + valeurs par defaut ; ordre complete si des cases ont change."""
    v = dict(DEFAULT_VIEW)
    v.update({k: val for k, val in (view or {}).items() if k in DEFAULT_VIEW})
    v["boss_order"] = list(BOSSES)                         # boss : toujours dans l'ordre du jeu
    for key, full in (("order", TILES), ("boss_order", BOSSES)):
        seen = [k for k in v[key] if k in full]
        v[key] = list(dict.fromkeys(seen)) + [k for k in full if k not in seen]
    v["hidden"] = [k for k in v["hidden"] if k in TILES or k in BOSSES]
    if v["layout"] not in LAYOUTS:
        v["layout"] = "horizontal"
    if v["bg"] not in BACKGROUNDS:
        v["bg"] = "dark"
    if v["scale"] not in SCALES:
        v["scale"] = 100
    if v["rank_bg"] not in BACKGROUNDS:
        v["rank_bg"] = "dark"
    if v["rank_scale"] not in SCALES:
        v["rank_scale"] = 100
    for key in COLOR_KEYS:
        if not (isinstance(v[key], str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v[key])):
            v[key] = DEFAULT_VIEW[key]
    if not (isinstance(v["rank_pos"], str) and re.fullmatch(r"([+-]\d+){2}|", v["rank_pos"])):
        v["rank_pos"] = ""
    return v


def _font(size):
    for name in ("segoeuib.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


class F6Window:
    def __init__(self, root, folder, on_dark_hole, on_close, geometry=None, view=None, on_view=None):
        self.folder = folder
        self.on_dark_hole = on_dark_hole
        self.on_close = on_close
        self.on_view = on_view or (lambda v: None)
        self.view = clean_view(view)
        self.win = tk.Toplevel(root, bg=BG)
        self.win.title("Final 6")
        if geometry:   # position seulement : la taille suit le contenu
            pos = geometry[geometry.find("+"):] if "+" in geometry else ""
            if pos:
                self.win.geometry(pos)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.cache = {}
        self.inputs = ({f: 0 for f in fmlogic.F6_FIELDS}, False, [], None)
        self.rank = None              # (rang, score, dans l'objectif, en duel)
        self.stars = 0                # total d'etoiles de la run
        self.stars_label = None
        self._rank_drawn = False
        self.drag = None
        self._hover = None
        self.body = None
        self.rank_win = None          # fenetre a part du rang (reglage "rank_window")
        self.build()

    # --- construction -----------------------------------------------------------------------

    def s(self, n):
        return max(1, int(round(n * self.view["scale"] / 100)))

    def build(self):
        """(Re)construit la fenetre selon les reglages ; la taille suit le contenu.
        Le nouveau contenu est prepare hors de l'ecran puis echange avec l'ancien d'un coup :
        detruit d'abord, la fenetre restait noire le temps de refaire les images."""
        v = self.view
        self.bg = BG = BACKGROUNDS[v["bg"]][0]
        old = self.body
        self.body = tk.Frame(self.win, bg=BG)
        self.widgets = {}        # widget -> ("boss" | "card", cle) pour glisser / clic droit
        self.boss_pct, self.boss_tiles, self.tiles, self.totals = {}, {}, {}, {}
        boss_cols, card_cols, side = LAYOUTS[v["layout"]]
        pad = self.s(4)
        main = self.body
        rank_here = v["show_rank"] and not v["rank_window"]
        stars_here = v["show_stars"]
        if boss_cols == 7:
            boss_cols += rank_here + stars_here   # rang et etoiles a cote des 7 boss, meme ligne
        self.rank_labels = None
        self.stars_label = None
        self._rank_drawn = False
        if v["show_bosses"] or rank_here or stars_here:
            top = tk.Frame(main, bg=BG)
            top.pack(side="left" if side == "left" else "top", anchor="n", padx=(0, pad) if side == "left" else 0,
                     pady=(0, pad))
            shown = [b for b in v["boss_order"] if b not in v["hidden"]] if v["show_bosses"] else []
            if rank_here:
                shown.append(RANK)
            if stars_here:
                shown.append(STARS)
            for i, name in enumerate(shown):
                if name == RANK:
                    self._rank_tile(top, i // boss_cols, i % boss_cols, pad)
                    continue
                if name == STARS:
                    self._stars_tile(top, i // boss_cols, i % boss_cols, pad)
                    continue
                f = tk.Frame(top, bg=TILE_BG, highlightbackground=BORDER, highlightthickness=max(1, self.s(2)))
                f.grid(row=i // boss_cols, column=i % boss_cols, padx=pad // 2 + 1, pady=pad // 2 + 1, sticky="nsew")
                img = tk.Label(f, image=self._image(BOSS_FILES[name], (self.s(BOSS), self.s(BOSS))), bg=TILE_BG)
                img.pack(padx=self.s(8), pady=(self.s(8), self.s(2)))
                parts = [f, img]
                if v["show_names"]:
                    lab = tk.Label(f, text=name, fg=TEXT, bg=TILE_BG, font=("Segoe UI", self.s(10), "bold"))
                    lab.pack()
                    parts.append(lab)
                if v["show_rates"]:
                    pct = tk.Label(f, text="-", fg=DIM, bg=TILE_BG, font=("Segoe UI", self.s(15), "bold"))
                    pct.pack(pady=(0, self.s(6)))
                    self.boss_pct[name] = pct
                    parts.append(pct)
                else:
                    tk.Frame(f, bg=TILE_BG, height=self.s(6)).pack()
                for w in parts:
                    self.widgets[w] = ("boss", name)
                self.boss_tiles[name] = f
            main = tk.Frame(main, bg=BG)
            main.pack(side="left" if side == "left" else "top", anchor="n")
        if v["show_totals"]:
            totals = tk.Frame(main, bg=BG)
            totals.pack(fill="x", pady=(0, pad))
            items = (("dragons", _("Dragons")), ("equips", _("Equipements")), ("magic", "Raigeki / Dark Hole"))
            narrow = card_cols <= 3
            for i, (key, label) in enumerate(items):
                f = tk.Frame(totals, bg=TILE_BG, highlightbackground=BORDER, highlightthickness=1)
                if narrow:
                    f.grid(row=i, column=0, sticky="ew", pady=1)
                    totals.columnconfigure(0, weight=1)
                else:
                    f.grid(row=0, column=i, sticky="ew", padx=1)
                    totals.columnconfigure(i, weight=1)
                tk.Label(f, text=label, fg=TEXT, bg=TILE_BG, font=("Segoe UI", self.s(10), "bold")).pack(
                    side="left", padx=self.s(8), pady=self.s(4))
                val = tk.Label(f, text="0", fg=TEXT, bg=TILE_BG, font=("Segoe UI", self.s(12), "bold"))
                val.pack(side="right", padx=self.s(8))
                self.totals[key] = val
        if v["show_cards"]:
            # Zone des cartes de taille fixe (toutes les cases non masquees) : avec les cartes
            # a 0 masquees, les cartes se regroupent en haut mais la fenetre ne change pas de
            # taille (source OBS stable).
            n = len([k for k in v["order"] if k not in v["hidden"]])
            cw, ch = self.s(CARD_W) + 4, self.s(CARD_H) + 4
            self._cell = (cw, ch)
            self._grid_w = max(1, min(n, card_cols)) * cw
            self.grid = tk.Frame(main, bg=BG, width=self._grid_w, height=max(1, -(-n // card_cols)) * ch)
            self.grid.grid_propagate(False)
            self.grid.pack(anchor="w")
            self.card_cols = card_cols
        else:
            self.grid = None
        self._bind_all(self.body)
        self._last_state = None
        self.update(*self.inputs, force=True)
        if self.rank:
            self.set_rank(*self.rank)
        self.body.update_idletasks()        # tout est pret avant l'echange
        self.win.configure(bg=BG)
        self.win.attributes("-topmost", bool(v["topmost"]))
        if old is not None:
            old.destroy()
        self.body.pack(padx=self.s(10), pady=self.s(10))
        self.win.bind("<Button-3>", self._menu)
        self._sync_rank_window()

    def _rank_tile(self, parent, row, col, pad):
        """Case du rang presume du duel en cours (meme rang que le panneau Rang)."""
        f = tk.Frame(parent, bg=TILE_BG, highlightbackground=BORDER, highlightthickness=max(1, self.s(2)))
        f.grid(row=row, column=col, padx=pad // 2 + 1, pady=pad // 2 + 1, sticky="nsew")
        inner = tk.Frame(f, bg=TILE_BG)
        inner.pack(expand=True, padx=self.s(8), pady=self.s(6))   # centre dans la hauteur de la ligne
        band = tk.Label(inner, text="-", fg=self.view["rank_color"], bg=TILE_BG, font=("Segoe UI", self.s(22), "bold"))
        band.pack()
        score = tk.Label(inner, text="", fg=self.view["score_color"], bg=TILE_BG, font=("Segoe UI", self.s(15), "bold"))
        score.pack()
        for w in (f, inner, band, score):
            self.widgets[w] = ("rank", RANK)
        self.rank_labels = (band, score)

    def _stars_tile(self, parent, row, col, pad):
        """Case du total d'etoiles (starchips) de la run."""
        f = tk.Frame(parent, bg=TILE_BG, highlightbackground=BORDER, highlightthickness=max(1, self.s(2)))
        f.grid(row=row, column=col, padx=pad // 2 + 1, pady=pad // 2 + 1, sticky="nsew")
        inner = tk.Frame(f, bg=TILE_BG)
        inner.pack(expand=True, padx=self.s(8), pady=self.s(6))
        star = tk.Label(inner, text="\u2605", fg="#f2d33a", bg=TILE_BG, font=("Segoe UI Symbol", self.s(24)))
        star.pack()
        num = tk.Label(inner, text=str(self.stars), fg=TEXT, bg=TILE_BG, font=("Segoe UI", self.s(18), "bold"))
        num.pack()
        for w in (f, inner, star, num):
            self.widgets[w] = ("stars", STARS)
        self.stars_label = num

    def set_stars(self, n):
        """Total d'etoiles de la run (appele a chaque changement)."""
        self.stars = n
        lab = self.stars_label
        if lab is not None and lab.winfo_exists():
            lab.configure(text=str(n))

    def set_rank(self, band, score, ok, in_duel):
        """Rang du duel en cours : vert quand il est dans l'objectif du panneau Rang.
        Appele 5 fois par seconde : rien n'est redessine si le rang n'a pas change."""
        if (band, score, ok, in_duel) == self.rank and self._rank_drawn:
            return
        self.rank = (band, score, ok, in_duel)
        labels = [lab for lab in (self.rank_labels, getattr(self, "rank_win_labels", None)) if lab]
        self._rank_drawn = bool(labels)
        if not self.win.winfo_exists():
            return
        v = self.view
        special = ok and v["ok_on"]
        for b, s in labels:
            if b.winfo_exists():
                b.configure(text=band, fg=v["ok_color"] if special else v["rank_color"])
                s.configure(text=str(score), fg=v["ok_color"] if special else v["score_color"])

    # --- rang dans sa propre fenetre (a capturer seul dans OBS) ---------------------------------

    def _sync_rank_window(self):
        """Cree, refait ou ferme la fenetre a part du rang selon les reglages."""
        v = self.view
        want = v["show_rank"] and v["rank_window"]
        if not want:
            self._close_rank_window()
            return
        if self.rank_win is None or not self.rank_win.winfo_exists():
            rw = self.rank_win = tk.Toplevel(self.win.master)
            rw.title(_("Rang du duel en cours"))
            rw.protocol("WM_DELETE_WINDOW", self._rank_window_closed)
            if v["rank_pos"]:
                rw.geometry(v["rank_pos"])
            rw.bind("<Configure>", lambda e: self._rank_window_moved())
            self._rank_body = None
        rw = self.rank_win
        bg = BACKGROUNDS[v["rank_bg"]][0]
        k = v["rank_scale"] / 100
        rw.configure(bg=bg)
        rw.attributes("-topmost", bool(v["topmost"]))
        old = self._rank_body
        body = self._rank_body = tk.Frame(rw, bg=bg)
        band = tk.Label(body, text="-", bg=bg, font=("Segoe UI", max(8, int(40 * k)), "bold"))
        band.pack(padx=int(18 * k), pady=(int(10 * k), 0))
        score = tk.Label(body, text="", bg=bg, font=("Segoe UI", max(8, int(26 * k)), "bold"))
        score.pack(pady=(0, int(10 * k)))
        for w in (rw, body, band, score):
            w.bind("<Button-3>", self._rank_menu)
        if old is not None:
            old.destroy()
        body.pack(expand=True)
        rw.geometry("")
        self.rank_win_labels = (band, score)
        self._rank_drawn = False
        if self.rank:
            self.set_rank(*self.rank)
        else:
            band.configure(fg=v["rank_color"])

    def _rank_menu(self, event):
        self._open_panel(event.x_root, event.y_root, ("rankwin", RANK))
        return "break"

    def _rank_window_moved(self):
        rw = self.rank_win
        if rw is not None and rw.winfo_exists():
            pos = rw.geometry()
            pos = pos[pos.find("+"):] if "+" in pos else ""
            if pos and pos != self.view["rank_pos"]:
                self.view["rank_pos"] = pos
                if getattr(self, "_pos_job", None) is None:      # enregistre une fois le deplacement fini
                    self._pos_job = self.win.after(800, self._save_rank_pos)

    def _save_rank_pos(self):
        self._pos_job = None
        self.on_view(dict(self.view))

    def _rank_window_closed(self):
        """Fenetre du rang fermee : le rang revient dans la fenetre Final 6."""
        self._set("rank_window", False)

    def _close_rank_window(self):
        rw, self.rank_win = self.rank_win, None
        self.rank_win_labels = None
        if rw is not None and rw.winfo_exists():
            pos = rw.geometry()
            if "+" in pos:
                self.view["rank_pos"] = pos[pos.find("+"):]
            rw.destroy()

    def _bind_all(self, w):
        w.bind("<Button-3>", self._menu)
        for c in w.winfo_children():
            self._bind_all(c)

    def _bind_card(self, w):
        w.bind("<Button-3>", self._menu)
        w.bind("<ButtonPress-1>", self._press)
        w.bind("<B1-Motion>", self._motion)
        w.bind("<ButtonRelease-1>", self._release)

    # --- images -------------------------------------------------------------------------------

    def _load(self, name):
        path = os.path.join(self.folder, name + ".png")
        if os.path.exists(path):
            return Image.open(path).convert("RGB")
        return Image.new("RGB", (102, 96), "#30313a")

    def _image(self, name, size):
        key = (name, size)
        if key not in self.cache:
            self.cache[key] = ImageTk.PhotoImage(self._load(name).resize(size, Image.LANCZOS))
        return self.cache[key]

    def _tile(self, name, badge, active):
        w, h = self.s(CARD_W), self.s(CARD_H)
        key = (name, badge, active, w)
        if key not in self.cache:
            img = self._load(name).resize((w, h), Image.LANCZOS)
            if not active:
                img = ImageOps.grayscale(img).point(lambda x: int(x * 0.55)).convert("RGB")
            d = ImageDraw.Draw(img)
            font = _font(self.s(20))
            bw = max(self.s(26), int(d.textlength(badge, font=font)) + self.s(10))
            m = self.s(3)
            d.rectangle((w - bw - m, h - self.s(31), w - m, h - m), fill="#111214")
            d.text((w - m - bw / 2, h - self.s(17)), badge, font=font, fill="#ffffff", anchor="mm")
            self.cache[key] = ImageTk.PhotoImage(img)
        return self.cache[key]

    # --- mise a jour --------------------------------------------------------------------------

    def update(self, counts, dark_hole, equips, result, force=False):
        if not self.win.winfo_exists():
            return
        self.inputs = (counts, dark_hole, equips, result)
        state = (tuple(sorted(counts.items())), dark_hole, tuple(sorted(equips)),
                 None if result is None else tuple(sorted(result.items())))
        if state == self._last_state and not force:
            return
        self._last_state = state
        v = self.view
        if self.grid is not None:
            n_of = {k: (equips.count(k) if k in EQUIPS else int(counts.get(k, 0))) for k in TILES}
            shown = [k for k in v["order"] if k not in v["hidden"]
                     and not (v["hide_zero"] and k != RAIGEKI and n_of[k] == 0)]
            if shown != list(self.tiles):           # cases a (re)placer
                for lab in self.tiles.values():
                    self.widgets.pop(lab, None)
                    lab.destroy()
                self.tiles = {}
                cols, (cw, ch) = self.card_cols, self._cell
                for i, key in enumerate(shown):
                    lab = tk.Label(self.grid, bg=self.bg, bd=0, highlightbackground=BORDER, highlightthickness=1,
                                   cursor="hand2" if key == RAIGEKI else "fleur")
                    # Cartes centrees sous les boss : une ligne incomplete (cartes a 0 masquees)
                    # est centree dans la zone, au lieu d'etre collee a gauche.
                    row, col = divmod(i, cols)
                    in_row = min(cols, len(shown) - row * cols)
                    x0 = (self._grid_w - in_row * cw) / 2
                    lab.place(x=int(x0 + col * cw) + 1, y=row * ch + 1)
                    self.widgets[lab] = ("card", key)
                    self._bind_card(lab)
                    self.tiles[key] = lab
            for key, lab in self.tiles.items():
                if key == RAIGEKI:
                    img = self._tile("dark_hole" if dark_hole else "raigeki", "DH" if dark_hole else "R", True)
                else:
                    img = self._tile(tile_file(key), str(n_of[key]), n_of[key] > 0)
                lab.configure(image=img)
        for name, lab in self.boss_pct.items():
            if result is None or name not in result:
                lab.configure(text="-", fg=DIM)
            else:
                p = result[name]
                lab.configure(text=f"{p * 100:.2f}%", fg=pct_color(p))
        if self.totals:
            self.totals["dragons"].configure(text=str(counts.get("dragonsUnder1600", 0) + counts.get("dragons1600Plus", 0)
                                                      + counts.get("thunderDragons", 0) + counts.get("mbd", 0)))
            self.totals["equips"].configure(text=str(len(equips) + counts.get("mm", 0)))
            self.totals["magic"].configure(text="Dark Hole" if dark_hole else "Raigeki")

    # --- glisser une case sur une autre : elle prend sa place -----------------------------------

    def _target(self, event):
        w = self.win.winfo_containing(event.x_root, event.y_root)
        while w is not None and w not in self.widgets:
            w = getattr(w, "master", None)
        return self.widgets.get(w) if w is not None else None

    def _press(self, event):
        self.drag = self.widgets.get(event.widget)

    def _motion(self, event):
        if not self.drag:
            return
        tgt = self._target(event)
        widget = None
        if tgt and tgt[0] == "card" and tgt != self.drag:
            widget = self.tiles.get(tgt[1])
        if widget is not (self._hover[0] if self._hover else None):
            self._unhover()
            if widget is not None:
                self._hover = (widget, widget.cget("highlightthickness"))
                widget.configure(highlightbackground=DROP, highlightthickness=max(2, self._hover[1]))

    def _unhover(self):
        if self._hover and self._hover[0].winfo_exists():
            self._hover[0].configure(highlightbackground=BORDER, highlightthickness=self._hover[1])
        self._hover = None

    def _release(self, event):
        src, self.drag = self.drag, None
        self._unhover()
        tgt = self._target(event)
        if not src:
            return
        if tgt == src:
            if src[1] == RAIGEKI:          # simple clic : Raigeki <-> Dark Hole
                self.on_dark_hole()
            return
        if tgt and tgt[0] == src[0] == "card":     # les boss restent a leur place
            self._move("order", src[1], tgt[1])

    def _move(self, key, src, dst):
        """La case glissee prend la place de celle ou on la lache (les autres se decalent)."""
        order = self.view[key]
        j = order.index(dst)
        order.remove(src)
        order.insert(j, src)
        self._changed()

    # --- reglages au clic droit : panneau qui reste ouvert ---------------------------------------

    PANEL_BG, PANEL_HEAD = "#1c1d21", "#e0a64a"

    def _menu(self, event):
        self._open_panel(event.x_root, event.y_root, self._target(event))
        # Un seul panneau par clic : la fenetre recoit aussi le clic fait sur une case.
        return "break"

    def _open_panel(self, x, y, target):
        """Panneau des reglages : reste ouvert pendant qu'on coche, chaque reglage s'applique
        tout de suite ; un clic ailleurs ou Echap le ferme. (Le menu de Windows se fermait a
        chaque choix ; le rouvrir le faisait clignoter.)"""
        self._close_panel()
        v = self.view
        bg, fg = self.PANEL_BG, TEXT
        p = self.panel = tk.Toplevel(self.win, bg=BORDER)
        p.overrideredirect(True)
        p.attributes("-topmost", True)
        body = tk.Frame(p, bg=bg, padx=10, pady=8)
        body.pack(padx=1, pady=1)
        font, bold = ("Segoe UI", 10), ("Segoe UI", 10, "bold")
        opts = dict(bg=bg, fg=fg, activebackground=bg, activeforeground=fg, selectcolor="#2c2d33",
                    font=font, anchor="w", highlightthickness=0, bd=0)

        def head(parent, text):
            tk.Label(parent, text=text, bg=bg, fg=self.PANEL_HEAD, font=bold).pack(anchor="w", pady=(6, 1))

        cols = tk.Frame(body, bg=bg)
        cols.pack(fill="x")
        left, right, third = tk.Frame(cols, bg=bg), tk.Frame(cols, bg=bg), tk.Frame(cols, bg=bg)
        left.pack(side="left", anchor="n", padx=(0, 18))
        right.pack(side="left", anchor="n", padx=(0, 18))
        third.pack(side="left", anchor="n")
        self._panel_vars = {}
        head(left, _("Disposition"))
        lay = tk.StringVar(p, v["layout"])
        for key, label in LAYOUT_NAMES.items():
            tk.Radiobutton(left, text=_(label), value=key, variable=lay,
                           command=lambda: self._set("layout", lay.get()), **opts).pack(anchor="w")
        head(left, _("Taille"))
        sizes = tk.Frame(left, bg=bg)
        sizes.pack(anchor="w")
        sc = tk.IntVar(p, v["scale"])
        for i, n in enumerate(SCALES):
            tk.Radiobutton(sizes, text=f"{n} %", value=n, variable=sc, indicatoron=False, width=5,
                           command=lambda: self._set("scale", sc.get()),
                           **{**opts, "anchor": "center", "selectcolor": "#3a3b40"}).grid(
                row=i // 4, column=i % 4, padx=1, pady=1)
        head(left, _("Fond"))
        bgv = tk.StringVar(p, v["bg"])
        for key, (_c, label) in BACKGROUNDS.items():
            tk.Radiobutton(left, text=_(label), value=key, variable=bgv,
                           command=lambda: self._set("bg", bgv.get()), **opts).pack(anchor="w")
        head(right, _("Afficher"))
        for key, label in SHOW_NAMES:
            var = tk.BooleanVar(p, v[key])
            self._panel_vars[key] = var
            tk.Checkbutton(right, text=_(label), variable=var,
                           command=lambda k=key, x=var: self._set(k, x.get()), **opts).pack(anchor="w")
        head(right, _("Cases"))
        bopts = dict(bg="#2c2d33", fg=fg, activebackground="#3a3b40", activeforeground=fg, font=font,
                     relief="flat", bd=0, padx=8, pady=2, anchor="w", cursor="hand2")
        if target and target[0] == "rankwin":
            pass
        elif target and target[0] == "stars":
            tk.Button(right, text=_("Masquer la case {name}", name=_("Etoiles")),
                      command=lambda: self._panel_do(lambda: self._set("show_stars", False)), **bopts).pack(
                fill="x", pady=1)
        elif target and target[0] == "rank":
            tk.Button(right, text=_("Masquer la case {name}", name=_("Rang du duel en cours")),
                      command=lambda: self._panel_do(lambda: self._set("show_rank", False)), **bopts).pack(
                fill="x", pady=1)
        elif target and target[1] not in v["hidden"]:
            label = target[1] if target[0] == "boss" else self._card_name(target[1])
            tk.Button(right, text=_("Masquer la case {name}", name=label),
                      command=lambda k=target[1]: self._panel_do(lambda: self._hide(k)), **bopts).pack(
                fill="x", pady=1)
        if v["hidden"]:
            tk.Button(right, text=_("Reafficher les cases masquees ({n})", n=len(v["hidden"])),
                      command=lambda: self._panel_do(lambda: self._set("hidden", [])), **bopts).pack(
                fill="x", pady=1)
        tk.Button(right, text=_("Ordre par defaut des cartes"),
                  command=lambda: self._set("order", list(TILES)), **bopts).pack(fill="x", pady=1)
        tk.Button(right, text=_("Tout remettre par defaut"),
                  command=lambda: self._panel_do(self._reset), **bopts).pack(fill="x", pady=1)
        # Rang du duel en cours : fenetre a part, couleurs, fond et taille de sa fenetre.
        head(third, _("Rang du duel en cours"))
        for key, label in (("rank_window", N_("Dans une fenetre a part")),
                           ("ok_on", N_("Couleur speciale dans l'objectif"))):
            var = tk.BooleanVar(p, v[key])
            tk.Checkbutton(third, text=_(label), variable=var,
                           command=lambda k=key, x=var: self._panel_do(lambda: self._set(k, x.get())),
                           **opts).pack(anchor="w")
        for key, label in (("rank_color", N_("Couleur du rang")), ("score_color", N_("Couleur du score")),
                           ("ok_color", N_("Couleur dans l'objectif"))):
            row = tk.Frame(third, bg=bg)
            row.pack(fill="x", pady=1)
            tk.Label(row, bg=v[key], width=2, relief="flat", bd=0).pack(side="left", padx=(0, 6), ipady=3)
            tk.Button(row, text=_(label) + "...", command=lambda k=key, t=label: self._pick_color(k, t),
                      **bopts).pack(side="left", fill="x", expand=True)
        tk.Button(third, text=_("Couleurs d'origine"),
                  command=lambda: self._panel_do(self._reset_colors), **bopts).pack(fill="x", pady=1)
        if v["rank_window"]:
            head(third, _("Fenetre du rang"))
            rbg = tk.StringVar(p, v["rank_bg"])
            for key, (_c, label) in BACKGROUNDS.items():
                tk.Radiobutton(third, text=_(label), value=key, variable=rbg,
                               command=lambda: self._set("rank_bg", rbg.get()), **opts).pack(anchor="w")
            rsizes = tk.Frame(third, bg=bg)
            rsizes.pack(anchor="w", pady=(2, 0))
            rsc = tk.IntVar(p, v["rank_scale"])
            for i, n in enumerate(SCALES):
                tk.Radiobutton(rsizes, text=f"{n} %", value=n, variable=rsc, indicatoron=False, width=5,
                               command=lambda: self._set("rank_scale", rsc.get()),
                               **{**opts, "anchor": "center", "selectcolor": "#3a3b40"}).grid(
                    row=i // 4, column=i % 4, padx=1, pady=1)
        tk.Label(body, text=_("Astuce : glisse une carte sur une autre pour la deplacer"),
                 bg=bg, fg=DIM, font=("Segoe UI", 9)).pack(anchor="w", pady=(8, 0))
        # Pres du curseur, sans deborder de l'ecran.
        p.update_idletasks()
        w, h = p.winfo_reqwidth(), p.winfo_reqheight()
        x = max(0, min(x, p.winfo_screenwidth() - w - 4))
        y = max(0, min(y, p.winfo_screenheight() - h - 48))
        p.geometry(f"+{x}+{y}")
        self._panel_at = (x, y, target)
        p.bind("<Escape>", lambda e: self._close_panel())
        p.bind("<FocusOut>", lambda e: p.after(80, self._panel_focus_check))
        p.focus_force()

    def _reset_colors(self):
        """Couleurs du rang, du score et de l'objectif remises comme a l'origine."""
        for key in COLOR_KEYS:
            self.view[key] = DEFAULT_VIEW[key]
        self._changed()

    def _pick_color(self, key, label):
        """Choix d'une couleur (fenetre de Windows) ; le panneau est refait ensuite."""
        def choose():
            rgb, hexa = colorchooser.askcolor(color=self.view[key], parent=self.win, title=_(label))
            if hexa:
                self._set(key, hexa.lower())
        self._close_panel()
        self._panel_do(choose)

    def _panel_focus_check(self):
        """Ferme le panneau quand on clique ailleurs (le focus a quitte le panneau)."""
        p = getattr(self, "panel", None)
        if p is None or not p.winfo_exists():
            return
        f = p.focus_get()
        if f is None or not str(f).startswith(str(p)):
            self._close_panel()

    def _panel_do(self, action):
        """Reglage qui change le contenu du panneau lui-meme (cases masquees, tout par defaut) :
        le panneau est refait au meme endroit."""
        action()
        if getattr(self, "_panel_at", None):
            x, y, target = self._panel_at
            self.win.after(40, lambda: self.win.winfo_exists() and self._open_panel(x, y, target))

    def _close_panel(self):
        p = getattr(self, "panel", None)
        self.panel = None
        if p is not None and p.winfo_exists():
            p.destroy()

    @staticmethod
    def _card_name(key):
        if key == RAIGEKI:
            return "Raigeki / Dark Hole"
        return fmlogic.F6_LABELS.get(key, key).split(" (")[0]

    def _set(self, key, value):
        self.view[key] = value
        self._changed()

    def _hide(self, key):
        if key not in self.view["hidden"]:
            self.view["hidden"].append(key)
        self._changed()

    def _unhide(self, key):
        self.view["hidden"] = [k for k in self.view["hidden"] if k != key]
        self._changed()

    def _reset(self):
        self.view = clean_view(None)
        self._changed()

    def _changed(self):
        """Reglage change : applique au prochain passage de la boucle (plusieurs reglages
        d'affilee ne reconstruisent la fenetre qu'une fois)."""
        if getattr(self, "_pending", None) is None:
            self._pending = self.win.after(10, self._apply_change)

    def _apply_change(self):
        self._pending = None
        if not self.win.winfo_exists():
            return
        self.view = clean_view(self.view)
        self.on_view(dict(self.view))
        self.win.geometry("")             # la taille suit le nouveau contenu
        self.build()
        self.win.update_idletasks()


    def geometry(self):
        return self.win.geometry() if self.win.winfo_exists() else None

    def close(self):
        self._close_panel()
        self._close_rank_window()
        self.on_view(dict(self.view))     # position de la fenetre du rang
        geo = self.geometry()
        self.win.destroy()
        self.on_close(geo)


assert len(TILES) == 24 and set(f6calc.DUELISTS) <= set(BOSS_FILES)
