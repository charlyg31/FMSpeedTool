"""Machine d'etat : transforme les images successives en evenements de run.

Tout vient de l'image : HUD du duel (LP, cartes restantes, joueur actif),
gabarits integres (titre, Free Duel, YOU WIN / YOU LOSE, adversaires, pose
face cachee, SAVE / LOAD COMPLETE...).
"""

import time

import fmlogic
import vision
from i18n import N_, _

STAT_ACTIONS = ("fusion", "equip", "magic", "trap", "eff_atk", "def_win", "facedown")

HUD_ON_FRAMES = 3        # images consecutives pour valider l'apparition du HUD
DUEL_GONE_SECONDS = 8.0  # HUD absent aussi longtemps, resultat connu : fin du duel
RESULT_WAIT = 30.0       # resultat inconnu : attente de RESULTS OF DUEL (WINNER) avant d'abandonner
EDGE_COOLDOWN = 1.5      # anti-rebond des gabarits
FADE_WINDOW = 0.8        # NEW GAME valide : l'ecran titre s'assombrit dans ce delai
NAME_ENTRY_GRACE = 30.0  # l'ecran du nom ne relance pas une run deja demarree
POST_DUEL_IGNORE = 20.0  # portrait du vaincu dans le dialogue d'apres-duel
FLASH_GAP = 0.3          # images blanches plus espacees : nouveau flash (video a 4 img/s : 0,25 s)
GLOW_WITH_FLASH = 0.12   # halo d'equipement : commence avec son propre flash blanc
REVEAL_WATCH = 0.6       # duree d'observation de la grande carte (ATK qui defile = equipement)
ORIENT_END_WINDOW = 0.2  # pose face cachee : dos de carte vu juste avant de valider
PLACE_CONFIRM = 1.2      # la camera zoome sur le terrain dans ce delai si la pose est validee
PLACE_CANCEL = 1.0       # choix de la case annule : l'ecran d'orientation revient dans ce delai (~0,3 s)
# Types de split (transmis au script LiveSplit, qui filtre selon ses reglages)
SPLIT_WIN, SPLIT_FIRST_LOSS, SPLIT_FARM, SPLIT_OTHER = 1, 2, 3, 4


