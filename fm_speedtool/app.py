"""FM Speed Tool : autosplit LiveSplit, rang A-TEC et Final 6 par analyse d'image.
Tout est sur une seule page."""

import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

import cv2
from PIL import Image, ImageTk

import capture
import deckscreen
import f6calc
import fmlogic
import i18n
import livesplit_bridge
import passwords
import tracker
import vision
from i18n import _
from livesplit import LiveSplitClient

APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "FMSpeedTool")
BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
BUILTIN_DIR = os.path.join(BASE_DIR, "assets", "builtin")
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
PREVIEW = (480, 384)   # apercu de la fenetre d'apprentissage
FPS_TARGET = 60

DEFAULT_CONFIG = {
    "host": "localhost", "port": 16834,
    "language": "",               # "" = langue de Windows (francais ou anglais)
    "livesplit_mode": "script",   # "script" (FMSpeedTool.asl) ou "tcp" (serveur TCP)
    "options": {"split_first_loss": True, "auto_reset": True, "auto_start": True, "split_farm_v2": False},
    "f6": {f: 0 for f in fmlogic.F6_FIELDS}, "dark_hole": False, "equips": ["N/A"] * 6,
}


def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            saved = json.load(f)
        for k, v in saved.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    except (OSError, ValueError):
        pass
    return cfg


class Worker(threading.Thread):
    """Capture + analyse en continu ; pilote LiveSplit."""

    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.cap = capture.WindowCapture()
        self.events = queue.Queue()
        self.lock = threading.Lock()
        self.window_ok = False
        self.fps = 0.0
        self.running = True

    def on_event(self, kind, msg):
        self.events.put((kind, msg))
        if kind not in ("split", "new_run"):
            return
        opts = self.app.tracker.options
        if self.app.cfg["livesplit_mode"] == "script":
            # Le script FMSpeedTool.asl lit ces compteurs ; ses cases Start/Split/Reset decident.
            bridge = self.app.bridge
            if bridge is None:
                return
            if kind == "split":
                bridge.split(*self.app.tracker.last_split)
            else:
                bridge.reset()
                bridge.start()
            return
        ls = self.app.livesplit
        try:
            if kind == "split":
                ls.split()
            else:
                if opts["auto_reset"]:
                    ls.reset()
                if opts["auto_start"]:
                    ls.start()
        except OSError:
            self.events.put(("error", _("LiveSplit injoignable (serveur TCP demarre ?)")))

    def run(self):
        frames, t0 = 0, time.monotonic()
        while self.running:
            start = time.monotonic()
            try:
                frame = self.cap.grab()
            except OSError:
                frame = None
            self.window_ok = frame is not None
            if frame is not None:
                with self.lock:
                    self.app.tracker.process(frame)
                frames += 1
                if self.app.bridge is not None:
                    self.app.bridge.beat()
            else:
                # Jeu masque ou ferme : on ne garde pas un ecran PASSWORD perime.
                self.app.tracker.on_password_screen = False
            if time.monotonic() - t0 >= 1.0:
                self.fps = frames / (time.monotonic() - t0)
                frames, t0 = 0, time.monotonic()
            time.sleep(max(0.0, 1.0 / FPS_TARGET - (time.monotonic() - start)))


