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
import subprocess
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


def run(fps: float, temp_override: float | None) -> None:
    load = metrics.CpuLoad()
    particles = render.Particles()
    dev = find_kraken()
    with dev.connect():
        dev.initialize()
        hue = Hue2(dev)
        last_colors = None
        next_poll = 0.0
        view = None
        period = 1.0 / fps
        while True:
            t0 = time.monotonic()
            if t0 >= next_poll:
                next_poll = t0 + 2.0
                used, total = metrics.ram()
                lxc = metrics.lxc_state()
                temp = temp_override if temp_override is not None else metrics.cpu_temp()
                view = render.View(
                    cpu_temp=temp, cpu_load=load.percent(), ram_used=used, ram_total=total,
                    lxc_running=lxc.running, lxc_expected=lxc.expected, lxc_ok=lxc.ok,
                    notifications=notify.count(),
                )
                state_col = render.GREEN if lxc.ok else render.ORANGE
                # par paliers de 5 °C pour ne pas réécrire à chaque variation
                temp_col = render.temp_color(round((temp if temp is not None else 50) / 5) * 5)
                if (state_col, temp_col) != last_colors:
                    hue.set_fans([state_col, temp_col])
                    try:
                        _set_board(state_col)
                    except Exception:  # la carte mère est optionnelle
                        log.exception("RGB carte mère")
                    last_colors = (state_col, temp_col)
                    log.info("couleurs : LXC %s, temp %s", state_col, temp_col)
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
