"""Test Linux sans emulateur : sur un ecran X virtuel (Xvfb + gestionnaire de fenetres),
un faux emulateur dont le programme s'appelle "duckstation-fake" affiche l'ecran titre du jeu
(image reelle prise dans DuckStation sous Windows, 1397x963) ; l'outil doit le trouver par son
programme, le capturer a l'identique, se caler dessus et reconnaitre l'ecran titre (NEW GAME).
Puis le logiciel complet est lance 40 s : il ne doit pas planter.

python .github/linux_smoke.py      (dans xvfb-run, avec un gestionnaire de fenetres lance)
"""

import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "fm_speedtool")
sys.path.insert(0, SRC)

FAKE = r'''
import sys, tkinter as tk
from PIL import Image, ImageTk
from Xlib import display
img = Image.open(sys.argv[1]).convert("RGB")
root = tk.Tk()
root.title("Yu-Gi-Oh! Forbidden Memories")
root.geometry(f"{img.width}x{img.height}+20+20")
photo = ImageTk.PhotoImage(img)
tk.Label(root, image=photo, bd=0).pack()
root.update()
# Tk ne pose pas toujours _NET_WM_PID : on le pose sur la fenetre de l'application (celle de
# _NET_CLIENT_LIST, pas le cadre du gestionnaire de fenetres), comme DuckStation (Qt) le fait.
import os
d = display.Display()
w = d.create_resource_object("window", root.winfo_id()).query_tree().parent
w.change_property(d.intern_atom("_NET_WM_PID"), d.intern_atom("CARDINAL"), 32, [os.getpid()])
d.flush()
root.mainloop()
'''


def title_image():
    """Ecran titre du jeu tel que DuckStation l'affiche (capture reelle)."""
    import cv2
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "duckstation_title.png")
    return path, cv2.imread(path)


def read_title(img):
    """Meme chaine que le logiciel : bandes noires retirees, 640x512, cadrage, puis ecran titre
    reconnu (gabarit NEW GAME surligne). Rend le meilleur score du gabarit."""
    import vision
    assets = os.path.join(SRC, "assets")
    area = vision.GameArea()
    norm = None
    for _ in range(3):
        norm = vision.normalize(area.crop(img))
    fr = vision.Framing(os.path.join(assets, "hud_ref.png"), vertical=True)
    for _ in range(6):
        fr.calibrate(norm)
    print("cadrage", [round(float(v), 3) for v in fr.values()[:4]], "complet", fr.full)
    framed = fr.apply(norm)
    lib = vision.TemplateLibrary(os.path.join(assets, "builtin"))
    scores = [t.score(framed) for t in lib.items if t.action == "title_newgame"]
    return max(scores)


def main():
    import numpy as np
    import capture
    assert capture.WindowCapture.__module__ == "capture_x11", capture.WindowCapture.__module__

    # Faux emulateur : lien dur vers python nomme "duckstation-fake" (meme dossier, meme
    # bibliotheques), /proc/<pid>/exe donne alors ce nom.
    real = os.path.realpath(sys.executable)
    fake = os.path.join(os.path.dirname(real), "duckstation-fake")
    if not os.path.exists(fake):
        os.link(real, fake)
    script = os.path.join(tempfile.gettempdir(), "fake_emu.py")
    open(script, "w").write(FAKE)
    path, ref = title_image()
    # Le lien dur est hors du venv eventuel : on lui donne les bibliotheques de ce Python.
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in sys.path if p and os.path.isdir(p)))
    proc = subprocess.Popen([fake, script, path], env=env)
    try:
        cap = capture.WindowCapture()
        cap.set_source(None, "duckstation")
        img = None
        for _ in range(40):
            time.sleep(0.25)
            img = cap.grab()
            if img is not None:
                break
        if img is None:
            import capture_x11 as cx
            for wid in cx._client_list():
                print("fenetre", hex(wid), repr(cx.window_title(wid)), "pid", cx._pid(wid),
                      "programme", cx.process_exe(wid), "visible", cx._viewable(wid))
        assert img is not None, f"fenetre non capturee (fenetre={cap.hwnd}, recouverte={cap.covered})"
        print("capture", img.shape, "fenetre", cap.hwnd)
        import cv2  # noqa: F401
        assert img.shape == ref.shape, f"taille capturee {img.shape} au lieu de {ref.shape}"
        diff = float(np.abs(img.astype(int) - ref.astype(int)).mean())
        print("ecart moyen avec l'image affichee :", round(diff, 2))
        assert diff < 3, "l'image capturee ne correspond pas"
        score = read_title(img)
        print("ecran titre reconnu : score", round(score, 3), "(seuil 0,85)")
        assert score >= 0.85, "ecran titre non reconnu"
        assert capture.list_windows(), "list_windows vide"
    finally:
        proc.terminate()

    # Logiciel complet : 40 s sans plantage (tableur charge dans son processus).
    # Sortie d'erreurs dans un fichier (pas un tube : le processus du tableur, lance par le
    # logiciel, le garderait ouvert et l'attente ne finirait jamais) ; tout le groupe de
    # processus est arrete a la fin.
    import signal
    env = dict(os.environ, XDG_CONFIG_HOME=tempfile.mkdtemp())
    log = os.path.join(env["XDG_CONFIG_HOME"], "stderr.txt")
    with open(log, "w") as errf:
        app = subprocess.Popen([sys.executable, os.path.join(SRC, "app.py")], env=env,
                               stdout=subprocess.DEVNULL, stderr=errf, start_new_session=True)
        time.sleep(40)
        alive = app.poll() is None
        # SIGTERM au logiciel seul : il doit se fermer proprement, tableur compris.
        app.send_signal(signal.SIGTERM)
        try:
            app.wait(timeout=15)
        except subprocess.TimeoutExpired:
            pass
        time.sleep(2)
        orphans = subprocess.run(["pgrep", "-g", str(app.pid)], capture_output=True, text=True).stdout.split()
        try:
            os.killpg(app.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    err = open(log).read()
    print(err[-3000:])
    assert alive, "le logiciel s'est arrete"
    assert not orphans, f"processus restes apres SIGTERM : {orphans}"
    assert "Traceback" not in err, "erreur Python pendant le lancement"
    f6 = os.path.join(env["XDG_CONFIG_HOME"], "FMSpeedTool", "f6_error.txt")
    assert not os.path.exists(f6), open(f6).read()
    print("OK")


if __name__ == "__main__":
    main()