class App:
    def __init__(self, root):
        self.root = root
        root.title("FM Speed Tool")
        root.geometry("1440x940")
        root.minsize(1100, 700)
        os.makedirs(APP_DIR, exist_ok=True)
        self.cfg = load_config()
        i18n.set_language(self.cfg.get("language") or i18n.system_language())
        root.title(_("FM Speed Tool - Forbidden Memories (analyse d'image)"))
        try:
            self.bridge = livesplit_bridge.Bridge()
        except OSError:
            self.bridge = None            # memoire partagee indisponible : TCP seulement
        self.livesplit = LiveSplitClient(self.cfg["host"], int(self.cfg["port"]))
        self.digits = vision.DigitReader(os.path.join(APP_DIR, "digits.json"),
                                         os.path.join(BASE_DIR, "assets", "digits_default.json"))
        self.builtin = vision.TemplateLibrary(BUILTIN_DIR)
        self.learned = vision.TemplateLibrary(os.path.join(APP_DIR, "templates"))
        self.worker = None
        self.deck = deckscreen.DeckReader(os.path.join(BASE_DIR, "assets"))
        self._deck_version = -1
        self.tracker = tracker.Tracker(self.digits, self.builtin, self.learned,
                                       lambda k, m: self.worker.on_event(k, m), deck=self.deck)
        self.tracker.options.update(self.cfg["options"])
        self.worker = Worker(self)

        page = self.page = ttk.Frame(root, padding=6)
        page.pack(fill="both", expand=True)
        page.columnconfigure(0, weight=2)
        page.columnconfigure(1, weight=2)
        page.columnconfigure(2, weight=3)
        page.rowconfigure(1, weight=1)
        page.rowconfigure(2, weight=0)   # barre "Apprentissage" + chiffres : compacte

        self._build_status(page)
        self._build_rank(self._box(page, _("Duel en cours - rang"), 1, 0))
        self._build_f6(self._box(page, "Final 6", 1, 1))
        self._build_log(self._box(page, _("Historique des duels"), 1, 2))
        self._build_learn(self._box(page, _("Apprentissage"), 2, 0, colspan=2))
        self._build_digits(self._box(page, _("Chiffres a nommer"), 2, 2))
        self._build_passwords()

        self.worker.start()
        if self.cfg["livesplit_mode"] == "tcp":
            self._connect_livesplit(quiet=True)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._tick()

    @staticmethod
    def _box(parent, title, row, col, colspan=1):
        f = ttk.LabelFrame(parent, text=title, padding=6)
        f.grid(row=row, column=col, columnspan=colspan, sticky="nsew", padx=3, pady=3)
        return f

    # --- statut + LiveSplit + options ---------------------------------------------

    def _build_status(self, page):
        top = ttk.Frame(page)
        top.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.status = tk.StringVar()
        ttk.Label(top, textvariable=self.status, font=("Segoe UI", 10)).pack(side="left")

        bottom = ttk.Frame(page)
        bottom.grid(row=3, column=0, columnspan=3, sticky="ew")
        self.host = tk.StringVar(value=self.cfg["host"])
        self.port = tk.StringVar(value=str(self.cfg["port"]))
        ttk.Button(bottom, text=_("Tester split"), command=lambda: self._ls_cmd("split")).pack(side="right")
        ttk.Button(bottom, text=_("Connecter LiveSplit"), command=self._connect_livesplit).pack(side="right", padx=4)
        ttk.Entry(bottom, textvariable=self.port, width=6).pack(side="right")
        ttk.Entry(bottom, textvariable=self.host, width=10).pack(side="right", padx=2)
        ttk.Label(bottom, text="TCP (Control > Start TCP Server) :").pack(side="right", padx=4)
        # Mode de liaison avec LiveSplit : script .asl (recommande) ou serveur TCP.
        self.ls_mode = tk.StringVar(value=self.cfg["livesplit_mode"])
        self.ls_mode.trace_add("write", lambda *_a: self._set_ls_mode())
        ttk.Radiobutton(bottom, text="TCP", value="tcp", variable=self.ls_mode).pack(side="right", padx=(2, 12))
        ttk.Radiobutton(bottom, text="Script FMSpeedTool.asl", value="script",
                        variable=self.ls_mode).pack(side="right")
        ttk.Label(bottom, text=_("LiveSplit :")).pack(side="right", padx=4)

        opts = ttk.Frame(page)
        opts.grid(row=4, column=0, columnspan=3, sticky="w")
        self.opt_vars = {}
        for key, text in (("auto_reset", _("Reset auto (NEW GAME)")),
                          ("auto_start", _("Demarrer le timer (NEW GAME)")),
                          ("split_first_loss", _("Split 1re defaite (Heishin 1)")),
                          ("split_farm_v2", _("Split fin de farm (desactive : pas de farm)"))):
            v = tk.BooleanVar(value=self.tracker.options[key])
            v.trace_add("write", lambda *_a, k=key, var=v: self._set_option(k, var.get()))
            ttk.Checkbutton(opts, text=text, variable=v).pack(side="left", padx=4)
            self.opt_vars[key] = v
        # Langue : fichiers lang/<code>.json (voir i18n.py) ; change au redemarrage.
        self.langs = i18n.available()
        names = sorted(self.langs.values())
        self.lang_var = tk.StringVar(value=self.langs.get(i18n.current, i18n.current))
        lang_box = ttk.Combobox(opts, textvariable=self.lang_var, values=names, state="readonly", width=12)
        lang_box.pack(side="left", padx=4)
        lang_box.bind("<<ComboboxSelected>>", lambda e: self._set_language())
        ttk.Label(opts, text="Langue / Language :").pack(side="left", padx=(24, 0), before=lang_box)

    def _set_language(self):
        code = next((c for c, n in self.langs.items() if n == self.lang_var.get()), None)
        if not code or code == i18n.current:
            return
        self.cfg["language"] = code
        self._save_config()
        if messagebox.askyesno("FM Speed Tool", _("Redemarrer maintenant pour changer de langue ?")):
            self.restart()

    def restart(self):
        import subprocess
        args = [sys.executable] + ([] if getattr(sys, "frozen", False) else [os.path.abspath(sys.argv[0])])
        self.close()
        subprocess.Popen(args, close_fds=True)

    def _set_ls_mode(self):
        self.cfg["livesplit_mode"] = self.ls_mode.get()
        self._save_config()
        if self.cfg["livesplit_mode"] == "tcp":
            self._connect_livesplit(quiet=True)
        self._log(_("LiveSplit : script FMSpeedTool.asl") if self.ls_mode.get() == "script"
                  else _("LiveSplit : serveur TCP"))

    def _set_option(self, key, value):
        self.tracker.options[key] = value
        self.cfg["options"][key] = value
        self._save_config()

    def _connect_livesplit(self, quiet=False):
        self.livesplit.close()
        self.livesplit.host = self.host.get().strip() or "localhost"
        try:
            self.livesplit.port = int(self.port.get())
        except ValueError:
            self.livesplit.port = 16834
        self.cfg["host"], self.cfg["port"] = self.livesplit.host, self.livesplit.port
        self._save_config()
        try:
            self.livesplit.connect()
            self._log(_("LiveSplit connecte"))
        except OSError:
            if not quiet:
                messagebox.showwarning("LiveSplit", _("Connexion impossible. Dans LiveSplit : "
                                                     "clic droit > Control > Start TCP Server."))

    def _ls_cmd(self, cmd):
        try:
            getattr(self.livesplit, cmd)()
            self._log(f"LiveSplit : {cmd}")
        except OSError:
            self._log(_("LiveSplit injoignable"))

    # --- journal ---------------------------------------------------------------------

    def _build_log(self, box):
        ttk.Label(box, text=_("Rang de chaque duel de la run")).pack(anchor="w")
        cols = ("n", "adv", "mode", "res", "rang")
        self.hist = ttk.Treeview(box, columns=cols, show="headings", height=8)
        for c, title, w in zip(cols, ("#", _("Adversaire"), _("Mode"), _("Resultat"), _("Rang")), (28, 95, 70, 62, 80)):
            self.hist.heading(c, text=title)
            self.hist.column(c, width=w, anchor="w")
        self.hist.pack(fill="both", expand=True)
        self._hist_shown = 0
        ttk.Label(box, text=_("Journal")).pack(anchor="w", pady=(4, 0))
        self.log = tk.Listbox(box, height=6)
        self.log.pack(fill="both", expand=True)

    def _refresh_history(self):
        h = self.tracker.history
        if len(h) < self._hist_shown:   # nouvelle run
            self.hist.delete(*self.hist.get_children())
            self._hist_shown = 0
        campaign = sum(1 for d in h[:self._hist_shown] if not d["free"])
        for i, d in enumerate(h[self._hist_shown:], start=self._hist_shown + 1):
            if not d["free"]:
                campaign += 1
            opp = d["opponent"] if d["opponent"] != "?" else _("Campagne {n}", n=campaign)
            self.hist.insert("", 0, values=(i, opp, "Free Duel" if d["free"] else _("Campagne"),
                                            _(d["result"]), f"{d['rank']} ({d['score']})"))
        self._hist_shown = len(h)

    def _log(self, msg):
        self.log.insert(0, time.strftime("%H:%M:%S ") + msg)
        self.log.delete(300, "end")

    # --- rang ------------------------------------------------------------------------

    def _build_rank(self, box):
        top = ttk.Frame(box)
        top.pack(fill="x")
        self.rank_big = tk.StringVar()
        ttk.Label(top, textvariable=self.rank_big, font=("Segoe UI", 18, "bold")).pack(side="left")
        self.target = tk.StringVar(value="A-TEC")
        ttk.Combobox(top, textvariable=self.target, width=7, state="readonly",
                     values=[b[2] for b in fmlogic.BANDS]).pack(side="right")
        ttk.Label(top, text=_("Objectif")).pack(side="right", padx=4)
        self.duel_info = tk.StringVar()
        ttk.Label(box, textvariable=self.duel_info, foreground="#555").pack(anchor="w")

        grid = ttk.Frame(box)
        grid.pack(fill="x", pady=4)
        self.rank_rows = {}
        step = {"lp": 100}
        for r, stat in enumerate(fmlogic.RANK_TABLE):
            ttk.Label(grid, text=_(fmlogic.STAT_LABELS[stat])).grid(row=r, column=0, sticky="w")
            val, pts, nxt = tk.StringVar(), tk.StringVar(), tk.StringVar()
            ttk.Label(grid, textvariable=val, width=7, anchor="e").grid(row=r, column=1)
            d = step.get(stat, 1)
            ttk.Button(grid, text="-", width=2, command=lambda s=stat, d=d: self._adjust(s, -d)).grid(row=r, column=2)
            ttk.Button(grid, text="+", width=2, command=lambda s=stat, d=d: self._adjust(s, d)).grid(row=r, column=3)
            ttk.Label(grid, textvariable=pts, width=5, anchor="e").grid(row=r, column=4)
            ttk.Label(grid, textvariable=nxt, foreground="#777").grid(row=r, column=5, sticky="w", padx=6)
            self.rank_rows[stat] = (val, pts, nxt)
        self.advice = tk.StringVar()
        ttk.Label(box, textvariable=self.advice, justify="left", font=("Consolas", 9)).pack(anchor="w")

    def _adjust(self, stat, d):
        with self.worker.lock:
            self.tracker.manual[stat] += d

    def _refresh_rank(self):
        tr = self.tracker
        s = tr.rank_stats()
        for stat, (val, pts, nxt) in self.rank_rows.items():
            m = tr.manual[stat]
            val.set(f"{s[stat]}" + ("*" if m else ""))
            pts.set(f"{fmlogic.stat_points(stat, s[stat]):+d}")
            n = fmlogic.next_threshold(stat, s[stat])
            nxt.set(_("a {value} : {points}", value=n[0], points=f"{n[1]:+d}") if n else "")
        total = fmlogic.score(s)
        duel_key = (tr.in_duel, tr.opponent)
        if duel_key != getattr(self, "_last_duel_key", None):
            self._last_duel_key = duel_key
            if tr.in_duel and tr.target:
                self.target.set(tr.target)   # Pegasus : objectif A-TEC automatique
        target = self.target.get()
        lo, hi = fmlogic.band_range(target)
        shown = max(0, min(99, total))  # le jeu borne le score a 0..99
        self.rank_big.set(f"{fmlogic.band(total)}  {shown}" + ("  OK" if lo <= total <= hi else ""))
        mode = "Free Duel" if tr.free_duel else _("Campagne")
        opp = _(" contre {name}", name=tr.opponent) if tr.opponent else ""
        self.duel_info.set((_("Duel en cours") if tr.in_duel else _("Hors duel")) + f"{opp} - {mode}"
                           + "   " + _("(* = corrige a la main)"))
        self.advice.set(fmlogic.advice(s, target))

    # --- Final 6 -----------------------------------------------------------------------

    def _build_f6(self, box):
        self.deck_auto = tk.BooleanVar(value=self.cfg.get("deck_auto", True))
        self.deck_auto.trace_add("write", lambda *_a: self._set_deck_auto())
        ttk.Checkbutton(box, text=_("Deck lu automatiquement (ecrans DECK / CHEST)"),
                        variable=self.deck_auto).pack(anchor="w")
        self.deck_info = tk.StringVar(value=_("Deck : pas encore vu"))
        ttk.Label(box, textvariable=self.deck_info, foreground="#555", wraplength=460,
                  justify="left").pack(anchor="w")
        grid = ttk.Frame(box)
        grid.pack(anchor="w")
        self.f6_vars = {}
        for i, field in enumerate(fmlogic.F6_FIELDS):
            v = tk.IntVar(value=int(self.cfg["f6"].get(field, 0)))
            label = fmlogic.F6_LABELS[field].split(" (")[0]
            col = (i // 9) * 2
            ttk.Label(grid, text=label).grid(row=i % 9, column=col, sticky="w")
            ttk.Spinbox(grid, from_=0, to=40, width=3, textvariable=v).grid(row=i % 9, column=col + 1, padx=(2, 8))
            self.f6_vars[field] = v
        self.dark_hole = tk.BooleanVar(value=self.cfg["dark_hole"])
        ttk.Checkbutton(box, text=_("Dark Hole (au lieu de Raigeki)"), variable=self.dark_hole).pack(anchor="w")
        eq = ttk.Frame(box)
        eq.pack(anchor="w")
        self.equip_vars = []
        for i in range(6):
            v = tk.StringVar(value=self.cfg["equips"][i] if i < len(self.cfg["equips"]) else "N/A")
            ttk.Combobox(eq, textvariable=v, values=fmlogic.F6_EQUIPS, state="readonly",
                         width=13).grid(row=i // 2, column=i % 2, padx=1, pady=1)
            self.equip_vars.append(v)

        res = ttk.Frame(box)
        res.pack(fill="x", pady=(2, 4), before=grid)   # resultat en haut du panneau
        self.f6_total = tk.StringVar(value=_("Chargement du tableur d'Exarion..."))
        ttk.Label(res, textvariable=self.f6_total, font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, columnspan=6, sticky="w")
        self.f6_each = {}
        for i, name in enumerate(f6calc.DUELISTS):
            ttk.Label(res, text=name).grid(row=1 + i // 3, column=(i % 3) * 2, sticky="w")
            v = tk.StringVar(value="-")
            ttk.Label(res, textvariable=v, width=7).grid(row=1 + i // 3, column=(i % 3) * 2 + 1, sticky="w")
            self.f6_each[name] = v
        ttk.Button(box, text=_("Ouvrir aussi sur fusion.lukadevv.com"), command=self._open_f6).pack(fill="x", pady=4)

        for v in list(self.f6_vars.values()) + self.equip_vars + [self.dark_hole]:
            v.trace_add("write", lambda *_a: self._schedule_f6())
        self.f6 = f6calc.F6Calculator(os.path.join(BASE_DIR, "assets", "f6_model.xlsx"))
        threading.Thread(target=self._load_f6, daemon=True).start()
        self._f6_job = None

    def _set_deck_auto(self):
        self.cfg["deck_auto"] = self.deck_auto.get()
        self._save_config()
        self._deck_version = -1

    def _refresh_deck(self):
        """Recopie le deck lu a l'ecran dans les compteurs du Final 6."""
        w = self.deck.watcher
        n, complete = w.summary()
        state = _("complet") if complete else _("fais defiler tout le deck une fois")
        self.deck_info.set(_("Deck : {n}/40 ({state})   Ajouts : {added}   Retraits : {removed}",
                             n=n, state=state, added=len(w.added), removed=len(w.removed)))
        if not self.deck_auto.get() or self.deck.version == self._deck_version or n == 0:
            return
        self._deck_version = self.deck.version
        counts, dark_hole, equips = self.deck.f6()
        for k, v in self.f6_vars.items():
            v.set(counts.get(k, 0))
        self.dark_hole.set(dark_hole)
        for i, v in enumerate(self.equip_vars):
            v.set(equips[i] if i < len(equips) else "N/A")

    def _load_f6(self):
        self.f6.load()
        self.root.after(0, self._update_f6)

    def _schedule_f6(self):
        if self._f6_job:
            self.root.after_cancel(self._f6_job)
        self._f6_job = self.root.after(250, self._update_f6)

    def _f6_inputs(self):
        counts = {}
        for k, v in self.f6_vars.items():
            try:
                counts[k] = max(0, int(v.get()))
            except (tk.TclError, ValueError):
                counts[k] = 0
        equips = [v.get() for v in self.equip_vars if v.get() != "N/A"]
        return counts, self.dark_hole.get(), equips

    def _update_f6(self):
        """Recalcule le % de victoire avec les formules du tableur d'Exarion."""
        self._f6_job = None
        counts, dark_hole, equips = self._f6_inputs()
        self.cfg["f6"], self.cfg["dark_hole"] = counts, dark_hole
        self.cfg["equips"] = [v.get() for v in self.equip_vars]
        self._save_config()
        if self.f6.error:
            self.f6_total.set(_("Tableur indisponible : utilise le site"))
            if not getattr(self, "_f6_error_logged", False):
                self._f6_error_logged = True
                self._log(_("Tableur Final 6 : {error}", error=self.f6.error))
                try:
                    with open(os.path.join(APP_DIR, "f6_error.txt"), "w", encoding="utf-8") as f:
                        f.write(getattr(self.f6, "traceback", self.f6.error))
                except OSError:
                    pass
            return
        if not self.f6.ready:
            return
        try:
            r = self.f6.compute(counts, dark_hole, equips)
        except Exception as e:
            self.f6_total.set(_("Calcul impossible ({error})", error=e))
            return
        self.f6_total.set(f"Final 6 : {r['Final 6'] * 100:.1f} %")
        for name, v in self.f6_each.items():
            v.set(f"{r[name] * 100:.1f} %")

    def _open_f6(self):
        counts, dark_hole, equips = self._f6_inputs()
        url = fmlogic.f6_url(counts, dark_hole, equips)
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        webbrowser.open("https://fusion.lukadevv.com/win-rate")
        self._log(_("Lien Final 6 copie : clique IMPORT sur la page et colle (Ctrl+V)"))

    # --- vue du jeu + apprentissage -------------------------------------------------

    def _build_learn(self, box):
        """Sur la page : un simple bouton. L'apercu du jeu (qui prenait de la
        place) n'apparait que dans la fenetre d'apprentissage."""
        self.learn_win = None
        self.frozen = None
        self.sel = None
        ttk.Button(box, text=_("Apprendre un ecran..."), command=self._open_learn).pack(side="left")
        self.learn_count = tk.StringVar()
        ttk.Label(box, textvariable=self.learn_count, foreground="#777").pack(side="left", padx=8)
        ttk.Button(box, text=_("Mots de passe utiles"),
                   command=lambda: self._set_pw_manual(True)).pack(side="left", padx=12)

    # --- mots de passe (ecran PASSWORD du jeu) ----------------------------------------

    def _build_passwords(self):
        """Vue des codes des cartes utiles achetables. Elle remplace la page normale
        tant que l'ecran PASSWORD du jeu est affiche (ou a la demande)."""
        view = self.pw_view = ttk.Frame(self.root, padding=6)
        top = ttk.Frame(view)
        top.pack(fill="x")
        ttk.Label(top, text=_("Ecran PASSWORD : codes des cartes utiles"),
                  font=("Segoe UI", 16, "bold")).pack(side="left")
        self.pw_back = ttk.Button(top, text=_("Retour"), command=lambda: self._set_pw_manual(False))
        cols = ("carte", "code", "prix", "info")
        ttk.Style(self.root).configure("PW.Treeview", font=("Consolas", 12), rowheight=24)
        tree = ttk.Treeview(view, columns=cols, show="tree headings", style="PW.Treeview")
        tree.column("#0", width=230)
        tree.heading("#0", text=_("Categorie"))
        for c, title, w in zip(cols, (_("Carte"), _("Mot de passe"), _("Etoiles"), _("Info")), (380, 180, 100, 180)):
            tree.heading(c, text=title)
            tree.column(c, width=w, anchor="w")
        sections = {}
        for section, name, pw, cost, info in passwords.useful_passwords(self.deck.db):
            if section not in sections:
                sections[section] = tree.insert("", "end", text=_(section), open=True)
            tree.insert(sections[section], "end", values=(name, passwords.format_password(pw), cost, info))
        tree.pack(fill="both", expand=True, pady=6)
        ttk.Label(view, foreground="#777", text=_("Cette liste remplace la page tant que l'ecran "
                         "PASSWORD du jeu est affiche ; la page normale revient quand tu le quittes.")).pack(anchor="w")
        self._pw_manual = False
        self._pw_seen = -1e9
        self._pw_shown = False

    def _set_pw_manual(self, on):
        self._pw_manual = on

    def _refresh_passwords(self):
        now = time.monotonic()
        if self.tracker.on_password_screen:
            self._pw_seen = now
        show = self._pw_manual or now - self._pw_seen < 1.0
        if show == self._pw_shown:
            return
        self._pw_shown = show
        if show:
            self.page.pack_forget()
            self.pw_view.pack(fill="both", expand=True)
            if self._pw_manual:
                self.pw_back.pack(side="right")
        else:
            self.pw_back.pack_forget()
            self.pw_view.pack_forget()
            self.page.pack(fill="both", expand=True)

    def _open_learn(self):
        if self.learn_win is not None:
            self.learn_win.lift()
            return
        win = self.learn_win = tk.Toplevel(self.root)
        win.title(_("Apprendre un ecran"))
        win.protocol("WM_DELETE_WINDOW", self._close_learn)
        self.canvas = tk.Canvas(win, width=PREVIEW[0], height=PREVIEW[1], bg="black", cursor="cross")
        self.canvas.pack(side="left", padx=6, pady=6)
        self.canvas.bind("<ButtonPress-1>", self._sel_start)
        self.canvas.bind("<B1-Motion>", self._sel_move)

        right = ttk.Frame(win, padding=(8, 6))
        right.pack(side="left", fill="both", expand=True)
        row = ttk.Frame(right)
        row.pack(fill="x")
        self.freeze_btn = ttk.Button(row, text=_("Figer l'image"), command=self._toggle_freeze)
        self.freeze_btn.pack(side="left")
        self.learn_name = tk.StringVar()
        ttk.Entry(row, textvariable=self.learn_name, width=16).pack(side="left", padx=4)
        self.learn_action = tk.StringVar(value=_(tracker.LEARN_ACTIONS["fusion"]))
        ttk.Combobox(row, textvariable=self.learn_action, state="readonly", width=34,
                     values=[_(v) for v in tracker.LEARN_ACTIONS.values()]).pack(side="left")
        ttk.Button(row, text=_("Apprendre"), command=self._learn).pack(side="left", padx=4)
        ttk.Label(right, foreground="#777", text=_("Fige l'ecran voulu, trace un rectangle sur une zone "
                         "qui le caracterise, choisis l'action. Score en direct (1,00 = identique) :")).pack(anchor="w")
        self.learn_list = tk.Listbox(right, height=12, width=60)
        self.learn_list.pack(fill="both", expand=True)
        ttk.Button(right, text=_("Supprimer l'ecran selectionne"), command=self._unlearn).pack(anchor="w")

    def _close_learn(self):
        self.learn_win.destroy()
        self.learn_win = None
        self.frozen = None
        self.sel = None

    def _toggle_freeze(self):
        if self.frozen is None and self.tracker.last_frame is not None:
            self.frozen = self.tracker.last_frame.copy()
            self.freeze_btn.config(text=_("Reprendre"))
        else:
            self.frozen = None
            self.sel = None
            self.freeze_btn.config(text=_("Figer l'image"))

    def _sel_start(self, e):
        self.sel = [e.x, e.y, e.x, e.y]

    def _sel_move(self, e):
        if self.sel:
            self.sel[2], self.sel[3] = e.x, e.y

    def _learn(self):
        if self.frozen is None or not self.sel:
            messagebox.showinfo(_("Apprentissage"), _("Fige d'abord l'image puis trace un rectangle."))
            return
        sx, sy = vision.W / PREVIEW[0], vision.H / PREVIEW[1]
        x0, x1 = sorted((self.sel[0], self.sel[2]))
        y0, y1 = sorted((self.sel[1], self.sel[3]))
        rect = (int(x0 * sx), int(y0 * sy), int((x1 - x0) * sx), int((y1 - y0) * sy))
        if rect[2] < 8 or rect[3] < 8:
            messagebox.showinfo(_("Apprentissage"), _("Rectangle trop petit."))
            return
        action = next(k for k, v in tracker.LEARN_ACTIONS.items() if _(v) == self.learn_action.get())
        name = self.learn_name.get().strip() or _(tracker.LEARN_ACTIONS[action])
        with self.worker.lock:
            self.learned.add(name, action, rect, self.frozen)
        self._log(_("Ecran appris : {name}", name=name))
        self._toggle_freeze()

    def _unlearn(self):
        sel = self.learn_list.curselection()
        if sel:
            with self.worker.lock:
                self.learned.remove(sel[0])

    def _refresh_learn(self):
        n = len(self.learned.items)
        self.learn_count.set(_("{n} ecran(s) appris", n=n) if n else "")
        if self.learn_win is None:
            return
        img = self.frozen if self.frozen is not None else self.tracker.last_frame
        if img is not None:
            small = cv2.cvtColor(cv2.resize(img, PREVIEW, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
            self._photo = ImageTk.PhotoImage(Image.fromarray(small))
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
            if self.sel:
                self.canvas.create_rectangle(*self.sel, outline="red", width=2)
        live = self.tracker.last_frame
        items = [f"{t.name}  [{_(tracker.LEARN_ACTIONS.get(t.action, t.action))}]  "
                 f"{(t.score(live) if live is not None else 0):.2f}"
                 for t in self.learned.items]
        if list(self.learn_list.get(0, "end")) != items:
            cur = self.learn_list.curselection()
            self.learn_list.delete(0, "end")
            for it in items:
                self.learn_list.insert("end", it)
            for i in cur:
                if i < len(items):
                    self.learn_list.selection_set(i)

    # --- chiffres ----------------------------------------------------------------------

    def _build_digits(self, box):
        self.digits_info = tk.StringVar()
        ttk.Label(box, textvariable=self.digits_info, wraplength=380, justify="left").pack(anchor="w")
        self.unknown_frame = ttk.Frame(box)
        self.unknown_frame.pack(fill="both", expand=True)
        ttk.Button(box, text=_("Oublier les chiffres appris"), command=self._forget_digits).pack(anchor="w")
        self._unknown_shown = -1

    def _forget_digits(self):
        with self.worker.lock:
            if os.path.exists(self.digits.path):
                os.remove(self.digits.path)
            self.digits.templates = {}
            self.digits.unknown = []
            self.digits.load()  # repart des chiffres integres
        self._unknown_shown = -1

    def _refresh_digits(self):
        n = len(self.digits.unknown)
        self.digits_info.set(_("Aucun chiffre inconnu.") if not n else
                             _("{n} chiffre(s) inconnu(s) : tape la valeur puis OK.", n=n))
        if n == self._unknown_shown:
            return
        self._unknown_shown = n
        for w in self.unknown_frame.winfo_children():
            w.destroy()
        self._glyph_photos = []
        for i, (vec, preview) in enumerate(list(self.digits.unknown)[:10]):
            cell = ttk.Frame(self.unknown_frame, padding=2)
            cell.grid(row=i // 5, column=i % 5)
            ph = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)))
            self._glyph_photos.append(ph)
            ttk.Label(cell, image=ph).pack()
            var = tk.StringVar()
            ttk.Entry(cell, textvariable=var, width=3).pack()
            ttk.Button(cell, text="OK", width=3,
                       command=lambda v=vec, var=var: self._label_digit(v, var)).pack()

    def _label_digit(self, vec, var):
        d = var.get().strip()
        if len(d) != 1 or not d.isdigit():
            return
        with self.worker.lock:
            self.digits.add(d, vec)
            self.digits.save()
            self.digits.unknown = [(v, p) for v, p in self.digits.unknown if v is not vec]
        self._unknown_shown = -1

    # --- boucle UI --------------------------------------------------------------------

    def _tick(self):
        while not self.worker.events.empty():
            kind, msg = self.worker.events.get()
            self._log(msg)
        tr = self.tracker
        hud = tr.hud
        if self.worker.cap.covered:
            win = _("RECOUVERTE par une autre fenetre (rien n'est lu)")
        else:
            win = "OK" if self.worker.window_ok else _("introuvable")
        if self.cfg["livesplit_mode"] == "script":
            ls = _("script .asl") if self.bridge is not None else _("script indisponible (utilise TCP)")
        else:
            ls = _("TCP connecte") if self.livesplit.connected else _("TCP deconnecte")
        def val(x):
            return "-" if x is None else x
        self.status.set(_("ePSXe : {win} ({fps} img/s)     LiveSplit : {ls}", win=win,
                          fps=f"{self.worker.fps:.0f}", ls=ls) + "\n"
                        + _("Tour : {turn}     LP  COM {com_lp} / YOU {you_lp}     Cartes  COM {com_deck} / YOU {you_deck}",
                            turn=tr.active or "-", com_lp=val(hud["com_lp"]), you_lp=val(hud["you_lp"]),
                            com_deck=val(hud["com_deck"]), you_deck=val(hud["you_deck"])))
        self._refresh_rank()
        self._refresh_history()
        self._refresh_deck()
        self._refresh_passwords()
        self._refresh_learn()
        self._refresh_digits()
        self.root.after(200, self._tick)

    def _save_config(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, indent=1)
        except OSError:
            pass

    def close(self):
        self.worker.running = False
        self.livesplit.close()
        self.root.destroy()


def main():
    # .exe sans console : stdout/stderr valent None, ce qui casse la barre de
    # progression (tqdm) de la bibliotheque de formules.
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
    # Minuteur Windows a 1 ms : sans lui, time.sleep arrondit a ~15 ms et la
    # boucle ne tient pas 60 img/s.
    try:
        import ctypes
        ctypes.windll.winmm.timeBeginPeriod(1)
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
