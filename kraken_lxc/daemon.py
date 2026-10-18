"""Démon kraken-lxc : écran LCD + couleurs selon l'état de l'hôte Proxmox.

- Écran : tableau de bord animé (~15 img/s), relevés rafraîchis toutes les 2 s.
  L'état des LXC est porté par l'icône du robot.
- Ventilateurs + carte mère : même palette que la barre de température
  (bleu/violet froid -> rouge/orange chaud), en respiration lente (6 s).

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


class BoardLight(threading.Thread):
    """Carte mère (RGB Fusion, autre périphérique) : ~6 écritures/s, ~33 ms chacune."""

    def __init__(self, anim: render.Anim):
        super().__init__(daemon=True)
        self.anim = anim

    def run(self) -> None:
        while True:
            dev = _fusion()
            if dev is None:
                return
            try:
                with dev.connect():
                    while True:
                        t0 = time.monotonic()
                        if self.anim.heat is not None:
                            c = render.light_color(self.anim.heat, t0 - self.anim._t0)
                            dev.set_color("sync", "fixed", [c])
                        time.sleep(max(0.0, 0.16 - (time.monotonic() - t0)))
            except Exception:
                log.exception("RGB carte mère, nouvelle tentative dans 5 s")
                time.sleep(5)


class Poller(threading.Thread):
    """Relevés toutes les 2 s dans un thread à part : `pct list` prend ~0,6 s
    et figeait l'écran s'il était appelé dans la boucle d'affichage."""

    def __init__(self, temp_override: float | None):
        super().__init__(daemon=True)
        self.temp_override = temp_override
        self.load = metrics.CpuLoad()
        self.view: render.View | None = None
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

    def run(self) -> None:
        while True:
            time.sleep(2.0)
            try:
                self.poll()
            except Exception:
                log.exception("relevés")


def run(fps: float, poller: Poller, anim: render.Anim) -> None:
    """Boucle d'affichage. Relancée après une erreur USB ; les threads (relevés,
    carte mère) sont créés une seule fois dans main() et réutilisés."""
    dev = find_kraken()
    with dev.connect():
        dev.initialize()
        hue = Hue2(dev)
        period = 1.0 / fps
        frame = 0
        while True:
            t0 = time.monotonic()
            view = poller.view
            anim.step(view.cpu_temp)
            if frame % 8 == 0:  # ventilateurs : ~2 màj/s (1/s confirmé OK, ~4/s ignoré)
                c = render.light_color(anim.heat, t0 - anim._t0)
                hue.set_fans([c, c])
            lcd.send_frame(dev, render.to_rgb565(render.render(view, anim)))
            frame += 1
            time.sleep(max(0.0, period - (time.monotonic() - t0)))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--fps", type=float, default=15.0)
    p.add_argument("--temp-override", type=float, default=None,
                   help="force la température (test des couleurs)")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    poller = Poller(a.temp_override)
    poller.start()
    anim = render.Anim()
    anim.step(poller.view.cpu_temp)
    BoardLight(anim).start()
    while True:
        try:
            run(a.fps, poller, anim)
        except KeyboardInterrupt:
            break
        except Exception:
            log.exception("erreur, nouvelle tentative dans 5 s")
            time.sleep(5)


if __name__ == "__main__":
    main()
