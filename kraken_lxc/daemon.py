"""Démon kraken-lxc : écran LCD + couleurs selon l'état de l'hôte Proxmox.

- Écran : tableau de bord animé (~15 img/s), relevés rafraîchis toutes les 2 s.
- Ventilateur 1 + carte mère : état des LXC (vert OK, orange LXC attendu arrêté).
- Ventilateur 2 : température CPU (bleu froid -> rouge chaud).
Les couleurs ne sont réécrites qu'en cas de changement, et au démarrage.

Usage : python -m kraken_lxc.daemon [--fps 15] [--temp-override 30]
"""
from __future__ import annotations

import argparse
import logging
import threading
import time

from liquidctl import find_liquidctl_devices

from . import lcd, metrics, notify, render
from .hue2 import Hue2, find_kraken

log = logging.getLogger("kraken-lxc")


def _fusion():
    for dev in find_liquidctl_devices():
        if "Fusion" in dev.description:
            return dev
    return None


def _set_board(color: tuple[int, int, int]) -> None:
    dev = _fusion()
    if dev is None:
        return
    with dev.connect():
        dev.set_color("sync", "fixed", [color])


class Poller(threading.Thread):
    """Relevés toutes les 2 s dans un thread à part : `pct list` prend ~0,6 s
    et figeait l'écran s'il était appelé dans la boucle d'affichage."""

    def __init__(self, temp_override: float | None):
        super().__init__(daemon=True)
        self.temp_override = temp_override
        self.load = metrics.CpuLoad()
        self.view: render.View | None = None
        self.colors: tuple | None = None   # (état LXC, température) souhaités
        self._board = None
        self.poll()

    def poll(self) -> None:
        used, total = metrics.ram()
        lxc = metrics.lxc_state()
        temp = self.temp_override if self.temp_override is not None else metrics.cpu_temp()
        self.view = render.View(
            cpu_temp=temp, cpu_load=self.load.percent(), ram_used=used, ram_total=total,
            lxc_running=lxc.running, lxc_expected=lxc.expected, lxc_ok=lxc.ok,
            notifications=notify.count(),
        )
        state_col = render.GREEN if lxc.ok else render.ORANGE
        # par paliers de 5 °C pour ne pas réécrire à chaque variation
        temp_col = render.temp_color(round((temp if temp is not None else 50) / 5) * 5)
        self.colors = (state_col, temp_col)
        if state_col != self._board:  # carte mère : autre périphérique, réglé ici
            try:
                _set_board(state_col)
                self._board = state_col
            except Exception:  # la carte mère est optionnelle
                log.exception("RGB carte mère")

    def run(self) -> None:
        while True:
            time.sleep(2.0)
            try:
                self.poll()
            except Exception:
                log.exception("relevés")


def run(fps: float, temp_override: float | None) -> None:
    poller = Poller(temp_override)
    poller.start()
    particles = render.Particles()
    dev = find_kraken()
    with dev.connect():
        dev.initialize()
        hue = Hue2(dev)
        last_colors = None
        period = 1.0 / fps
        while True:
            t0 = time.monotonic()
            view, colors = poller.view, poller.colors
            if colors != last_colors:  # même périphérique USB que l'écran : ici
                hue.set_fans(list(colors))
                last_colors = colors
                log.info("couleurs ventilateurs : LXC %s, temp %s", *colors)
            particles.step(view.cpu_temp)
            lcd.send_frame(dev, render.to_rgb565(render.render(view, particles)))
            time.sleep(max(0.0, period - (time.monotonic() - t0)))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--fps", type=float, default=15.0)
    p.add_argument("--temp-override", type=float, default=None,
                   help="force la température affichée (test des effets neige/feu)")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    while True:
        try:
            run(a.fps, a.temp_override)
        except KeyboardInterrupt:
            break
        except Exception:
            log.exception("erreur, nouvelle tentative dans 5 s")
            time.sleep(5)


if __name__ == "__main__":
    main()
