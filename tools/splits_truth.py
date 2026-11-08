"""Verite terrain des splits d'une video de stream : la ligne surlignee (bleue)
de LiveSplit, lue 4 fois par seconde. Ecrit split_row dans index.csv du dossier
(cree par extract_any.py), pour que replay_video.py affiche les vrais splits.

python tools/splits_truth.py VIDEO DOSSIER X Y W H
X Y W H : liste des splits de LiveSplit dans la video.
"""

import csv
import os
import subprocess
import sys

import cv2
import imageio_ffmpeg
import numpy as np

FPS = 4


def highlight_row(panel):
    p = panel.astype(int)
    blue = (p[..., 0] > 150) & (p[..., 0] > p[..., 2] + 80) & (p[..., 1] < 170)
    rows = np.nonzero(blue.sum(1) > panel.shape[1] * 0.5)[0]
    return int(rows.mean()) if rows.size else -1


def stable(rows, hold=4, step=8):
    """Ligne retenue seulement si elle tient `hold` images de suite (le fond anime
    du layout fait parfois croire a un bandeau bleu) ; arrondie au pas `step` px."""
    out, cur = [], -1
    for i, r in enumerate(rows):
        win = rows[i:i + hold]
        if r != -1 and len(win) == hold and max(win) - min(win) <= 3:
            if cur == -1 or abs(r - cur) > step:
                cur = r
        out.append(cur)
    return out


def splits_counter(frames, hold=4, thr=18.0):
    """Compteur de splits : +1 quand la ligne surlignee change de place OU de contenu
    (icone + nom ; la liste peut defiler sous un bandeau fixe), de facon stable."""
    out, count, ref = [], 0, None        # ref = (ligne, signature) du split courant
    for i, (r, sig) in enumerate(frames):
        win = frames[i:i + hold]
        ok = sig is not None and len(win) == hold and all(
            s is not None and abs(rr - r) <= 3 and float(np.abs(s - sig).mean()) < thr / 2
            for rr, s in win)
        if ok:
            if ref is None:
                ref = (r, sig)
            elif abs(r - ref[0]) > 8 or float(np.abs(sig - ref[1]).mean()) > thr:
                ref = (r, sig)
                count += 1
        out.append(count if ref is not None else -1)
    return out


def main(video, folder, x, y, w, h):
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-i", video,
           "-vf", f"fps={FPS},crop={w}:{h}:{x}:{y}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=w * h * 3 * 8)
    rows = []
    while True:
        buf = proc.stdout.read(w * h * 3)
        if len(buf) < w * h * 3:
            break
        panel = np.frombuffer(buf, np.uint8).reshape(h, w, 3)
        r = highlight_row(panel)
        sig = None
        if r != -1:
            band = panel[max(0, r - 8):r + 8, :int(w * 0.55)]
            sig = cv2.resize(cv2.cvtColor(band, cv2.COLOR_BGR2GRAY), (48, 8),
                             interpolation=cv2.INTER_AREA).astype(np.float32)
        rows.append((r, sig))
    proc.wait()
    rows = splits_counter(rows)
    path = os.path.join(folder, "index.csv")
    with open(path, newline="") as f:
        data = list(csv.DictReader(f))
    for r in data:
        i = int(r["i"])
        r["split_row"] = rows[i] if i < len(rows) else -1
    with open(path, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["i", "t", "split_row"])
        wr.writeheader()
        wr.writerows(data)
    changes = [i for i in range(1, len(rows)) if rows[i] != rows[i - 1]]
    print("changements :", [(i, rows[i - 1], rows[i]) for i in changes][:60])
    changes = len(changes)
    print(len(rows), "images,", changes, "changements de ligne")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], *(int(v) for v in a[2:6]))
