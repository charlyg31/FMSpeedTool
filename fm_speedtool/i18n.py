"""Traductions de l'interface.

Le texte source (francais) sert de cle : _("Tours") donne "Turns" en anglais.
Chaque langue est un fichier JSON `lang/<code>.json` :

    {"language": "English", "author": "...",
     "strings": {"Tours": "Turns", "Victoire{who} - {summary}": "Win{who} - {summary}"}}

Les {noms} entre accolades sont remplaces par le logiciel : il faut les garder
tels quels dans la traduction. Une chaine absente ou vide reste en francais.

Fichiers lus (le dernier gagne) : ceux livres avec le logiciel, puis le dossier
`lang` a cote de FMSpeedTool.exe, puis %APPDATA%\\FMSpeedTool\\lang.
"""

import ctypes
import glob
import json
import os
import sys

SOURCE = "fr"
SOURCE_NAME = "Français"

BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
EXE_DIR = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
           else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "FMSpeedTool")
LANG_DIRS = [os.path.join(BASE_DIR, "lang"), os.path.join(EXE_DIR, "lang"),
             os.path.join(APP_DIR, "lang")]

_strings = {}
current = SOURCE


def N_(text):
    """Marque un texte a traduire plus tard (dictionnaires de module)."""
    return text


def _(text, **kw):
    out = _strings.get(text) or text
    if kw:
        try:
            return out.format(**kw)
        except (KeyError, IndexError, ValueError):
            return text.format(**kw)   # traduction mal formee : on garde la source
    return out


def _files():
    found = {}
    for d in LANG_DIRS:
        for path in glob.glob(os.path.join(d, "*.json")):
            code = os.path.splitext(os.path.basename(path))[0]
            if code.startswith("_") or code == "template":
                continue
            found.setdefault(code, []).append(path)
    return found


def _read(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def available():
    """{code: nom affiche} de toutes les langues trouvees."""
    langs = {SOURCE: SOURCE_NAME}
    for code, paths in _files().items():
        name = code
        for p in paths:
            name = _read(p).get("language") or name
        langs[code] = name
    return langs


def system_language():
    """'fr' si Windows est en francais, sinon 'en'."""
    try:
        lid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        if lid & 0x3FF == 0x0C:            # LANG_FRENCH
            return "fr"
    except (AttributeError, OSError):
        pass
    return "en"


def set_language(code):
    global current
    _strings.clear()
    current = code if code in available() else ("en" if "en" in available() else SOURCE)
    if current == SOURCE:
        return current
    for path in _files().get(current, []):
        strings = _read(path).get("strings", {})
        _strings.update({k: v for k, v in strings.items() if isinstance(v, str) and v})
    return current
