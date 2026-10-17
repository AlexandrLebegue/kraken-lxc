#!/usr/bin/env python3
"""Test : détecte les LED du Kraken, puis applique une couleur fixe.

Usage : probe.py [info] | [fans|ring|all RRGGBB]
"""
import sys
from kraken_lxc.hue2 import Hue2, find_kraken

dev = find_kraken()
with dev.connect():
    h = Hue2(dev)
    info = h.lighting_info()
    print("Lighting info:", info)
    if len(sys.argv) >= 3:
        target, hexcol = sys.argv[1], sys.argv[2]
        rgb = tuple(int(hexcol[i:i + 2], 16) for i in (0, 2, 4))
        chans = ["ring", "fans"] if target == "all" else [target]
        for c in chans:
            leds = info.get(c, {}).get("leds") or 24
            h.set_color(c, rgb, leds)
            print(f"{c}: {leds} LED -> #{hexcol}")
