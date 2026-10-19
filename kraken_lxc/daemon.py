"""Démon kraken-lxc : écran LCD + couleurs selon l'état de l'hôte Proxmox.

- Écran : tableau de bord animé (~15 img/s), relevés rafraîchis toutes les 2 s.
  L'état des LXC est porté par l'icône du robot.
- Ventilateurs + carte mère : même palette que la barre de température
  (bleu/violet froid -> rouge/orange chaud), en respiration lente.
- Extinction programmée des LED (défaut 00:00 -> 07:00) avec fondu de la
  couleur courante ; l'écran LCD reste allumé.

Usage : python -m kraken_lxc.daemon [--fps 15] [--temp-override 30]
        [--lights-off 00:00 | none] [--lights-on 07:00] [--fade 6]
"""
from __future__ import annotations

import argparse
import logging
import threading
import time

from liquidctl import find_liquidctl_devices

from . import lcd, metrics, notify, render
from .hue2 import Hue2, find_kraken
from .schedule import LightSchedule

log = logging.getLogger("kraken-lxc")
FAN_RATE = 3.5  # màj couleur ventilateurs /s : max fiable mesuré (3.75 et 4 ignorés par le Kraken)


def _fusion():
    for dev in find_liquidctl_devices():
        if "Fusion" in dev.description:
            return dev
    return None


class BoardLight(threading.Thread):
    """Carte mère (RGB Fusion, autre périphérique) : ~6 écritures/s, ~33 ms chacune."""

    def __init__(self, anim: render.Anim, sched: LightSchedule):
        super().__init__(daemon=True)
        self.anim = anim
        self.sched = sched

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
                            c = self.sched.apply(render.light_color(self.anim.heat, t0 - self.anim._t0))
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


def run(fps: float, poller: Poller, anim: render.Anim, sched: LightSchedule) -> None:
    """Boucle d'affichage. Relancée après une erreur USB ; les threads (relevés,
    carte mère) sont créés une seule fois dans main() et réutilisés."""
    dev = find_kraken()
    with dev.connect():
        dev.initialize()
        hue = Hue2(dev)
        period = 1.0 / fps
        frame = 0
        next_fan = 0.0
        while True:
            t0 = time.monotonic()
            view = poller.view
            anim.step(view.cpu_temp)
            if t0 >= next_fan:  # ventilateurs : cadence limitée (3/s OK, 4/s ignoré par le Kraken)
                next_fan = t0 + 1.0 / FAN_RATE
                c = sched.apply(render.light_color(anim.heat, t0 - anim._t0))
                hue.set_fans([c, c])
            lcd.send_frame(dev, render.to_rgb565(render.render(view, anim)))
            frame += 1
            time.sleep(max(0.0, period - (time.monotonic() - t0)))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--fps", type=float, default=15.0)
    p.add_argument("--temp-override", type=float, default=None,
                   help="force la température (test des couleurs)")
    p.add_argument("--lights-off", default="00:00",
                   help="heure d'extinction des LED (HH:MM), ou none pour jamais")
    p.add_argument("--lights-on", default="07:00", help="heure de rallumage des LED (HH:MM)")
    p.add_argument("--fade", type=float, default=6.0, help="durée du fondu (s)")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    off = None if a.lights_off.lower() in ("none", "off", "") else a.lights_off
    sched = LightSchedule(off, a.lights_on, a.fade)
    log.info("LED : extinction %s -> %s, fondu %.1f s", off or "jamais", a.lights_on, a.fade)
    poller = Poller(a.temp_override)
    poller.start()
    anim = render.Anim()
    anim.step(poller.view.cpu_temp)
    BoardLight(anim, sched).start()
    while True:
        try:
            run(a.fps, poller, anim, sched)
        except KeyboardInterrupt:
            break
        except Exception:
            log.exception("erreur, nouvelle tentative dans 5 s")
            time.sleep(5)


if __name__ == "__main__":
    main()
