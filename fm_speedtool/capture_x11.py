"""Capture de la fenetre du jeu sous Linux (X11, ou XWayland pour une session Wayland).

Meme principe que sous Windows : l'emulateur est reconnu a son programme (/proc/<pid>/exe),
la fenetre doit etre visible et non recouverte, et on copie sa zone de l'ecran (mss).
Une fenetre Wayland native n'est pas visible d'X11 : lancer l'emulateur en X11
(DuckStation : QT_QPA_PLATFORM=xcb).

Les fenetres sont designees par leur identifiant X11 (entier), comme les hwnd sous Windows.
"""

import os
import time

import numpy as np

try:
    from Xlib import X, display as xdisplay, error as xerror
except ImportError:                       # python-xlib absent : aucune capture possible
    X = xdisplay = xerror = None

try:
    import mss
except ImportError:
    mss = None

EMULATORS = {"epsxe": "epsxe", "duckstation": "duckstation"}   # source -> debut du nom du programme
_disp = None


def _display():
    global _disp
    if _disp is None and xdisplay is not None and os.environ.get("DISPLAY"):
        try:
            _disp = xdisplay.Display()
        except Exception:
            _disp = None
    return _disp


def _atom(name):
    return _display().intern_atom(name)


def _prop(win, name):
    try:
        p = win.get_full_property(_atom(name), X.AnyPropertyType)
    except xerror.XError:
        return None
    return p.value if p is not None else None


def _client_list():
    """Fenetres des applications, de la plus basse a la plus haute (ordre d'empilement)."""
    d = _display()
    if d is None:
        return []
    root = d.screen().root
    ids = _prop(root, "_NET_CLIENT_LIST_STACKING")
    if ids is None:
        ids = _prop(root, "_NET_CLIENT_LIST")
    if ids is None:                        # pas de gestionnaire de fenetres : enfants de la racine
        try:
            return [w.id for w in root.query_tree().children]
        except xerror.XError:
            return []
    return list(ids)


def _win(wid):
    return _display().create_resource_object("window", wid)


def window_title(wid):
    try:
        w = _win(wid)
        t = _prop(w, "_NET_WM_NAME")
        if t is None:
            t = w.get_wm_name()
        if isinstance(t, bytes):
            t = t.decode("utf-8", "replace")
        return t or ""
    except Exception:
        return ""


def _pid(wid):
    v = _prop(_win(wid), "_NET_WM_PID")
    return int(v[0]) if v is not None and len(v) else None


def _wm_class(wid):
    try:
        c = _win(wid).get_wm_class()
    except xerror.XError:
        return ""
    return " ".join(c).lower() if c else ""


def process_exe(wid):
    """Nom du programme (en minuscules) qui possede la fenetre, ex. 'duckstation-qt'.
    Sans _NET_WM_PID (ou programme illisible) : la classe X11 de la fenetre (WM_CLASS)."""
    pid = _pid(wid)
    if pid:
        for path in (f"/proc/{pid}/exe", f"/proc/{pid}/comm"):
            try:
                name = os.readlink(path) if path.endswith("exe") else open(path).read().strip()
                return os.path.basename(name).lower()
            except OSError:
                continue
    return _wm_class(wid)


def _viewable(wid):
    try:
        return _win(wid).get_attributes().map_state == X.IsViewable
    except xerror.XError:
        return False


def client_rect_on_screen(wid):
    """(x, y, largeur, hauteur) de la fenetre a l'ecran."""
    w = _win(wid)
    g = w.get_geometry()
    pos = w.translate_coords(_display().screen().root, 0, 0)
    return -pos.x, -pos.y, g.width, g.height


def _area(wid):
    try:
        g = _win(wid).get_geometry()
        return g.width * g.height
    except xerror.XError:
        return 0


def _render_child(top):
    """DuckStation (Qt) : l'image est dans une sous-fenetre ; la plus grande visible."""
    best, best_a = top, 0
    try:
        stack = list(_win(top).query_tree().children)
        depth = 0
        while stack and depth < 3:
            nxt = []
            for c in stack:
                if _viewable(c.id):
                    a = _area(c.id)
                    if a > best_a:
                        best, best_a = c.id, a
                    nxt.extend(c.query_tree().children)
            stack, depth = nxt, depth + 1
    except xerror.XError:
        pass
    return best if best_a >= 0.3 * _area(top) else top


