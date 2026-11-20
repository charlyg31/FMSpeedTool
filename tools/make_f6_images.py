"""Images de la fenetre Final 6 (fm_speedtool/assets/f6/), toutes prises dans le jeu.

Cartes : grande illustration (102x96, 256 couleurs) lue sur le disque du jeu, dans
DATA/WA_MRG.MRG (a 0x169000, un bloc de 0x3800 octets par carte, dans l'ordre des numeros).
Boss : visage du dialogue d'avant-duel dans la video All Duelists (YouTube NzFnsCr3ENc,
images extraites par extract_any.py).

python tools/make_f6_images.py JEU.bin DOSSIER_VIDEO_ALL_DUELISTS
"""

import os
import struct
import sys

import cv2
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "fm_speedtool", "assets", "f6")
SIZE = (204, 192)
# Case -> numero de la carte (une carte qui represente sa categorie pour les groupes)
CARDS = {"dragonsUnder1600": 200, "dragons1600Plus": 39, "thunderDragons": 425, "thunders": 191,
         "umi": 334, "wsr": 686, "mm": 657, "mbd": 713, "skullKnight": 707, "darkMagician": 35,
         "zoa": 391, "ushiOni": 401, "mountain": 332, "fields": 333, "dcj": 329, "ath": 685,
         "crushCard": 661, "raigeki": 337, "dark_hole": 336,
         "equip_bright_castle": 668, "equip_dragon_treasure": 315, "equip_dark_energy": 303,
         "equip_beast_fangs": 308, "equip_invigoration": 324, "equip_horn_of_light": 313}
ART_AT, ART_STEP, ART_W, ART_H = 0x169000, 0x3800, 102, 96
# Portraits : image de la video et centre du visage
BOSSES = {"sebek": (18053, 210), "neku": (18359, 430), "heishin": (18800, 210),
          "seto3": (19234, 210), "darknite": (20551, 210), "nitemare": (21281, 210)}


def read_file(bin_path, wanted):
    """Fichier d'une image disque MODE2/2352 (ISO 9660), ex. "DATA/WA_MRG.MRG"."""
    f = open(bin_path, "rb")

    def sector(n, count=1):
        out = b""
        for i in range(count):
            f.seek((n + i) * 2352)
            out += f.read(2352)[24:24 + 2048]
        return out

    lba, size = struct.unpack("<I", sector(16)[158:162])[0], struct.unpack("<I", sector(16)[166:170])[0]
    for part in wanted.split("/"):
        data, i, found = sector(lba, (size + 2047) // 2048), 0, None
        while i < len(data):
            n = data[i]
            if n == 0:
                i = (i // 2048 + 1) * 2048
                continue
            e = data[i:i + n]
            if e[33:33 + e[32]].decode("ascii", "replace").split(";")[0] == part:
                found = struct.unpack("<I", e[2:6])[0], struct.unpack("<I", e[10:14])[0]
                break
            i += n
        if found is None:
            raise FileNotFoundError(wanted)
        lba, size = found
    return sector(lba, (size + 2047) // 2048)[:size]


def card_art(mrg, cid):
    o = ART_AT + (cid - 1) * ART_STEP
    px = np.frombuffer(mrg[o:o + ART_W * ART_H], np.uint8).reshape(ART_H, ART_W)
    pal = np.frombuffer(mrg[o + ART_W * ART_H:o + ART_W * ART_H + 512], "<u2").astype(np.uint16)
    bgr = np.stack([(pal >> 10) & 31, (pal >> 5) & 31, pal & 31], 1) * 255 // 31   # couleurs PS1 15 bits
    return bgr.astype(np.uint8)[px]


def main(bin_path, video):
    os.makedirs(OUT, exist_ok=True)
    mrg = read_file(bin_path, "DATA/WA_MRG.MRG")
    for key, cid in CARDS.items():
        cv2.imwrite(os.path.join(OUT, key + ".png"),
                    cv2.resize(card_art(mrg, cid), SIZE, interpolation=cv2.INTER_CUBIC))
    faces = []
    for key, (i, cx) in BOSSES.items():
        img = cv2.imread(os.path.join(video, "frames", f"{i:06d}.jpg"))
        face = cv2.resize(img[10:250, cx - 120:cx + 120], (168, 168), interpolation=cv2.INTER_AREA)
        cv2.imwrite(os.path.join(OUT, f"boss_{key}.png"), face)
        faces.append(cv2.resize(face, (84, 84), interpolation=cv2.INTER_AREA))
    mosaic = np.vstack([np.hstack(faces[:3]), np.hstack(faces[3:])])
    mosaic = cv2.copyMakeBorder(mosaic, 42, 42, 0, 0, cv2.BORDER_CONSTANT, value=(20, 18, 17))
    cv2.imwrite(os.path.join(OUT, "boss_final6.png"), cv2.resize(mosaic, (168, 168), interpolation=cv2.INTER_AREA))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
