#!/usr/bin/env python3
"""Démo : animation en boucle sur l'écran LCD (streaming image par image).

Usage : demo.py [fps] [images par tour]   (Ctrl+C ou `systemctl stop kl-demo` pour arrêter)
"""
import sys

from PIL import Image, ImageDraw

from kraken_lxc import lcd
from kraken_lxc.hue2 import find_kraken

FPS = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
N = int(sys.argv[2]) if len(sys.argv) > 2 else 36

dev = find_kraken()
with dev.connect():
    dev.initialize()
    frames = []
    for i in range(N):
        im = Image.new("RGB", (240, 240), (0, 0, 0))
        d = ImageDraw.Draw(im)
        a = i * 360 // N
        d.arc((15, 15, 225, 225), a, a + 90, fill=(0, 200, 255), width=14)
        d.arc((15, 15, 225, 225), a + 180, a + 270, fill=(0, 255, 120), width=14)
        d.text((88, 112), "ProxBoss", fill=(255, 255, 255))
        path = f"/tmp/kl-demo-{i}.png"
        im.save(path)
        frames.append(dev._prepare_static_file_rgb16(path, 0))
    lcd.stream(dev, frames, fps=FPS)
