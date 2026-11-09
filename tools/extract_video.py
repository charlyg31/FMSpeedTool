"""Extrait une video OBS de run : images du jeu (640x512, 4/s) + position du split
surligne dans LiveSplit (verite terrain des splits).

python tools/extract_video.py VIDEO DOSSIER_SORTIE [DEBUT_EN_SECONDES] [DUREE_EN_SECONDES]
Mise en page attendue (4K) : jeu en x 1204..3764, y 0..2048 ; LiveSplit a gauche.
"""

import csv
import os
import subprocess
import sys

import cv2
import imageio_ffmpeg
import numpy as np

FPS = 4
OW, OH = 1280, 684           # image complete reduite (3840x2054 / 3)
GAME = (401, 0, 853, 683)    # jeu dans l'image reduite
SPLITS = (30, 20, 275, 365)  # liste des splits LiveSplit dans l'image reduite


def highlight_row(panel):
    """Ordonnee du bandeau bleu du split courant, ou -1."""
    p = panel.astype(int)
    blue = (p[..., 0] > 150) & (p[..., 0] > p[..., 2] + 80) & (p[..., 1] < 140)
    rows = np.nonzero(blue.sum(1) > panel.shape[1] * 0.6)[0]
    return int(rows.mean()) if rows.size else -1


def main(video, out, start=0.0, duration=None):
    os.makedirs(os.path.join(out, "frames"), exist_ok=True)
    os.makedirs(os.path.join(out, "splits"), exist_ok=True)
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-hwaccel", "auto",
           "-ss", str(start)] + (["-t", str(duration)] if duration else []) + ["-i", video, "-vf", f"fps={FPS},scale={OW}:{OH}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=OW * OH * 3 * 4)
    size = OW * OH * 3
    gx, gy, gw, gh = GAME
    sx, sy, sw, sh = SPLITS
    with open(os.path.join(out, "index.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["i", "t", "split_row"])
        i = 0
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            img = np.frombuffer(buf, np.uint8).reshape(OH, OW, 3)
            game = cv2.resize(img[gy:gy + gh, gx:gx + gw], (640, 512), interpolation=cv2.INTER_AREA)
            cv2.imwrite(os.path.join(out, "frames", f"{i:06d}.jpg"), game, [cv2.IMWRITE_JPEG_QUALITY, 90])
            panel = img[sy:sy + sh, sx:sx + sw]
            w.writerow([i, i / FPS, highlight_row(panel)])
            if i % (FPS * 30) == 0:
                cv2.imwrite(os.path.join(out, "splits", f"{i:06d}.jpg"), panel)
                f.flush()
                print(f"{i / FPS / 60:.1f} min", flush=True)
            i += 1
    proc.wait()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 0.0,
         float(sys.argv[4]) if len(sys.argv) > 4 else None)
