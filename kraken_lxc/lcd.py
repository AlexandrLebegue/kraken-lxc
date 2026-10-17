"""Écran LCD 240x240 du Kraken 2024 Plus (1e71:3014).

Le chemin d'upload standard de liquidctl (buckets) échoue sur ce modèle
(liquidctl #908 : "missing messages"). Le Plus accepte en revanche le transfert
direct "fw2" sans buckets, prévu dans liquidctl pour le Kraken 2023 firmware 2.x :
  0x36 0x01 0x00 0x01 <type>  -> en-tête bulk + données -> 0x36 0x02
Confirmé visuellement le 2026-10-17 pour une image statique (type 0x06, RGB16).
"""
from __future__ import annotations

import time

from liquidctl.driver.kraken3 import KrakenZ3

BULK_MAGIC = [0x12, 0xFA, 0x01, 0xE8, 0xAB, 0xCD, 0xEF, 0x98, 0x76, 0x54, 0x32, 0x10]
TYPE_STATIC_RGB16 = 0x06


def _send(dev: KrakenZ3, kind: int, data: bytes) -> None:
    info = [kind, 0x00, 0x00, 0x00] + list(len(data).to_bytes(4, "little"))
    dev._write_then_read([0x36, 0x01, 0x00, 0x01, kind])
    dev._bulk_write(BULK_MAGIC + info)
    for i in range(0, len(data), dev.bulk_buffer_size):
        dev._bulk_write(list(data[i:i + dev.bulk_buffer_size]))
    dev._write_then_read([0x36, 0x02])


def show_image(dev: KrakenZ3, path: str, orientation: int = 0) -> None:
    """Affiche une image fixe (redimensionnée en 240x240 par liquidctl)."""
    data = dev._prepare_static_file_rgb16(path, orientation)
    # Le premier envoi après initialisation doit être doublé (comportement
    # observé par liquidctl sur le firmware 2.x, conservé ici).
    _send(dev, TYPE_STATIC_RGB16, data)
    _send(dev, TYPE_STATIC_RGB16, data)


def stream(dev: KrakenZ3, frames: list[bytes], fps: float = 10.0,
           duration: float | None = None) -> None:
    """Animation envoyée image par image depuis l'hôte.

    Le GIF natif n'est PAS supporté sur le Plus via ce transfert : les octets du
    GIF sont affichés comme des pixels bruts (bruit en haut de l'écran, testé le
    2026-10-17). `frames` = images déjà converties par
    `dev._prepare_static_file_rgb16`. Débit brut mesuré : ~55 img/s.
    """
    period = 1.0 / fps
    start = time.monotonic()
    i = 0
    while duration is None or time.monotonic() - start < duration:
        t = time.monotonic()
        _send(dev, TYPE_STATIC_RGB16, frames[i % len(frames)])
        i += 1
        time.sleep(max(0.0, period - (time.monotonic() - t)))


def show_liquid(dev: KrakenZ3) -> None:
    """Revient à l'affichage natif de la température du liquide."""
    dev.set_screen("lcd", "liquid", None)
