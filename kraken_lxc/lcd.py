"""Écran LCD 240x240 du Kraken 2024 Plus (1e71:3014).

Le chemin d'upload standard de liquidctl (buckets) échoue sur ce modèle
(liquidctl #908 : "missing messages"). Le Plus accepte en revanche le transfert
direct "fw2" sans buckets, prévu dans liquidctl pour le Kraken 2023 firmware 2.x :
  0x36 0x01 0x00 0x01 <type>  -> en-tête bulk + données -> 0x36 0x02
Confirmé visuellement le 2026-10-17 pour une image statique (type 0x06, RGB16).

Le GIF natif n'est PAS supporté via ce transfert : les octets du GIF sont
affichés comme des pixels bruts (bruit en haut de l'écran, testé le 2026-10-17).
Les animations sont donc envoyées image par image depuis l'hôte.

Synchronisation reprise de kori (github.com/arthjean/kori, GPL-3.0,
crates/hardware-linux/src/lcd.rs) : attendre l'acquittement de chaque commande
de transfert, et envoyer chaque image deux fois.
"""
from __future__ import annotations

import time

from liquidctl.driver.kraken3 import KrakenZ3

BULK_MAGIC = [0x12, 0xFA, 0x01, 0xE8, 0xAB, 0xCD, 0xEF, 0x98, 0x76, 0x54, 0x32, 0x10]
TYPE_STATIC_RGB16 = 0x06
REPORT_LEN = 64
ACK = 0x37
ACK_TIMEOUT_S = 0.05


def _write(dev: KrakenZ3, data: list[int]) -> None:
    dev.device.write(data + [0] * (REPORT_LEN - len(data)))


def _await_ack(dev: KrakenZ3, sub: int) -> bool:
    """Attend `0x37 <sub>`, l'acquittement d'une commande `0x36 <sub>`.

    Le Kraken intercale ses rapports d'état sur la même interface HID : lire
    « le prochain rapport » (comme `_write_then_read`) peut tomber sur un rapport
    d'état et laisser partir les pixels avant que l'écran soit prêt. On filtre
    donc sur l'identifiant, avec un délai court (sans réponse, on continue).
    """
    deadline = time.monotonic() + ACK_TIMEOUT_S
    while (left := deadline - time.monotonic()) > 0:
        msg = dev.device.read(REPORT_LEN, timeout=max(1, int(left * 1000)))
        if msg and msg[0] == ACK and msg[1] == sub:
            return True
    return False


def _send(dev: KrakenZ3, kind: int, data: bytes) -> int:
    """Une séquence de transfert ; renvoie le nombre d'acquittements reçus (0-2)."""
    info = [kind, 0x00, 0x00, 0x00] + list(len(data).to_bytes(4, "little"))
    _write(dev, [0x36, 0x01, 0x00, 0x01, kind])
    acks = _await_ack(dev, 0x01)
    dev._bulk_write(BULK_MAGIC + info)
    for i in range(0, len(data), dev.bulk_buffer_size):
        dev._bulk_write(list(data[i:i + dev.bulk_buffer_size]))
    _write(dev, [0x36, 0x02])
    return acks + _await_ack(dev, 0x02)


def send_frame(dev: KrakenZ3, data: bytes) -> int:
    """Image complète envoyée deux fois : l'écran a deux tampons et, sinon,
    affiche l'image précédente. Renvoie les acquittements reçus (0-4)."""
    return _send(dev, TYPE_STATIC_RGB16, data) + _send(dev, TYPE_STATIC_RGB16, data)


def show_image(dev: KrakenZ3, path: str, orientation: int = 0) -> int:
    """Affiche une image fixe (redimensionnée en 240x240 par liquidctl)."""
    return send_frame(dev, dev._prepare_static_file_rgb16(path, orientation))


def stream(dev: KrakenZ3, frames: list[bytes], fps: float = 10.0,
           duration: float | None = None) -> None:
    """Animation envoyée image par image depuis l'hôte.

    `frames` = images déjà converties par `dev._prepare_static_file_rgb16`.
    """
    period = 1.0 / fps
    start = time.monotonic()
    i = 0
    while duration is None or time.monotonic() - start < duration:
        t = time.monotonic()
        send_frame(dev, frames[i % len(frames)])
        i += 1
        time.sleep(max(0.0, period - (time.monotonic() - t)))


def show_liquid(dev: KrakenZ3) -> None:
    """Revient à l'affichage natif de la température du liquide."""
    dev.set_screen("lcd", "liquid", None)
