"""Pont vers le script LiveSplit (FMSpeedTool.asl) : une petite zone de memoire
partagee Windows, nommee, que le script lit ~60 fois par seconde.

Le script ne lit que cette zone (ecrite par ce logiciel), jamais la memoire du jeu.

Disposition (entiers 32 bits, petit-boutiste) :
  0  magie 'FMST'          4  version
  8  battement (images analysees, prouve que le logiciel tourne)
  12 compteur de departs   16 compteur de splits   20 compteur de resets
  24 type du dernier split (1 victoire, 2 1re defaite, 3 fin de farm, 4 autre)
  32..63 nom de l'adversaire du dernier split (ASCII)
"""

import mmap
import struct

NAME = "FMSpeedTool_LiveSplit"
SIZE = 64
MAGIC = 0x54534D46          # 'FMST' lu en petit-boutiste
VERSION = 1
KIND_WIN, KIND_FIRST_LOSS, KIND_FARM, KIND_OTHER = 1, 2, 3, 4


class Bridge:
    def __init__(self):
        self.mem = mmap.mmap(-1, SIZE, tagname=NAME)
        self.heartbeat = 0
        self.counts = [0, 0, 0]          # departs, splits, resets
        self._write_header()

    def _write_header(self):
        self.mem.seek(0)
        self.mem.write(struct.pack("<iiiiiii", MAGIC, VERSION, self.heartbeat, *self.counts, 0))

    def beat(self):
        self.heartbeat = (self.heartbeat + 1) & 0x7FFFFFFF
        self.mem[8:12] = struct.pack("<i", self.heartbeat)

    def _bump(self, index):
        self.counts[index] += 1
        self.mem[12 + 4 * index:16 + 4 * index] = struct.pack("<i", self.counts[index])

    def start(self):
        self._bump(0)

    def reset(self):
        self._bump(2)

    def split(self, kind, opponent=""):
        # Type et adversaire d'abord : le script les lit quand le compteur change.
        self.mem[24:28] = struct.pack("<i", kind)
        name = opponent.encode("ascii", "replace")[:31]
        self.mem[32:64] = name + b"\0" * (32 - len(name))
        self._bump(1)

    def close(self):
        self.mem.close()
