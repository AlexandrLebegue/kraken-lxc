"""Rendu du tableau de bord 240x240 pour l'écran rond du Kraken.

Disposition : icônes LXC et OpenClaw (avec pastille de notifications), grande
température CPU, barre de température, charge CPU et RAM. Un effet de particules
traduit la température : orbes bleutés qui respirent quand le CPU est froid,
orangés quand il chauffe.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SIZE = 240
CENTER = SIZE // 2
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

WHITE = (240, 240, 240)
GREY = (150, 150, 150)
GREEN = (60, 220, 110)
ORANGE = (255, 160, 40)
RED = (240, 60, 50)
BLUE = (40, 140, 255)

# Seuils de l'effet (°C, Tctl du Ryzen) et bornes de la barre
SNOW_BELOW = 45.0
FIRE_ABOVE = 70.0
BAR_MIN, BAR_MAX = 25.0, 90.0


@dataclass
class View:
    cpu_temp: float | None
    cpu_load: float
    ram_used: float
    ram_total: float
    lxc_running: int
    lxc_expected: int
    lxc_ok: bool
    notifications: int


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


F_BIG = _font(FONT_BOLD, 54)
F_UNIT = _font(FONT_BOLD, 18)
F_LABEL = _font(FONT_BOLD, 12)
F_SMALL = _font(FONT_BOLD, 11)
F_BADGE = _font(FONT_BOLD, 10)


def temp_color(t: float) -> tuple[int, int, int]:
    """Bleu (froid) -> gris -> rouge (chaud) sur la plage de la barre."""
    x = min(1.0, max(0.0, (t - BAR_MIN) / (BAR_MAX - BAR_MIN)))
    if x < 0.5:
        k = x / 0.5
        return tuple(int(a + (b - a) * k) for a, b in zip(BLUE, (170, 170, 170)))
    k = (x - 0.5) / 0.5
    return tuple(int(a + (b - a) * k) for a, b in zip((170, 170, 170), RED))


# --------------------------------------------------------------- orbes
# Ronds lumineux et flous qui flottent lentement et « respirent » chacun à leur
# rythme : bleutés quand le CPU est froid, orangés quand il chauffe.
ORB_MAX = 14
_COLD = [(110, 170, 255), (170, 210, 255), (80, 130, 230)]
_HOT = [(255, 130, 40), (255, 80, 30), (255, 180, 70)]


def _sprite(r: float) -> np.ndarray:
    """Disque flou (gaussienne) de rayon visuel r, valeurs 0..1."""
    n = int(r * 2.2) + 1
    y, x = np.mgrid[-n:n + 1, -n:n + 1]
    return np.exp(-(x * x + y * y) / (2 * (r * 0.55) ** 2)).astype(np.float32)


class Particles:
    """Orbes qui flottent et respirent. Leur nombre et leur éclat suivent
    l'écart de température au seuil ; ils apparaissent et disparaissent en fondu."""

    def __init__(self):
        self.orbs: list[dict] = []
        self.kind = None          # "cold" ou "hot"
        self.level = 0.0          # intensité globale, lissée (fondu)
        self._t0 = time.monotonic()

    def _new_orb(self) -> dict:
        a = random.uniform(0, 2 * math.pi)
        d = random.uniform(0, 95)
        speed = random.uniform(0.08, 0.25)
        heading = random.uniform(0, 2 * math.pi)
        return {
            "x": CENTER + d * math.cos(a), "y": CENTER + d * math.sin(a),
            "vx": speed * math.cos(heading), "vy": speed * math.sin(heading),
            "r": random.uniform(9, 22), "period": random.uniform(5.0, 9.0),
            "phase": random.uniform(0, 1), "ci": random.randrange(3), "fade": 0.0,
        }

    def step(self, temp: float | None) -> None:
        cold_k = hot_k = 0.0
        if temp is not None:
            if temp < SNOW_BELOW:
                cold_k = min(1.0, (SNOW_BELOW - temp) / 10 + 0.3)
            elif temp > FIRE_ABOVE:
                hot_k = min(1.0, (temp - FIRE_ABOVE) / 15 + 0.3)
        kind = "cold" if cold_k else "hot" if hot_k else None
        k = cold_k or hot_k
        if kind != self.kind and self.level > 0.02:
            target = 0.0                       # on éteint avant de changer de famille
        else:
            if kind != self.kind:
                self.orbs = []
            self.kind = kind
            target = k
        self.level += (target - self.level) * 0.03
        want = int(round(4 + (ORB_MAX - 4) * k)) if self.kind else 0
        while len(self.orbs) < want:
            self.orbs.append(self._new_orb())
        for i, o in enumerate(self.orbs):
            o["fade"] = min(1.0, o["fade"] + 0.02) if i < want else max(0.0, o["fade"] - 0.02)
            o["x"] += o["vx"]
            o["y"] += o["vy"]
            dx, dy = o["x"] - CENTER, o["y"] - CENTER
            if dx * dx + dy * dy > 100 ** 2:   # reste dans l'écran rond : on rebrousse chemin
                o["vx"], o["vy"] = -o["vx"] + random.uniform(-0.05, 0.05), -o["vy"] + random.uniform(-0.05, 0.05)
        self.orbs = [o for i, o in enumerate(self.orbs) if i < want or o["fade"] > 0]

    def background(self) -> Image.Image:
        a = np.zeros((SIZE, SIZE, 3), dtype=np.float32)
        if self.kind and self.level > 0.005:
            pal = _COLD if self.kind == "cold" else _HOT
            t = time.monotonic() - self._t0
            for o in self.orbs:
                b = 0.5 - 0.5 * math.cos(2 * math.pi * (t / o["period"] + o["phase"]))
                b = b * b * (3 - 2 * b)
                r = o["r"] * (0.65 + 0.35 * b)
                alpha = (0.12 + 0.6 * b) * o["fade"] * self.level
                s = _sprite(r)
                n = s.shape[0] // 2
                x, y = int(o["x"]), int(o["y"])
                x0, y0, x1, y1 = max(0, x - n), max(0, y - n), min(SIZE, x + n + 1), min(SIZE, y + n + 1)
                if x0 >= x1 or y0 >= y1:
                    continue
                sub = s[y0 - (y - n):y1 - (y - n), x0 - (x - n):x1 - (x - n)]
                a[y0:y1, x0:x1] += sub[..., None] * (np.array(pal[o["ci"]], np.float32) * alpha)
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

    def draw(self, d: ImageDraw.ImageDraw) -> None:
        """Tout est déjà dans le fond (conservé pour l'API)."""


