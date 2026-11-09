"""Test en direct sur ePSXe : le moteur (image + son du jeu) tourne pendant qu'on joue
une suite de touches, puis on affiche ce qu'il a compte.

python tools/play_live_test.py "UP RIGHT UP X w4 X X" [duree_apres_s]
(meme syntaxe que drive.py keys ; wN = attendre N s)
"""

import os
import sys
import tempfile
import threading
import time

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "fm_speedtool"))
sys.path.insert(0, os.path.dirname(__file__))
import cv2  # noqa: E402

import audio  # noqa: E402
import capture  # noqa: E402
import deckscreen as ds  # noqa: E402
import drive  # noqa: E402
import tracker  # noqa: E402
import vision  # noqa: E402

KEYS = sys.argv[1]
AFTER = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0
assets = os.path.join(ROOT, "fm_speedtool", "assets")
tmp = tempfile.mkdtemp()
digits = vision.DigitReader(os.path.join(tmp, "d.json"), os.path.join(assets, "digits_default.json"))
events = []
T0 = time.monotonic()
tr = tracker.Tracker(digits, vision.TemplateLibrary(os.path.join(assets, "builtin")),
                     vision.TemplateLibrary(os.path.join(tmp, "l")),
                     lambda k, m: events.append((round(time.monotonic() - T0, 2), k, m)),
                     deck=ds.DeckReader(assets))
tr.audio_clf = audio.Classifier(os.path.join(assets, "audio_templates.npz"))
tr.audio = audio.LiveSource()
_decide = tr.audio_clf.decide


def decide_logged(samples):
    """Meme decision, avec les scores affiches (fusion / equipement)."""
    res = _decide(samples)
    f = audio.features(samples) if samples is not None else None
    sc = ("" if f is None else f" (fusion {audio.best_corr(f, tr.audio_clf.tpl['fusion']):.2f}"
          f" / equip {audio.best_corr(f, tr.audio_clf.tpl['equip']):.2f})")
    events.append((round(time.monotonic() - T0, 2), "son", f"{res}{sc}"))
    return res


tr.audio_clf.decide = decide_logged
cap = capture.WindowCapture()
cap.ensure_window()
stop = threading.Event()
n = {"f": 0}


REC = os.environ.get("REC")          # dossier : enregistre images (320x256) et son pour analyse
tr.audio.KEEP = 900.0 if REC else tr.audio.KEEP
frames, stamps = [], []


def engine():
    while not stop.is_set():
        t = time.monotonic()
        f = cap.grab()
        if f is not None:
            tr.audio.follow(cap.hwnd)
            tr.process(f)
            n["f"] += 1
            if REC and tr.last_frame is not None:
                frames.append(cv2.resize(tr.last_frame, (320, 256), interpolation=cv2.INTER_AREA))
                stamps.append(tr.last_now - T0)
        time.sleep(max(0.0, 1 / 60 - (time.monotonic() - t)))


drive.focus(cap)
th = threading.Thread(target=engine, daemon=True)
th.start()
time.sleep(1.5)
for tok in KEYS.split():
    if tok.startswith("w"):
        time.sleep(float(tok[1:]))
        continue
    name, _, rep = tok.partition("*")
    for _ in range(int(rep or 1)):
        events.append((round(time.monotonic() - T0, 2), "touche", name))
        drive.press(name)
        time.sleep(0.25)
time.sleep(AFTER)
stop.set()
th.join()
cv2.imwrite(os.path.join(ROOT, "captures", "play_end_s.png"),
            cv2.resize(cap.grab(), (480, 384), interpolation=cv2.INTER_AREA))
if REC:
    import wave

    import numpy as np
    os.makedirs(REC, exist_ok=True)
    np.save(os.path.join(REC, "frames.npy"), np.array(frames))
    np.save(os.path.join(REC, "stamps.npy"), np.array(stamps))
    with tr.audio.lock:
        t_last = tr.audio.chunks[-1][0] if tr.audio.chunks else None
        a = np.concatenate([c for _, c in tr.audio.chunks]) if tr.audio.chunks else None
    if a is not None:
        start = t_last - len(a) / audio.SR - T0          # temps (depuis T0) du 1er echantillon
        open(os.path.join(REC, "sound_start.txt"), "w").write(f"{start:.4f}")
        with wave.open(os.path.join(REC, "sound.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(audio.SR)
            w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())
print(f"moteur {n['f'] / (time.monotonic() - T0):.0f} img/s, son : {tr.audio.status}")
for t, k, m in events:
    if k != "touche":
        print(f"{t:6.2f}  {k:10s} {m}")
print("stats :", {k: v for k, v in tr.stats.items() if v} if hasattr(tr, "stats") else "")
