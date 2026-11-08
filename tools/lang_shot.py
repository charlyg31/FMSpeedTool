"""Ouvre l'interface dans une langue donnee (sans changer la config) et
enregistre une capture de la page normale et de la page mots de passe.

python tools/lang_shot.py en
"""

import os
import sys
import tkinter as tk

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
import cv2  # noqa: E402

import app  # noqa: E402
import capture  # noqa: E402

lang = sys.argv[1] if len(sys.argv) > 1 else "en"
orig = app.load_config


def load_config():
    cfg = orig()
    cfg["language"] = lang
    if os.environ.get("FM_SOURCE"):
        cfg["source"] = os.environ["FM_SOURCE"]
    return cfg


app.load_config = load_config
app.App._save_config = lambda self: None      # ne touche pas a la vraie config

root = tk.Tk()
a = app.App(root)


def shot(name):
    root.update()
    img = capture._grab(root.winfo_id() and int(root.wm_frame(), 16), False)
    cv2.imwrite(os.path.join(ROOT, "captures", f"lang_{lang}_{name}.png"), img)


def step1():
    shot("main")
    a._set_pw_manual(True)
    root.after(800, step2)


def step2():
    shot("passwords")
    a.close()


root.after(3000, step1)
root.mainloop()
