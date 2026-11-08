"""Test en direct : depuis le menu du jeu (curseur sur BUILD DECK), le moteur tourne
pendant qu'on entre dans le deck, qu'on le fait defiler vite avec R1 et qu'on
ressort. Puis on y retourne lentement, page par page, pour la verite.

python tools/deck_r1_test.py [delai_entre_R1_s]
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

import capture  # noqa: E402
import deckscreen as ds  # noqa: E402
import drive  # noqa: E402
import tracker  # noqa: E402
import vision  # noqa: E402

GAP = float(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else 0.1
assets = os.path.join(ROOT, "fm_speedtool", "assets")
tmp = tempfile.mkdtemp()
reader = ds.DeckReader(assets)
tr = tracker.Tracker(vision.DigitReader(os.path.join(tmp, "d.json"), os.path.join(assets, "digits_default.json")),
                     vision.TemplateLibrary(os.path.join(assets, "builtin")),
                     vision.TemplateLibrary(os.path.join(tmp, "l")), lambda k, m: None, deck=reader)
cap = capture.WindowCapture()
cap.ensure_window()
stop = threading.Event()
TRACE = [] if "--trace" in sys.argv else None
n_frames = [0]


def engine():
    while not stop.is_set():
        t = time.monotonic()
        f = cap.grab()
        if f is not None:
            tr.process(f)
            n_frames[0] += 1
            if TRACE is not None and tr.last_frame is not None:
                rows = ds.deck_rows(tr.last_frame, reader.deck_digits)
                TRACE.append((round(time.monotonic() - t0, 3), sorted(p for p, _ in rows.values())))
        time.sleep(max(0.0, 1 / 60 - (time.monotonic() - t)))


def press(k, gap):
    drive.press(k, hold=0.08)
    time.sleep(gap)


def grab_img():
    while True:
        f = cap.grab()
        if f is not None:
            return vision.normalize(tr.area.crop(f))
        time.sleep(0.05)


LIB = vision.TemplateLibrary(os.path.join(assets, "builtin"))


def wait_screen(name, timeout=4.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        img = grab_img()
        if name in {t.action for t in LIB.matching(img, vision.prepare(img))}:
            return True
        time.sleep(0.1)
    return False


drive.focus(cap)
time.sleep(1.0)
# 1) passage rapide, moteur en marche
th = threading.Thread(target=engine, daemon=True)
t0 = time.monotonic()
th.start()
press("X", 0.2)          # BUILD DECK -> coffre
if not wait_screen("chest_screen"):
    stop.set()
    sys.exit("ecran du coffre pas atteint : arret (aucune autre touche)")
time.sleep(0.8)
press("RIGHT", 0.2)      # deck (a droite)
if not wait_screen("deck_screen"):
    stop.set()
    sys.exit("ecran du deck pas atteint : arret")
t1 = time.monotonic()
for _ in range(5):
    press("R1", GAP)     # page suivante, vite
t_scroll = time.monotonic() - t1
press("O", 1.5)          # on quitte le deck
stop.set()
th.join()
fps = n_frames[0] / (time.monotonic() - t0)
seen = dict(reader.watcher.slots)
tool_deck = sorted(reader.watcher.cards())
print(f"moteur {fps:.0f} img/s ; 5 x R1 en {t_scroll:.2f} s ; compteur lu {reader.watcher.count} ; "
      f"complet {reader.watcher.complete}")

if TRACE:
    last = None
    for t, ps in TRACE:
        key = (ps[0], ps[-1]) if ps else None
        if key != last:
            print(f"   {t:6.3f}s  positions lues {key}")
            last = key
missing = [p for p in range(1, (reader.watcher.count or 40) + 1) if p not in seen]
print("positions non vues pendant le passage rapide :", missing or "aucune")
if "--fast-only" in sys.argv:
    sys.exit()
# 2) verite : on revient lentement, page par page
time.sleep(2.5)
press("X", 0.2)
if not wait_screen("chest_screen"):
    sys.exit("coffre pas atteint pour la verite : arret")
time.sleep(0.8)
press("RIGHT", 0.2)
if not wait_screen("deck_screen"):
    sys.exit("deck pas atteint pour la verite : arret")
truth = {}
for page in range(6):
    time.sleep(0.6)
    img = grab_img()
    truth.update(dict(ds.deck_rows(img, reader.deck_digits).values()))
    cv2.imwrite(os.path.join(ROOT, "captures", f"r1_truth_p{page}.png"), img)
    press("R1", 0.2)
count = ds.deck_count(img, reader.count_digits) or 40
press("O", 1.0)

db = reader.db
ok = 0
print(f"\n{'pos':>3}  {'vraie carte':28} {'vue par le logiciel':28}")
for p in range(1, count + 1):
    t, s = truth.get(p), seen.get(p)
    ok += t is not None and t == s
    flag = "" if t == s else "   <-- DIFFERENT"
    print(f"{p:3d}  {(db.name(t) if t else '?'):28} {(db.name(s) if s else '(pas vue)'):28}{flag}")
truth_deck = sorted(truth[p] for p in range(1, count + 1) if p in truth)
print(f"\npositions identiques : {ok}/{count} ; deck reconstitue identique : {tool_deck == truth_deck}")
