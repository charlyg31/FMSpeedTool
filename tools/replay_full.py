"""Rejoue une video de run image par image, a sa cadence reelle (30 ou 60 img/s), avec
la meme chaine que le logiciel en direct : cadrage, Tracker, lecture du deck (DECK/CHEST).
Ecrit chaque evenement, et au debut de chaque duel les comptes du Final 6 et le deck lu.

python tools/replay_full.py VIDEO X Y W H [DEBUT_S FIN_S] > journal
X Y W H : zone du jeu dans la video (pixels de la video).
"""

import os
import subprocess
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
import cv2  # noqa: E402
import imageio_ffmpeg  # noqa: E402
import numpy as np  # noqa: E402

import deckscreen  # noqa: E402
import tracker  # noqa: E402
import vision  # noqa: E402

A = os.path.join(ROOT, "fm_speedtool", "assets")


def main(video, x, y, w, h, t0=0.0, t1=None):
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    vw, vh = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    deck = deckscreen.DeckReader(A)
    state = {"t": t0}

    def ev(kind, msg):
        print(f"{state['t']:8.2f}s ({state['t'] * 4:6.0f})  {kind:10s} {msg}", flush=True)
        if kind == "duel_start":
            counts, dark_hole, equips = deck.f6()
            n, comp = deck.watcher.summary()
            print(f"          deck {n}/40 complet={comp} F6={ {k: v for k, v in counts.items() if v} } "
                  f"equips={equips} dark_hole={dark_hole}", flush=True)
            print("          cartes", sorted(deck.watcher.cards()), flush=True)

    tr = tracker.Tracker(vision.DigitReader(os.path.join(tempfile.mkdtemp(), "d.json"),
                                            os.path.join(A, "digits_default.json")),
                         vision.TemplateLibrary(os.path.join(A, "builtin")),
                         vision.TemplateLibrary(os.path.join(tempfile.mkdtemp(), "l")), ev, deck=deck)
    tr.framing = vision.Framing(os.path.join(A, "hud_ref.png"), vertical=True)
    # Zone du jeu (peut deborder de la video : complete en noir), puis 640x512.
    x0, y0, x1, y1 = max(0, x), max(0, y), min(vw, x + w), min(vh, y + h)
    vf = f"crop={x1 - x0}:{y1 - y0}:{x0}:{y0}"
    if (x1 - x0, y1 - y0) != (w, h):
        vf += f",pad={w}:{h}:{x0 - x}:{y0 - y}"
    vf += ",scale=640:512:flags=area"
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-ss", str(t0)]
    if t1:
        cmd += ["-t", str(t1 - t0)]
    cmd += ["-i", video, "-vf", vf, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=640 * 512 * 3 * 8)
    n = 0
    while True:
        buf = p.stdout.read(640 * 512 * 3)
        if len(buf) < 640 * 512 * 3:
            break
        state["t"] = t0 + n / fps
        img = np.frombuffer(buf, np.uint8).reshape(512, 640, 3)
        tr.process(img, now=state["t"])
        n += 1
        if n % int(fps * 600) == 0:
            print(f"   ... {state['t'] / 60:.0f} min", file=sys.stderr, flush=True)
    ev("fin", "fin de la video")
    counts, dark_hole, equips = deck.f6()
    print("          F6 final", {k: v for k, v in counts.items() if v}, equips, flush=True)
    print(n, "images", file=sys.stderr)


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], *(int(v) for v in a[1:5]), *(float(v) for v in a[5:7]))
