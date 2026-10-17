#!/usr/bin/env python3
"""Test : détecte les LED du Kraken, puis applique une couleur.

Usage :
  probe.py                    affiche les canaux LED détectés
  probe.py RRGGBB             même couleur sur les 2 ventilateurs
  probe.py RRGGBB RRGGBB      une couleur par ventilateur
"""
import sys

from kraken_lxc.hue2 import Hue2, find_kraken


def parse(hexcol: str) -> tuple[int, int, int]:
    return tuple(int(hexcol[i:i + 2], 16) for i in (0, 2, 4))


dev = find_kraken()
with dev.connect():
    h = Hue2(dev)
    print("Canaux LED :", h.lighting_info())
    cols = [parse(c) for c in sys.argv[1:]]
    if len(cols) == 1:
        h.set_fans_color(cols[0])
    elif cols:
        h.set_fans(cols)
    if cols:
        print("Ventilateurs ->", " / ".join("#" + c for c in sys.argv[1:]))
