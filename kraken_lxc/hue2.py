"""Contrôle RGB "Direct" (protocole NZXT HUE2) pour Kraken 2023/2024 (KrakenZ3).

liquidctl 1.16 n'expose pas de canal couleur pour ces modèles. Ce module parle
directement le protocole, repris d'OpenKraken (MIT, (c) 2026 David Boulay,
https://github.com/davidboulay/OpenKraken, PROTOCOL.md §3/§4/§6), lui-même basé
sur liquidctl PR #882 et le contrôleur NZXT HUE2 d'OpenRGB.
"""
from __future__ import annotations

from liquidctl.driver.kraken3 import KrakenZ3

REPORT_LEN = 64
CHANNELS = {"ring": 0x01, "fans": 0x02}
LEDS_PER_PACKET = 20
ACCESSORY_LEDS = {0x1E: 24, 0x17: 8, 0x18: 8, 0x1B: 24, 0x1C: 16, 0x1D: 24}
FALLBACK_LEDS = 8
APPLY = [0x22, 0xA0, 0x00, 0x00, 0x01, 0x00, 0x00, 0x28,
         0x00, 0x00, 0x80, 0x00, 0x32, 0x00, 0x00, 0x01]


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
        count = reply[14]
        info = {}
        for name, mask in CHANNELS.items():
            idx = mask.bit_length() - 1
            if idx >= count:
                continue
            ids = [a for a in reply[15 + idx * 6: 21 + idx * 6] if a]
            info[name] = {
                "accessories": [hex(a) for a in ids],
                "leds": sum(ACCESSORY_LEDS.get(a, FALLBACK_LEDS) for a in ids),
            }
        info["_raw"] = " ".join(f"{b:02x}" for b in reply[:32])
        return info

    def set_color(self, channel: str, rgb: tuple[int, int, int], leds: int) -> None:
        """Couleur fixe sur tout un canal : trame Direct GRB + paquet d'application."""
        mask = CHANNELS[channel]
        r, g, b = rgb
        grb = [g, r, b] * leds
        n = LEDS_PER_PACKET * 3
        self._write([0x22, 0x10, mask, 0x00] + grb[:n])
        if leds > LEDS_PER_PACKET:
            self._write([0x22, 0x11, mask, 0x00] + grb[n:])
        apply = list(APPLY)
        apply[2] = mask
        self._write(apply)
