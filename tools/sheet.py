"""Planche contact d'images extraites : python tools/sheet.py DOSSIER SORTIE i1 i2 ... (ou a:b:pas)"""

import os
import sys

import cv2
import numpy as np


def indices(args):
    out = []
    for a in args:
        if ":" in a:
            s, e, *st = (int(x) for x in a.split(":"))
            out += list(range(s, e, st[0] if st else 1))
        else:
            out.append(int(a))
    return out


def main(folder, dest, args, cols=6, size=(200, 160)):
    tiles = []
    for i in indices(args):
        img = cv2.imread(os.path.join(folder, "frames", f"{i:06d}.jpg"))
        if img is None:
            img = np.zeros((size[1], size[0], 3), np.uint8)
        img = cv2.resize(img, size, interpolation=cv2.INTER_AREA)
        cv2.putText(img, str(i), (3, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        tiles.append(img)
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[k:k + cols]) for k in range(0, len(tiles), cols)]
    cv2.imwrite(dest, np.vstack(rows))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
