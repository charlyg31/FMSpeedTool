"""Fenetre Final 6 : boss et % de victoire, recap, cartes du deck en images.
Se remplit toute seule avec le deck lu et le calcul du panneau Final 6 (capturable dans OBS).

Personnalisable au clic droit : disposition, taille, parties affichees, cartes a 0 masquees,
cases masquees une par une ; les cartes se deplacent en les faisant glisser sur une autre
(les boss restent dans l'ordre du jeu)."""

import os
import tkinter as tk

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
SHOW_NAMES = (("show_bosses", N_("Boss")), ("show_rank", N_("Rang du duel en cours")), ("show_rates", N_("Taux de victoire")),
              ("show_names", N_("Noms des boss")), ("show_totals", N_("Recap (Dragons, Equipements...)")),
              ("show_cards", N_("Cartes")), ("hide_zero", N_("Masquer les cartes a 0")),
              ("topmost", N_("Toujours au premier plan")))
SCALES = (50, 60, 75, 90, 100, 125, 150)
# Fond de la fenetre : vert uni pour le rendre transparent dans OBS (filtre Cle chromatique)
BACKGROUNDS = {"dark": (BG, N_("Sombre")), "green": ("#00ff00", N_("Vert (cle chromatique OBS)"))}
DEFAULT_VIEW = {"layout": "horizontal", "scale": 100, "show_bosses": True, "show_rank": True, "show_rates": True,
                "show_names": True, "show_totals": True, "show_cards": True, "hide_zero": False,
                "topmost": False, "bg": "dark", "order": list(TILES), "boss_order": list(BOSSES), "hidden": []}


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
        self._rank_drawn = False
        self.drag = None
        self._hover = None
        self.body = None
        self.build()

    # --- construction -----------------------------------------------------------------------

    def s(self, n):
        return max(1, int(round(n * self.view["scale"] / 100)))

    def build(self):
        """(Re)construit la fenetre selon les reglages ; la taille suit le contenu."""
        v = self.view
        self.bg = BG = BACKGROUNDS[v["bg"]][0]
        self.win.configure(bg=BG)
        self.win.attributes("-topmost", bool(v["topmost"]))
        if self.body is not None:
            self.body.destroy()
        self.body = tk.Frame(self.win, bg=BG)
        self.body.pack(padx=self.s(10), pady=self.s(10))
        self.widgets = {}        # widget -> ("boss" | "card", cle) pour glisser / clic droit
        self.boss_pct, self.boss_tiles, self.tiles, self.totals = {}, {}, {}, {}
        boss_cols, card_cols, side = LAYOUTS[v["layout"]]
        pad = self.s(4)
        main = self.body
        if v["show_rank"] and boss_cols == 7:
            boss_cols = 8             # le rang a cote des 7 boss, sur la meme ligne
        self.rank_labels = None
        self._rank_drawn = False
        if v["show_bosses"] or v["show_rank"]:
            top = tk.Frame(main, bg=BG)
            top.pack(side="left" if side == "left" else "top", anchor="n", padx=(0, pad) if side == "left" else 0,
                     pady=(0, pad))
            shown = [b for b in v["boss_order"] if b not in v["hidden"]] if v["show_bosses"] else []
            if v["show_rank"]:
                shown.append(RANK)
            for i, name in enumerate(shown):
                if name == RANK:
                    self._rank_tile(top, i // boss_cols, i % boss_cols, pad)
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
            self.grid = tk.Frame(main, bg=BG, width=max(1, min(n, card_cols)) * cw,
                                 height=max(1, -(-n // card_cols)) * ch)
            self.grid.grid_propagate(False)
            self.grid.pack(anchor="w")
            self.card_cols = card_cols
        else:
            self.grid = None
        self._bind_all(self.win)
        self._last_state = None
        self.update(*self.inputs, force=True)
        if self.rank:
            self.set_rank(*self.rank)

    def _rank_tile(self, parent, row, col, pad):
        """Case du rang presume du duel en cours (meme rang que le panneau Rang)."""
        f = tk.Frame(parent, bg=TILE_BG, highlightbackground=BORDER, highlightthickness=max(1, self.s(2)))
        f.grid(row=row, column=col, padx=pad // 2 + 1, pady=pad // 2 + 1, sticky="nsew")
        inner = tk.Frame(f, bg=TILE_BG)
        inner.pack(expand=True, padx=self.s(8), pady=self.s(6))   # centre dans la hauteur de la ligne
        title = tk.Label(inner, text=_("Dernier duel"), fg=DIM, bg=TILE_BG, font=("Segoe UI", self.s(10), "bold"))
        title.pack()
        band = tk.Label(inner, text="-", fg=TEXT, bg=TILE_BG, font=("Segoe UI", self.s(22), "bold"))
        band.pack()
        score = tk.Label(inner, text="", fg=DIM, bg=TILE_BG, font=("Segoe UI", self.s(15), "bold"))
        score.pack()
        for w in (f, inner, title, band, score):
            self.widgets[w] = ("rank", RANK)
        self.rank_labels = (title, band, score)

    def set_rank(self, band, score, ok, in_duel):
        """Rang du duel en cours : vert quand il est dans l'objectif du panneau Rang.
        Appele 5 fois par seconde : rien n'est redessine si le rang n'a pas change."""
        if (band, score, ok, in_duel) == self.rank and self._rank_drawn:
            return
        self.rank = (band, score, ok, in_duel)
        self._rank_drawn = bool(self.rank_labels)
        if not self.rank_labels or not self.win.winfo_exists():
            return
        title, b, s = self.rank_labels
        title.configure(text=_("Duel en cours") if in_duel else _("Dernier duel"))
        color = "#5ac46e" if ok else TEXT
        b.configure(text=band, fg=color)
        s.configure(text=str(score), fg=color if ok else DIM)

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
                for i, key in enumerate(shown):
                    lab = tk.Label(self.grid, bg=self.bg, bd=0, highlightbackground=BORDER, highlightthickness=1,
                                   cursor="hand2" if key == RAIGEKI else "fleur")
                    lab.grid(row=i // self.card_cols, column=i % self.card_cols, padx=1, pady=1)
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

    # --- menu clic droit ----------------------------------------------------------------------

    def _menu(self, event):
        target = self._target(event)
        v = self.view
        m = tk.Menu(self.win, tearoff=0)
        lay = tk.Menu(m, tearoff=0)
        self._lay_var = tk.StringVar(value=v["layout"])
        for key, label in LAYOUT_NAMES.items():
            lay.add_radiobutton(label=_(label), value=key, variable=self._lay_var,
                                command=lambda k=key: self._set("layout", k))
        m.add_cascade(label=_("Disposition"), menu=lay)
        size = tk.Menu(m, tearoff=0)
        self._scale_var = tk.IntVar(value=v["scale"])
        for sc in SCALES:
            size.add_radiobutton(label=f"{sc} %", value=sc, variable=self._scale_var,
                                 command=lambda s=sc: self._set("scale", s))
        m.add_cascade(label=_("Taille"), menu=size)
        show = tk.Menu(m, tearoff=0)
        self._show_vars = {}
        for key, label in SHOW_NAMES:
            var = tk.BooleanVar(value=v[key])
            self._show_vars[key] = var
            show.add_checkbutton(label=_(label), variable=var, command=lambda k=key, x=var: self._set(k, x.get()))
        m.add_cascade(label=_("Afficher"), menu=show)
        bg = tk.Menu(m, tearoff=0)
        self._bg_var = tk.StringVar(value=v["bg"])
        for key, (_c, label) in BACKGROUNDS.items():
            bg.add_radiobutton(label=_(label), value=key, variable=self._bg_var, command=lambda k=key: self._set("bg", k))
        m.add_cascade(label=_("Fond"), menu=bg)
        m.add_separator()
        if target and target[0] == "rank":
            m.add_command(label=_("Masquer la case {name}", name=_("Rang du duel en cours")),
                          command=lambda: self._set("show_rank", False))
        elif target:
            kind, key = target
            label = key if kind == "boss" else self._card_name(key)
            m.add_command(label=_("Masquer la case {name}", name=label), command=lambda k=key: self._hide(k))
        hidden = v["hidden"]
        if hidden:
            back = tk.Menu(m, tearoff=0)
            for key in hidden:
                back.add_command(label=key if key in BOSSES else self._card_name(key),
                                 command=lambda k=key: self._unhide(k))
            back.add_separator()
            back.add_command(label=_("Toutes"), command=lambda: self._set("hidden", []))
            m.add_cascade(label=_("Reafficher une case"), menu=back)
        m.add_command(label=_("Ordre par defaut des cartes"),
                      command=lambda: self._set("order", list(TILES)))
        m.add_separator()
        m.add_command(label=_("Tout remettre par defaut"), command=self._reset)
        m.add_command(label=_("Astuce : glisse une carte sur une autre pour la deplacer"), state="disabled")
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

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
        self.view = clean_view(self.view)
        self.on_view(dict(self.view))
        self.win.geometry("")             # la taille suit le nouveau contenu
        self.build()

    def geometry(self):
        return self.win.geometry() if self.win.winfo_exists() else None

    def close(self):
        geo = self.geometry()
        self.win.destroy()
        self.on_close(geo)


assert len(TILES) == 24 and set(f6calc.DUELISTS) <= set(BOSS_FILES)
