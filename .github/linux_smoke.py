"""Test Linux sans emulateur : sur un ecran X virtuel (Xvfb + gestionnaire de fenetres),
un faux emulateur dont le programme s'appelle "duckstation-fake" affiche l'ecran titre ;
l'outil doit le trouver par son programme, le capturer et reconnaitre l'ecran titre.
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
img = Image.open(sys.argv[1]).convert("RGB").resize((640, 480))
root = tk.Tk()
root.title("Yu-Gi-Oh! Forbidden Memories")
root.geometry("640x480+40+40")
photo = ImageTk.PhotoImage(img)
tk.Label(root, image=photo, bd=0).pack()
root.update()
# Tk ne pose pas toujours _NET_WM_PID : on le pose (DuckStation, en Qt, le fait).
import os
d = display.Display()
w = d.create_resource_object("window", int(root.wm_frame(), 16))
w.change_property(d.intern_atom("_NET_WM_PID"), d.intern_atom("CARDINAL"), 32, [os.getpid()])
d.flush()
root.mainloop()
'''


def title_image():
    """Ecran titre du jeu : celui des tests s'il existe, sinon un ecran de synthese."""
    import cv2
    import numpy as np
    path = os.path.join(tempfile.gettempdir(), "fm_title.png")
    img = np.zeros((480, 640, 3), np.uint8)
    img[:, :] = (30, 60, 200)
    cv2.putText(img, "FM SPEED TOOL TEST", (60, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
    cv2.imwrite(path, img)
    return path, img


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
    proc = subprocess.Popen([fake, script, path])
    try:
        cap = capture.WindowCapture()
        cap.set_source(None, "duckstation")
        img = None
        for _ in range(40):
            time.sleep(0.25)
            img = cap.grab()
            if img is not None:
                break
        assert img is not None, f"fenetre non capturee (fenetre={cap.hwnd}, recouverte={cap.covered})"
        print("capture", img.shape, "fenetre", cap.hwnd)
        import cv2
        got = cv2.resize(img, (640, 480))
        diff = float(np.abs(got.astype(int) - ref.astype(int)).mean())
        print("ecart moyen avec l'image affichee :", round(diff, 2))
        assert diff < 12, "l'image capturee ne correspond pas"
        assert capture.list_windows(), "list_windows vide"
    finally:
        proc.terminate()

    # Logiciel complet : 40 s sans plantage (tableur charge dans son processus).
    env = dict(os.environ, XDG_CONFIG_HOME=tempfile.mkdtemp())
    app = subprocess.Popen([sys.executable, os.path.join(SRC, "app.py")], env=env,
                           stderr=subprocess.PIPE, text=True)
    time.sleep(40)
    alive = app.poll() is None
    app.terminate()
    try:
        err = app.communicate(timeout=15)[1]
    except subprocess.TimeoutExpired:
        app.kill()
        err = app.communicate()[1]
    print(err[-3000:])
    assert alive, "le logiciel s'est arrete"
    assert "Traceback" not in err, "erreur Python pendant le lancement"
    f6 = os.path.join(env["XDG_CONFIG_HOME"], "FMSpeedTool", "f6_error.txt")
    assert not os.path.exists(f6), open(f6).read()
    print("OK")


if __name__ == "__main__":
    main()