# --------------------------------------------------------------- icônes
def _robot(d: ImageDraw.ImageDraw, cx: int, cy: int, col) -> None:
    d.line((cx, cy - 26, cx, cy - 18), fill=col, width=2)
    d.ellipse((cx - 3, cy - 31, cx + 3, cy - 25), outline=col, width=2)
    d.rounded_rectangle((cx - 22, cy - 18, cx + 22, cy + 16), radius=10, outline=col, width=3)
    d.rectangle((cx - 27, cy - 5, cx - 23, cy + 5), fill=col)
    d.rectangle((cx + 23, cy - 5, cx + 27, cy + 5), fill=col)
    d.arc((cx - 14, cy - 8, cx - 4, cy + 2), 200, 340, fill=col, width=2)
    d.arc((cx + 4, cy - 8, cx + 14, cy + 2), 200, 340, fill=col, width=2)
    d.arc((cx - 9, cy - 2, cx + 9, cy + 10), 20, 160, fill=col, width=2)


def _lobster(d: ImageDraw.ImageDraw, cx: int, cy: int, col) -> None:
    # pinces
    for s in (-1, 1):
        px = cx + s * 17
        d.pieslice((px - 9, cy - 32, px + 9, cy - 14), 300 if s > 0 else 120,
                   240 if s > 0 else 60, outline=col, width=2)
        d.line((cx + s * 6, cy - 6, px, cy - 15), fill=col, width=2)
    # antennes
    d.line((cx - 3, cy - 10, cx - 10, cy - 30), fill=col, width=1)
    d.line((cx + 3, cy - 10, cx + 10, cy - 30), fill=col, width=1)
    # corps et queue
    d.ellipse((cx - 8, cy - 12, cx + 8, cy + 8), outline=col, width=2)
    for i in range(3):
        y = cy + 8 + i * 5
        d.arc((cx - 7 + i, y - 3, cx + 7 - i, y + 5), 0, 180, fill=col, width=2)
    d.polygon([(cx, cy + 22), (cx - 8, cy + 30), (cx + 8, cy + 30)], outline=col)
    # pattes
    for i in (-3, 1, 5):
        d.line((cx - 8, cy + i, cx - 14, cy + i + 4), fill=col, width=1)
        d.line((cx + 8, cy + i, cx + 14, cy + i + 4), fill=col, width=1)