class Tracker:
    def __init__(self, digits, builtin, learned, on_event, deck=None):
        self.digits = digits
        self.builtin = builtin
        self.learned = learned            # gabarits en plus (tests) ou None
        self.deck = deck                  # deckscreen.DeckReader (lecture du deck) ou None
        self.on_event = on_event          # callback(type, message)
        self.options = {"split_first_loss": True, "auto_reset": True, "auto_start": True,
                        "split_farm_v2": False,
                        # Chargement d'une sauvegarde : "undo" annule dans LiveSplit les splits
                        # faits depuis cette sauvegarde ; "skip" ignore les N prochains.
                        "load_mode": "undo"}
        self.edges = {}
        self.last_split = (SPLIT_OTHER, "")
        self.area = vision.GameArea()     # zone de jeu dans la fenetre (bandes noires)
        self.on_password_screen = False   # ecran PASSWORD du jeu affiche
        self.last_frame = None
        self.framing = None               # vision.Framing pour une source console (PS2)
        self.framing_next = 0.0
        self.audio = None                 # source du son du jeu (audio.LiveSource / FileSource) ou None
        self.audio_clf = None             # audio.Classifier : fusion ou equipement au son
        self.sound_pending = []           # [(instant, choix de l'image)] en attente du son
        self.last_now = 0.0
        self.last_new_run = -1e9
        self.duel_ended_at = -1e9
        self.title_armed = None           # luminosite du titre quand NEW GAME etait surligne
        self.title_left_at = None
        self.reset_run()

    # --- etat ----------------------------------------------------------------

    def reset_run(self):
        self.losses = 0
        self.wins = 0
        self.free_wins = 0
        self.history = []                 # un element par duel termine de la run
        self.split_counts = {}            # splits envoyes a LiveSplit pendant la run, par type
        self.skip_splits = {}             # par type : prochains splits a ignorer (duels rejoues)
        self.save_point = None            # ({type: splits atteints}, victoires, defaites) a la sauvegarde
        self.pending_split = None         # (message, echeance) : split au RESULTS OF DUEL
        self.in_duel = False
        self.free_duel = False            # mode du duel en cours / a venir
        self.free_pending = False         # ecran Free Duel vu depuis le dernier duel
        self.opponent = ""
        self.next_opponent = ""
        self.reset_duel()

    def reset_duel(self):
        self.stats = {k: 0 for k in fmlogic.RANK_TABLE}
        self.stats["lp"] = 8000
        self.hud = {"com_lp": None, "you_lp": None, "com_deck": None, "you_deck": None}
        self.prev_values = dict(self.hud)
        self.active = None
        self.hud_frames = 0
        self.hud_last_seen = 0.0
        self.decided = None               # 'win' / 'loss'
        self.orient_seen = False
        self.orient_back_at = None    # dernier dos de carte vu sur l'ecran d'orientation
        self.orient_last_at = 0.0
        self.facedown_until = 0.0         # pose face cachee a confirmer (zoom sur le terrain)
        self.facedown_zoom = False        # vue rapprochee (choix de la case) en cours
        self.facedown_confirm_at = None   # fin de la vue rapprochee : compte si pas d'annulation
        self.reveal_until = 0.0           # flash vu : on attend la grande carte
        self.equip_until = 0.0
        self.last_flash = -1e9
        self.flash_start = -1e9
        self.reveal_watch = None          # (debut, carte) : fusion ou equipement a confirmer
        self.battle = None
        self.manual = {k: 0 for k in fmlogic.RANK_TABLE}

    def rank_stats(self):
        s = dict(self.stats)
        for k, v in self.manual.items():
            s[k] = max(0, s[k] + v)
        # Paquet du COM vide : il perdra a sa pioche = victoire par epuisement (-40).
        s["victory"] = "attrition" if self.hud["com_deck"] == 0 else "annihilation"
        return s

    @property
    def target(self):
        return "A-TEC" if "pegasus" in self.opponent.lower() else None

    # --- boucle ----------------------------------------------------------------

    def process(self, frame, now=None, normalized=False):
        now = time.monotonic() if now is None else now
        self.last_now = now
        if self.sound_pending:
            self._resolve_sounds(now)
        # Fenetre ePSXe de n'importe quelle taille : bandes noires retirees, puis 640x512.
        img = frame if normalized else vision.normalize(self.area.crop(frame))
        if img is None:
            return
        if self.framing is not None:
            # Console : cale le cadrage vertical sur le menu titre ou le panneau LP/COM/YOU (4 fois/s
            # tant qu'il n'est pas trouve), puis l'applique a chaque image.
            if not self.framing.locked and now >= self.framing_next:
                self.framing_next = now + 0.25
                if self.framing.calibrate(img):
                    self.on_event("framing", _("Cadrage PS2 trouve (decalage {dy:+.0f}, echelle {sy:.2f})",
                                               dy=self.framing.dy, sy=self.framing.sy))
            img = self.framing.apply(img)
        self.last_frame = img
        prep = vision.prepare(img)
        matches = {t.action: t for t in self.builtin.matching(img, prep)}
        if self.learned is not None:
            for t in self.learned.matching(img, prep):
                matches.setdefault(t.action, t)
                if t.action == "opponent":
                    matches["opponent"] = t
        hud_now = vision.hud_present(img)
        self._title(img, matches, now)
        if self._edge("name_entry", "new_run" in matches, now) and now - self.last_new_run > NAME_ENTRY_GRACE:
            self._new_run(now, _("ecran du nom"))
        if self._edge("free_duel", "free_duel" in matches, now):
            if not self.free_pending:
                self.on_event("info", _("Ecran Free Duel : prochain duel en Free Duel"))
            self.free_pending = True
        # Apres un duel, le portrait du vaincu revient dans le dialogue : on
        # l'ignore 20 s (sauf sur l'ecran Free Duel, ou le nom choisi compte).
        after_duel = now - self.duel_ended_at < POST_DUEL_IGNORE
        if "opponent" in matches and not self.in_duel and (self.free_pending or not after_duel):
            name = matches["opponent"].name
            if name != self.next_opponent:
                self.next_opponent = name
                self.on_event("info", _("Adversaire choisi : {name}", name=name))
        for a in STAT_ACTIONS:
            if self._edge(f"stat_{a}", a in matches, now) and self.in_duel:
                self.stats[a] += 1
                self.on_event("stat", _(fmlogic.STAT_LABELS[a]) + " +1")
        if self._edge("split", "split" in matches, now):
            self._split(SPLIT_OTHER, _("Split ({name})", name=matches["split"].name))
        if self._edge("save_done", "save_done" in matches, now):
            self._save()
        if self._edge("load_done", "load_done" in matches, now):
            if self.in_duel and not hud_now:
                self._end_duel(self.decided, now)   # duel quitte sans attendre RESULTS
            self._load()

        self.on_password_screen = "password_screen" in matches
        if self.deck is not None:
            screen = ("deck" if "deck_screen" in matches else
                      "chest" if "chest_screen" in matches else None)
            for kind, name in self.deck.frame(screen, img):
                self.on_event("deck", (_("Deck : ajout de {name}", name=name) if kind == "+"
                                        else _("Deck : retrait de {name}", name=name)))

        hud = hud_now
        if hud:
            self._hud_frame(img, now)
        if self.in_duel:
            self._orientation(img, matches, now)
            self._fusion_equip(img, hud, now)
            self._battle(img, hud)
            if "you_win" in matches or "winner_you" in matches:
                self._end_duel("win", now)
            elif "you_lose" in matches or "winner_com" in matches:
                self._end_duel("loss", now)
            elif "results" in matches:
                self._end_duel(self.decided, now)
            elif now - self.hud_last_seen > (DUEL_GONE_SECONDS if self.decided else RESULT_WAIT):
                # Coup fatal : le panneau des LP quitte l'ecran pendant que le compteur
                # descend, le 0 n'est jamais affiche. Le resultat vient alors de
                # RESULTS OF DUEL (WINNER YOU/COM), ~12 s apres.
                self._end_duel(self.decided, now)
        # Le split part a l'apparition de l'ecran RESULTS OF DUEL (comme a la main).
        if self.pending_split and ("results" in matches or now > self.pending_split[1]):
            msg, _t, kind, opponent = self.pending_split
            self._split(kind, msg, opponent)
            self.pending_split = None
        # Fin de farm : retour au menu du jeu apres au moins une victoire en Free Duel.
        if self._edge("game_menu", "game_menu" in matches, now):
            self.free_pending = False     # on a quitte l'ecran Free Duel
            self.next_opponent = ""
            if self.free_wins:
                self.free_wins = 0
                if self.options["split_farm_v2"]:
                    self._split(SPLIT_FARM, _("Fin du farm (retour au menu)"))

    def _split(self, kind, msg, opponent=""):
        """Signale un split ; last_split dit lequel (le script LiveSplit filtre dessus)."""
        if self.skip_splits.get(kind):
            # Duel rejoue apres un chargement : ce split a deja ete fait.
            self.skip_splits[kind] -= 1
            self.on_event("info", _("{msg} : ignore (deja fait avant le chargement, encore {n})",
                                    msg=msg, n=sum(self.skip_splits.values())))
            return
        self.split_counts[kind] = self.split_counts.get(kind, 0) + 1
        self.last_split = (kind, opponent)
        self.on_event("split", msg)

    def _reached(self):
        """Splits par type deja faits dans le jeu (ceux encore a ignorer seront refaits)."""
        return {k: n - self.skip_splits.get(k, 0) for k, n in self.split_counts.items()}

    def _save(self):
        """SAVE COMPLETE! : retient ou en est la run (splits deja faits dans le jeu)."""
        reached = self._reached()
        self.save_point = (reached, self.wins, self.losses)
        self.on_event("save", _("Sauvegarde : {n} split(s) faits a ce point", n=sum(reached.values())))

    def _load(self):
        """LOAD COMPLETE! : la run revient a la derniere sauvegarde vue. Les splits faits
        depuis sont annules (undo) ou les prochains sont ignores (skip). Le skip compte par
        type : une defaite qui splittait et n'est pas rejouee ne mange pas une victoire."""
        if self.save_point is None:
            self.on_event("info", _("Chargement : aucune sauvegarde vue pendant cette run, rien a corriger"))
            return
        reached, self.wins, self.losses = self.save_point
        self.pending_split = None
        extra = {k: n - reached.get(k, 0) for k, n in self.split_counts.items()
                 if n - reached.get(k, 0) > 0}
        total = sum(extra.values())
        if not total:
            self.skip_splits = {}
            self.on_event("info", _("Chargement : aucun split depuis la sauvegarde"))
            return
        if self.options.get("load_mode", "undo") == "skip":
            self.skip_splits = extra
            self.on_event("info", _("Chargement : les {n} prochain(s) split(s) seront ignores", n=total))
        else:
            self.split_counts = dict(reached)
            self.skip_splits = {}
            self.on_event("undo", _("Chargement : {n} split(s) annule(s) dans LiveSplit", n=total))

    def _edge(self, key, active, now):
        """Front montant avec anti-rebond."""
        was, last = self.edges.get(key, (False, -1e9))
        fire = active and not was and now - last > EDGE_COOLDOWN
        self.edges[key] = (active, now if fire else last)
        return fire

    def _title(self, img, matches, now):
        """Depart a l'appui sur NEW GAME : NEW GAME est surligne, puis des l'image
        suivante les boutons du menu (LOAD, 2P DUEL, TRADE, OPTION) quittent leur place
        en glissant. Deplacer le curseur sur LOAD laisse les boutons en place (et
        valider LOAD ne part pas de NEW GAME) : aucun reset. Secours : le fondu au noir
        qui suit."""
        bright = float(img.mean())
        if "title_newgame" in matches:
            self.title_armed = bright
            self.title_left_at = None
            return
        if self.title_armed is None:
            return
        if self.title_left_at is None:
            self.title_left_at = now
        # Boutons du menu partis (score ~0,2 contre 0,63 a 0,85 menu en place).
        menu_gone = vision.title_menu_score(img) < 0.4
        pressed = now - self.title_left_at <= 0.15 and menu_gone
        # Fondu au noir : le menu doit aussi etre parti. A l'arrivee du menu, la 1re image
        # avec NEW GAME surligne garde un reste du flash blanc du titre (~40 % plus
        # claire) : curseur descendu sur LOAD juste apres = faux fondu sinon (video du 20/10).
        if pressed or (bright < self.title_armed * 0.7 and menu_gone):
            self.title_armed = None
            self._new_run(now, "NEW GAME")
        elif now - self.title_left_at > FADE_WINDOW:
            self.title_armed = None

    def _new_run(self, now, why):
        self.last_new_run = now
        self.reset_run()
        if self.deck is not None:
            self.deck.reset()             # nouveau deck de depart
        self.on_event("new_run", _("Nouvelle partie ({why})", why=why))

    def _hud_frame(self, img, now):
        if self.in_duel and now - self.hud_last_seen > DUEL_GONE_SECONDS:
            # Duel en attente de son resultat, mais un nouveau duel commence (sauvegarde
            # rechargee, reset) : on ferme l'ancien.
            self._end_duel(self.decided, now)
            self.hud_frames = 0
        self.hud_last_seen = now
        self.hud_frames += 1
        if not self.in_duel:
            if self.hud_frames < HUD_ON_FRAMES:
                return
            self._start_duel(img, now)
        active = vision.active_player(img)
        values = {k: self.digits.read(img, k) for k in vision.HUD_CELLS}
        if active and self.active and active != self.active:
            # Au changement de joueur, les LP et le paquet de celui qui finit son
            # tour ne bougent pas (le nouveau joueur, lui, pioche) : on apprend
            # leur nouvelle apparence (panneau allume/eteint) a partir des
            # valeurs lues sur l'image precedente.
            drawing = f"{active}_deck"
            known = {k: v for k, v in self.prev_values.items()
                     if v is not None and values[k] is None and k != drawing}
            if known and self.digits.bootstrap(img, known):
                values = {k: self.digits.read(img, k) for k in vision.HUD_CELLS}
            # Le jeu compte les tours termines : verifie sur la video (3 tours
            # affiches pour un duel gagne pendant ton 4e tour).
            if active == "com":
                self.stats["turns"] += 1
        if active:
            self.active = active
        self.prev_values = values
        for k, v in values.items():
            if v is None:
                continue
            old = self.hud[k]
            # Un paquet ne fait que diminuer, de 5 cartes au plus a la fois :
            # sinon c'est un chiffre des dizaines manque ("2" au lieu de "28").
            if k.endswith("deck") and old is not None and not (old - 5 <= v <= old):
                continue
            self.hud[k] = v
        if self.hud["you_deck"] is not None:
            self.stats["cards"] = 40 - self.hud["you_deck"]
        if self.hud["you_lp"] is not None:
            self.stats["lp"] = self.hud["you_lp"]
        if not self.decided:
            if values["com_lp"] == 0:
                self.decided = "win"
            elif values["you_lp"] == 0:
                self.decided = "loss"

    def _start_duel(self, img, now):
        self.reset_duel()
        self.in_duel = True
        self.hud_frames = HUD_ON_FRAMES
        self.hud_last_seen = now
        self.free_duel = self.free_pending
        self.free_pending = False
        self.opponent = self.next_opponent
        self.next_opponent = ""
        self.active = vision.active_player(img)
        mode = "Free Duel" if self.free_duel else _("Campagne")
        who = _(" contre {name}", name=self.opponent) if self.opponent else ""
        goal = _(" - objectif A-TEC") if self.target else ""
        self.on_event("duel_start", _("Debut de duel ({mode}){who}{goal}", mode=mode, who=who, goal=goal))

    def _end_duel(self, result, now):
        if not self.in_duel:
            return
        if result is None and self.hud["com_deck"] == 0:
            result = "win"
        if result is None and self.hud["you_deck"] == 0:
            result = "loss"
        if self.battle:
            self._resolve_battle()
        if self.reveal_watch:
            self._count_reveal("fusion")
        self._resolve_sounds(now, flush=True)
        s = self.rank_stats()
        total = fmlogic.score(s)
        summary = _("rang estime {band} ({score})", band=fmlogic.band(total), score=total)
        free = self.free_duel
        self.in_duel = False
        self.hud_frames = 0
        self.duel_ended_at = now
        who = _(" contre {name}", name=self.opponent) if self.opponent else ""
        self.history.append({"opponent": self.opponent or "?", "free": free,
                             "result": {"win": N_("Victoire"), "loss": N_("Defaite")}.get(result, "?"),
                             "rank": fmlogic.band(total), "score": max(0, min(99, total)),
                             "stats": s})
        if result == "win":
            self.wins += 1
            if free:
                self.free_wins += 1
                self.on_event("info", _("Victoire en Free Duel{who} - {summary}", who=who, summary=summary))
            else:
                self.on_event("info", _("Victoire{who} - {summary}", who=who, summary=summary))
                self.pending_split = (_("Split : victoire{who}", who=who), now + 10, SPLIT_WIN, self.opponent)
        elif result == "loss":
            # Seule la 1re defaite de campagne (Heishin 1) compte : une defaite en Free
            # Duel ne la decale pas, et les suivantes (mort puis rechargement) ne
            # splittent pas.
            if not free:
                self.losses += 1
            self.on_event("info", _("Defaite{who}", who=who))
            if self.options["split_first_loss"] and self.losses == 1 and not free:
                self.pending_split = (_("Split : premiere defaite (Heishin 1)"), now + 10,
                                      SPLIT_FIRST_LOSS, self.opponent)
        else:
            self.on_event("info", _("Duel interrompu (resultat illisible)"))

    def _fusion_equip(self, img, hud, now):
        """Fusion : flash blanc puis grande carte revelee. Equipement : halo
        violet-magenta, ou flash dore puis grande carte du monstre equipe dont
        l'ATK/DFD defile (verifie sur la video de run)."""
        if self.reveal_watch:
            t0, ref = self.reveal_watch
            verdict = vision.card_compare(ref, vision.reveal_card(img))
            if verdict == "counting":
                self._count_reveal("equip")
            elif verdict == "other" or now - t0 > REVEAL_WATCH:
                self._count_reveal("fusion")
        # Le flash d'une fusion/d'un equipement peut blanchir l'encadre FIELD (HUD
        # juge absent) : les panneaux COM/YOU suffisent alors, s'ils sont visibles.
        if not (hud or vision.hud_panels(img)) or self.active != "you":
            return
        if self._edge("magic_card", hud and vision.magic_card_shown(img), now):
            self.stats["magic"] += 1
            self.on_event("stat", _("Magie pure +1"))
        flash = vision.white_flash(img) > 3000
        if flash:
            if now - self.last_flash > FLASH_GAP:
                self.flash_start = now          # debut de ce flash
            self.last_flash = now
        # Halo violet = equipement. Apres le flash blanc d'une fusion, du violet est
        # l'illustration de la carte revelee (Curse of Dragon..., 0,5 s apres le debut du
        # flash) : ignore. L'explosion magenta d'un equipement fait elle-meme son flash
        # blanc : halo et flash commencent ensemble.
        glow = (vision.equip_glow(img) > 4000 and not self.reveal_watch
                and (now - self.last_flash > 1.2 or now - self.flash_start <= GLOW_WITH_FLASH))
        if self._edge("equip_glow", glow, now):
            # Un equipement se termine par la grande carte du monstre equipe.
            self.reveal_until = 0.0
            self.equip_until = now + 2.5
        if self._edge("flash", flash, now) and now > self.equip_until:
            self.reveal_until = now + 2.5
        pending_equip = now <= self.equip_until
        if not pending_equip and now > self.reveal_until:
            return
        if vision.reveal_card(img) is None:   # grande carte a la hauteur d une revelation (pas un combat)
            return
        self.equip_until = self.reveal_until = 0.0
        if pending_equip:
            self._count_reveal("equip", source="glow")
        else:
            # Flash blanc : fusion, sauf si l'ATK de la carte se met a defiler.
            self.reveal_watch = (now, vision.reveal_card(img))

    def _count_reveal(self, kind, source="flash"):
        self.reveal_watch = None
        # Le son tranche apres un flash (fusion ou equipement dore). Un equipement reconnu a
        # son halo violet est sur : le son ne le contredit pas.
        if source == "flash" and self.audio is not None and self.audio_clf is not None:
            # Le son tranche entre fusion et equipement : on attend d'avoir tout le bruitage.
            self.sound_pending.append((self.last_now, kind))
            return
        self._add_stat(kind)

    def _add_stat(self, kind, note=""):
        self.stats[kind] += 1
        self.on_event("stat", _(fmlogic.STAT_LABELS[kind]) + " +1" + note)

    def _resolve_sounds(self, now, flush=False):
        """Decide chaque fusion/equipement en attente des que le son autour est disponible
        (AFTER s apres la revelation). Son absent ou pas net : le choix de l'image reste."""
        import audio as au
        keep = []
        for t, kind in self.sound_pending:
            if not flush and now < t + au.AFTER + 0.05 and not now > t + 3.0:
                keep.append((t, kind))
                continue
            heard = None
            if self.audio.ready(t + au.AFTER):
                heard = self.audio_clf.decide(self.audio.window(t - au.BEFORE, t + au.AFTER))
            if heard and heard != kind:
                self._add_stat(heard, " " + _("(au son ; l'image disait {kind})",
                                              kind=_(fmlogic.STAT_LABELS[kind]).lower()))
            else:
                self._add_stat(kind)
        self.sound_pending = keep

    def _battle(self, img, hud):
        """Combat : deux grandes cartes (attaquant a gauche). La carte detruite
        brule et disparait ; on regarde qui reste a la fin."""
        if hud:
            if self.battle:
                self._resolve_battle()
            return
        sides = vision.battle_cards(img)
        if self.battle is None:
            if len(sides) == 2:
                self.battle = {"turn": self.active, "hist": [], "trap": False,
                               "right_def": vision.card_in_defense(img, "right")}
            return
        if not self.battle["trap"] and self.battle["turn"] == "com" and vision.trap_card_right(img):
            # Le COM attaque et c'est notre piege qui repond.
            self.battle["trap"] = True
            self.stats["trap"] += 1
            self.on_event("stat", _("Piege declenche +1"))
        if sides:
            self.battle["hist"].append(tuple(sorted(sides)))

    def _resolve_battle(self):
        b, self.battle = self.battle, None
        tail = b["hist"][-3:]
        if not tail or b["trap"]:
            return
        final = max(set(tail), key=tail.count)
        right_destroyed = final == ("left",)
        if b["turn"] == "you" and right_destroyed and not b["right_def"]:
            self.stats["eff_atk"] += 1
            self.on_event("stat", _("Attaque efficace +1"))
        elif b["turn"] == "com" and b["right_def"] and not right_destroyed:
            self.stats["def_win"] += 1
            self.on_event("stat", _("Victoire en defense +1"))

    def _orientation(self, img, matches, now):
        """Pose d'une carte : ecran avec les fleches jaunes. Le dos de carte
        apparait aussi au debut de l'animation d'une pose face visible (et
        d'un piege pose) : seule compte la position de la carte a la sortie
        de l'ecran (dos vu dans les ORIENT_END_WINDOW dernieres secondes ;
        il clignote, d'ou une fenetre plutot que la derniere image). Une pose
        annulee (carte remise en main) ne zoome pas sur le terrain."""
        arrows = vision.orient_arrows(img) >= 0.65
        if arrows:
            if not self.orient_seen:
                self.orient_back_at = None
            self.orient_seen = True
            self.orient_last_at = now
            if vision.card_back(img) >= 0.75:
                self.orient_back_at = now
        elif self.orient_seen:
            self.orient_seen = False
            if self.orient_back_at is not None and self.orient_last_at - self.orient_back_at <= ORIENT_END_WINDOW:
                self.facedown_until = now + PLACE_CONFIRM
        # Orientation validee : la camera zoome sur le terrain pour choisir la case
        # (des l'image de sortie, a 4 img/s).
        if self.facedown_until:
            if now > self.facedown_until or arrows:
                self.facedown_until = 0.0
            elif vision.board_zoom(img):
                self.facedown_until = 0.0
                self.facedown_zoom = True
        # Case choisie : la vue rapprochee se termine sur le terrain. Annulee (rond) :
        # l'ecran d'orientation revient juste apres, la carte n'est pas posee.
        if self.facedown_zoom:
            if arrows:
                self.facedown_zoom = False
                self.facedown_confirm_at = None
            elif vision.board_zoom(img):
                self.facedown_confirm_at = None
            elif self.facedown_confirm_at is None:
                self.facedown_confirm_at = now + PLACE_CANCEL
            elif now >= self.facedown_confirm_at:
                self.facedown_zoom = False
                self.facedown_confirm_at = None
                self.stats["facedown"] += 1
                self.on_event("stat", _("Pose face cachee +1"))
