"""Contrôle RGB "Direct" (protocole NZXT HUE2) pour Kraken 2023/2024 (KrakenZ3).

liquidctl 1.16 n'expose pas de canal couleur pour ces modèles. Ce module parle
directement le protocole, repris d'OpenKraken (MIT, (c) 2026 David Boulay,
https://github.com/davidboulay/OpenKraken, PROTOCOL.md §3/§4/§6), lui-même basé
sur liquidctl PR #882 et le contrôleur NZXT HUE2 d'OpenRGB.

Particularité du Kraken 2024 Plus (1e71:3014) : pas d'anneau LED sur la pompe.
Le firmware déclare un seul canal (canal 0, accessoire 0x29) qui correspond à la
chaîne de ventilateurs RGB Core (240 mm : 2 ventilateurs x 8 LED).
"""
from __future__ import annotations

from liquidctl.driver.kraken3 import KrakenZ3

REPORT_LEN = 64

# Elite : canal 0 = anneau de pompe, canal 1 = ventilateurs.
# Plus  : canal 0 = ventilateurs (pas d'anneau).
CHANNEL_MASKS = {0: 0x01, 1: 0x02}
PLUS_FANS_MASK = 0x01
LEDS_PER_FAN = 8

LEDS_PER_PACKET = 20
ACCESSORY_LEDS = {
    0x29: 16,  # Kraken 2024 Plus 240 : 2 ventilateurs RGB Core x 8 LED (confirmé visuellement)
    0x1E: 24,  # Kraken 2024 Elite : anneau de pompe
    0x17: 8,   # F140 RGB Core
    0x18: 8,   # F120 RGB Core
    0x1B: 24,  # kit radiateur RGB Core (agrégat)
    0x1C: 16,  # F280 RGB Core
    0x1D: 24,  # F360 RGB Core
}
FALLBACK_LEDS = 8
APPLY = [0x22, 0xA0, 0x00, 0x00, 0x01, 0x00, 0x00, 0x28,
         0x00, 0x00, 0x80, 0x00, 0x32, 0x00, 0x00, 0x01]

RGB = tuple[int, int, int]


def find_kraken() -> KrakenZ3:
    for dev in KrakenZ3.find_supported_devices():
        return dev
    raise RuntimeError("Aucun Kraken (KrakenZ3) détecté")


class Hue2:
    def __init__(self, dev: KrakenZ3):
        self.dev = dev

    def _write(self, data: list[int]) -> None:
        self.dev.device.write(data[:REPORT_LEN] + [0] * (REPORT_LEN - len(data)))

    def _read_until(self, prefix: tuple[int, int], attempts: int = 12) -> list[int] | None:
        for _ in range(attempts):
            msg = list(self.dev.device.read(REPORT_LEN))
            if msg[:2] == list(prefix):
                return msg
        return None

    def lighting_info(self) -> dict:
        """Lit les accessoires LED par canal (lecture seule)."""
        self.dev.device.clear_enqueued_reports()
        self._write([0x20, 0x03])
        reply = self._read_until((0x21, 0x03))
        if reply is None:
            return {}
        info = {}
        for idx in range(reply[14]):
            ids = [a for a in reply[15 + idx * 6: 21 + idx * 6] if a]
            info[idx] = {
                "accessories": [hex(a) for a in ids],
                "leds": sum(ACCESSORY_LEDS.get(a, FALLBACK_LEDS) for a in ids),
            }
        return info

    def set_frame(self, mask: int, colors: list[RGB]) -> None:
        """Trame Direct par LED (RGB -> GRB sur le fil) + paquet d'application."""
        grb = [x for (r, g, b) in colors for x in (g, r, b)]
        n = LEDS_PER_PACKET * 3
        self._write([0x22, 0x10, mask, 0x00] + grb[:n])
        if len(colors) > LEDS_PER_PACKET:
            self._write([0x22, 0x11, mask, 0x00] + grb[n:])
        apply = list(APPLY)
        apply[2] = mask
        self._write(apply)

    def set_fans(self, per_fan: list[RGB]) -> None:
        """Kraken Plus : une couleur par ventilateur, dans l'ordre de la chaîne."""
        self.set_frame(PLUS_FANS_MASK, [c for c in per_fan for _ in range(LEDS_PER_FAN)])

    def set_fans_color(self, rgb: RGB, fans: int = 2) -> None:
        """Kraken Plus : même couleur sur tous les ventilateurs."""
        self.set_fans([rgb] * fans)