def _center_text(d: ImageDraw.ImageDraw, y: int, parts: list[tuple[str, tuple, ImageFont.FreeTypeFont]]) -> None:
    widths = [d.textlength(t, font=f) for t, _, f in parts]
    x = CENTER - sum(widths) / 2
    for (t, c, f), w in zip(parts, widths):
        d.text((x, y), t, fill=c, font=f, stroke_width=2, stroke_fill=(0, 0, 0))
        x += w


# --------------------------------------------------------------- rendu
def render(v: View, particles: Particles) -> Image.Image:
    im = particles.background()
    d = ImageDraw.Draw(im)
    particles.draw(d)

    # icônes
    lx, ox, iy = 80, 160, 52
    _robot(d, lx, iy, WHITE)
    _lobster(d, ox, iy, WHITE)
    if v.notifications:
        n = str(min(v.notifications, 99))
        bx, by = ox + 16, iy + 18
        d.ellipse((bx - 10, by - 10, bx + 10, by + 10), fill=RED)
        w = d.textlength(n, font=F_BADGE)
        d.text((bx - w / 2, by - 6), n, fill=WHITE, font=F_BADGE)

    state = ("OK", GREEN) if v.lxc_ok else (f"{v.lxc_running}/{v.lxc_expected}", ORANGE)
    w1 = d.textlength("LXC: " + state[0], font=F_LABEL)
    d.text((lx - w1 / 2, 86), "LXC: ", fill=WHITE, font=F_LABEL)
    d.text((lx - w1 / 2 + d.textlength("LXC: ", font=F_LABEL), 86), state[0], fill=state[1], font=F_LABEL)
    w2 = d.textlength("OPENCLAW", font=F_LABEL)
    d.text((ox - w2 / 2, 86), "OPENCLAW", fill=WHITE, font=F_LABEL)

    # température
    t = v.cpu_temp
    txt = "--" if t is None else f"{t:.0f}"
    tw = d.textlength(txt, font=F_BIG)
    uw = d.textlength("°C", font=F_UNIT)
    x0 = CENTER - (tw + uw) / 2
    d.text((x0, 102), txt, fill=WHITE, font=F_BIG, stroke_width=2, stroke_fill=(0, 0, 0))
    d.text((x0 + tw + 2, 110), "°C", fill=WHITE, font=F_UNIT)
    _center_text(d, 160, [("CPU TEMP", GREY, F_SMALL)])

    # barre bleu -> rouge avec curseur
    x_a, x_b, y = 52, 188, 179
    for x in range(x_a, x_b):
        c = temp_color(BAR_MIN + (BAR_MAX - BAR_MIN) * (x - x_a) / (x_b - x_a))
        d.line((x, y - 2, x, y + 2), fill=c)
    if t is not None:
        k = min(1.0, max(0.0, (t - BAR_MIN) / (BAR_MAX - BAR_MIN)))
        cx = x_a + k * (x_b - x_a)
        d.ellipse((cx - 5, y - 5, cx + 5, y + 5), fill=WHITE)

    load_col = GREEN if v.cpu_load < 50 else ORANGE if v.cpu_load < 85 else RED
    _center_text(d, 190, [("CPU LOAD: ", WHITE, F_LABEL), (f"{v.cpu_load:.0f}%", load_col, F_LABEL)])
    _center_text(d, 207, [(f"RAM: {v.ram_used:.1f} / {v.ram_total:.0f} GB", WHITE, F_SMALL)])
    return im


def to_rgb565(im: Image.Image) -> bytes:
    """Format attendu par l'écran : RGB565 big-endian (identique à liquidctl)."""
    a = np.asarray(im.convert("RGB"), dtype=np.uint16)
    v = ((a[..., 0] >> 3) << 11) | ((a[..., 1] >> 2) << 5) | (a[..., 2] >> 3)
    return v.astype(">u2").tobytes()
