"""Labo son : spectrogrammes autour des evenements fusion/equipement d'un rejeu.

python tools/audio_lab.py WAV JOURNAL_REJEU SORTIE.png [avant_s apres_s]
JOURNAL_REJEU : sortie de replay_video.py (indices d'images a 4/s).
"""

import re
import sys
import wave

import cv2
import numpy as np

FPS = 4
SR = 22050
HOP = 256
NFFT = 1024


def load(path):
    with wave.open(path) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return a


def spec(x):
    """Spectrogramme log (frequences en lignes, temps en colonnes), 0..1."""
    win = np.hanning(NFFT).astype(np.float32)
    n = 1 + (len(x) - NFFT) // HOP
    if n <= 0:
        return np.zeros((NFFT // 2, 1), np.float32)
    idx = np.arange(NFFT)[None, :] + HOP * np.arange(n)[:, None]
    m = np.abs(np.fft.rfft(x[idx] * win, axis=1))[:, 1:NFFT // 2 + 1].T
    return np.log1p(m * 50)


def events(log):
    out = []
    for line in open(log, encoding="utf-8"):
        m = re.match(r"\s*(\d+)\s+[\d.]+min\s+stat\s+(Fusions|Equipements|Magie pure) \+1", line)
        if m:
            out.append((int(m.group(1)) / FPS, {"Fusions": "F", "Equipements": "E"}.get(m.group(2), "M")))
    return out


def main(wav, log, out, before=2.5, after=0.5):
    a = load(wav)
    tiles = []
    for t, kind in events(log)[:48]:
        s0, s1 = int((t - before) * SR), int((t + after) * SR)
        if s0 < 0 or s1 > len(a):
            continue
        sp = spec(a[s0:s1])[:256]                      # 0..5,5 kHz
        img = cv2.resize((np.clip(sp / 3, 0, 1) * 255).astype(np.uint8)[::-1], (240, 128))
        img = cv2.applyColorMap(img, cv2.COLORMAP_INFERNO)
        cv2.putText(img, f"{kind} {t:.1f}s", (4, 16), 0, 0.5, (255, 255, 255), 1)
        tiles.append(img)
    while len(tiles) % 6:
        tiles.append(np.zeros_like(tiles[0]))
    cv2.imwrite(out, np.vstack([np.hstack(tiles[i:i + 6]) for i in range(0, len(tiles), 6)]))
    print(len(events(log)), "evenements")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], a[2], *(float(v) for v in a[3:5]))