def find_emulator_windows(source):
    prefix = EMULATORS[source]
    found = []
    for wid in _client_list():
        if _viewable(wid) and process_exe(wid).startswith(prefix):
            a = _area(wid)
            if a >= 160 * 120:
                target = _render_child(wid) if source == "duckstation" else wid
                found.append((a, target, wid))
    found.sort(key=lambda f: -f[0])
    return [(t, h) for _a, t, h in found]


def list_windows():
    """Titres des fenetres visibles (source PS2), les plus grandes d'abord."""
    out = []
    for wid in sorted(_client_list(), key=lambda w: -_area(w)):
        if _viewable(wid) and _area(wid) >= 160 * 120:
            t = window_title(wid)
            if t and t not in out:
                out.append(t)
    return out


def find_window_titled(title):
    exact, partial = [], []
    for wid in _client_list():
        if _viewable(wid):
            t = window_title(wid)
            if t == title:
                exact.append(wid)
            elif title and title.lower() in t.lower():
                partial.append(wid)
    return (exact or partial or [None])[0]


def _top_of(wid):
    """Fenetre d'application qui contient wid (wid lui-meme si c'en est une)."""
    clients = set(_client_list())
    w = wid
    for _ in range(10):
        if w in clients:
            return w
        try:
            parent = _win(w).query_tree().parent
        except xerror.XError:
            return wid
        if parent is None or parent.id == _display().screen().root.id:
            return wid
        w = parent.id
    return wid


def is_covered(wid):
    """Une autre fenetre d'application, plus haut dans l'empilement, recouvre-t-elle la zone ?"""
    x, y, w, h = client_rect_on_screen(wid)
    stack = _client_list()
    top = _top_of(wid)
    above = stack[stack.index(top) + 1:] if top in stack else []
    rects = []
    for o in above:
        if _viewable(o):
            try:
                rects.append(client_rect_on_screen(o))
            except xerror.XError:
                pass
    for fx, fy in ((0.5, 0.5), (0.1, 0.1), (0.9, 0.1), (0.1, 0.9), (0.9, 0.9)):
        px, py = x + w * fx, y + h * fy
        if any(rx <= px < rx + rw and ry <= py < ry + rh for rx, ry, rw, rh in rects):
            return True
    return False


class WindowCapture:
    """Meme interface que la version Windows. Copie d'ecran par mss (XShm si possible)."""

    RESEARCH = 1.0

    def __init__(self):
        self.hwnd = None
        self.title = None
        self.emulator = "epsxe"
        self.next_search = 0.0
        self.method = "x11"
        self.covered = False
        self.sct = mss.mss() if mss is not None and _display() is not None else None

    def _search(self):
        if _display() is None:
            return None
        if self.title is not None:
            return find_window_titled(self.title)
        wins = find_emulator_windows(self.emulator)
        for target, _top in wins:
            if not is_covered(target):
                return target
        return wins[0][0] if wins else None

    def ensure_window(self):
        if self.hwnd and _viewable(self.hwnd):
            return True
        self.hwnd = self._search()
        self.next_search = time.monotonic() + self.RESEARCH
        return self.hwnd is not None

    def reset(self):
        self.hwnd = None
        self.next_search = 0.0

    def set_source(self, title, emulator="epsxe"):
        if title != self.title or emulator != self.emulator:
            self.title = title
            self.emulator = emulator
            self.hwnd = None

    def grab(self):
        if self.sct is None:
            return None
        try:
            if not self.ensure_window():
                return None
            self.covered = is_covered(self.hwnd)
            if self.covered and time.monotonic() >= self.next_search:
                self.next_search = time.monotonic() + self.RESEARCH
                other = self._search()
                if other and other != self.hwnd:
                    self.hwnd = other
                    self.covered = is_covered(other)
            if self.covered:
                return None
            x, y, w, h = client_rect_on_screen(self.hwnd)
        except xerror.XError:
            self.hwnd = None                  # fenetre fermee entre-temps
            return None
        if w <= 0 or h <= 0:
            return None
        shot = self.sct.grab({"left": x, "top": y, "width": w, "height": h})
        return np.asarray(shot)[:, :, :3].copy()      # BGRA -> BGR
