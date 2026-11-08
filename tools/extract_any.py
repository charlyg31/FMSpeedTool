"""Extrait les images du jeu d'une video de run quelconque (stream, YouTube).

python tools/extract_any.py VIDEO DOSSIER_SORTIE X Y W H
X Y W H : zone du jeu dans la video (pixels de la video). Sortie : frames/
en 640x512 a 4 images/s + index.csv (sans splits LiveSplit : split_row = -1),
lisible par replay_video.py et rank_check.py.

python tools/extract_any.py VIDEO SORTIE.png --shot SECONDES : une image pour
reperer la zone du jeu.
"""

import csv
import os
import subprocess
import sys

import cv2
import imageio_ffmpeg
import numpy as np

FPS = 4


def size_of(video):
    cap = cv2.VideoCapture(video)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return w, h


def shot(video, out, t):
    cap = cv2.VideoCapture(video)
    cap.set(cv2.CAP_PROP_POS_MSEC, float(t) * 1000)
    ok, img = cap.read()
    cap.release()
    if ok:
        cv2.imwrite(out, img)
    print(out if ok else "lecture impossible")


def main(video, out, x, y, w, h):
    vw, vh = size_of(video)
    os.makedirs(os.path.join(out, "frames"), exist_ok=True)
    # La zone peut deborder de la video (cadrage console) : bandes noires.
    cx0, cy0 = max(0, x), max(0, y)
    cx1, cy1 = min(vw, x + w), min(vh, y + h)
    crop = f"crop={cx1 - cx0}:{cy1 - cy0}:{cx0}:{cy0},pad={w}:{h}:{cx0 - x}:{cy0 - y}"
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-i", video,
           "-vf", f"fps={FPS},{crop},scale=640:512:flags=area",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=640 * 512 * 3 * 4)
    size = 640 * 512 * 3
    with open(os.path.join(out, "index.csv"), "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["i", "t", "split_row"])
        i = 0
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            img = np.frombuffer(buf, np.uint8).reshape(512, 640, 3)
            cv2.imwrite(os.path.join(out, "frames", f"{i:06d}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            wr.writerow([i, i / FPS, -1])
            if i % (FPS * 300) == 0:
                print(f"{i / FPS / 60:.0f} min", flush=True)
            i += 1
    proc.wait()
    print(i, "images", (vw, vh))


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 3 and a[2] == "--shot":
        shot(a[0], a[1], a[3])
    else:
        main(a[0], a[1], *(int(v) for v in a[2:6]))
