"""Extinction programmée des LED (ventilateurs + carte mère), avec fondu.

Le niveau (0 = éteint, 1 = allumé) est une fonction pure de l'heure locale :
pas d'état partagé entre les threads qui pilotent les LED. Le fondu applique
le niveau à la couleur courante (respiration comprise), donc la teinte du
moment s'éteint et se rallume progressivement.
"""
from __future__ import annotations

import time

DAY = 86400.0


def parse_hhmm(s: str) -> float:
    """"07:00" -> secondes depuis minuit."""
    h, _, m = s.partition(":")
    h, m = int(h), int(m or 0)
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError(f"heure invalide : {s!r}")
    return h * 3600.0 + m * 60.0


def _smooth(x: float) -> float:
    return x * x * (3 - 2 * x)


class LightSchedule:
    """Plage nocturne [off, on[ (peut passer minuit) et durée du fondu.

    off=None : jamais éteint. Au démarrage du service, le niveau part de
    l'état opposé et fond vers l'état attendu (pas de coupure sèche).
    """

    def __init__(self, off: str | None = "00:00", on: str = "07:00", fade_s: float = 6.0):
        self.off = None if off is None else parse_hhmm(off)
        self.on = parse_hhmm(on)
        self.fade = max(0.1, fade_s)
        self._start = time.time()

    def _clock(self, now: float) -> float:
        lt = time.localtime(now)
        return lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec + (now % 1.0)

    def raw_level(self, now: float) -> float:
        if self.off is None:
            return 1.0
        s = self._clock(now)
        night_len = (self.on - self.off) % DAY
        since_off = (s - self.off) % DAY
        if since_off < night_len:                       # nuit : fondu de sortie après `off`
            return max(0.0, 1.0 - since_off / self.fade)
        since_on = (s - self.on) % DAY                  # jour : fondu d'entrée après `on`
        return min(1.0, since_on / self.fade)

    def level(self, now: float | None = None) -> float:
        now = time.time() if now is None else now
        lv = self.raw_level(now)
        boot = min(1.0, max(0.0, (now - self._start) / self.fade))
        lv = max(lv, 1.0 - boot) if lv < 0.5 else min(lv, boot)   # fondu aussi au démarrage
        return _smooth(lv)

    def apply(self, c, now: float | None = None) -> tuple[int, int, int]:
        """Couleur courante atténuée (gamma 2 : fondu perçu régulier)."""
        k = self.level(now) ** 2
        return tuple(int(round(x * k)) for x in c)
