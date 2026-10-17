"""Rendu du tableau de bord 240x240 pour l'écran rond du Kraken.

Disposition : icônes LXC et OpenClaw (avec pastille de notifications), grande
température CPU, barre de température, charge CPU et RAM. Un effet de particules
traduit la température : neige quand le CPU est froid, feu quand il chauffe.
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


# --------------------------------------------------------------- particules
BREATH_PERIOD_S = 4.0

# Halo sur le bord de l'écran rond : 0 au centre, 1 sur le bord.
_yy, _xx = np.mgrid[0:SIZE, 0:SIZE]
_R = np.hypot(_xx - CENTER + 0.5, _yy - CENTER + 0.5)
_RING = np.clip((_R - 70) / 50, 0, 1) ** 1.6
_GLOW_SNOW = _RING * (1.0 - 0.6 * _yy / SIZE)   # plus présent en haut
_GLOW_FIRE = _RING * (0.4 + 0.6 * _yy / SIZE)   # plus présent en bas


class Particles:
    """Neige (froid) ou braises (chaud) en « respiration » : halo sur le bord
    et apparition des particules qui gonflent et retombent sur ~4 s.
    L'intensité dépend de l'écart au seuil."""

    def __init__(self):
        self.snow: list[list[float]] = []
        self.fire: list[list[float]] = []
        self.snow_k = self.fire_k = 0.0
        self.breath = 0.0

    def step(self, temp: float | None) -> None:
        snow_k = fire_k = 0.0
        if temp is not None:
            snow_k = min(1.0, max(0.0, (SNOW_BELOW - temp) / 10 + 0.3)) if temp < SNOW_BELOW else 0.0
            fire_k = min(1.0, max(0.0, (temp - FIRE_ABOVE) / 15 + 0.3)) if temp > FIRE_ABOVE else 0.0
        self.snow_k, self.fire_k = snow_k, fire_k
        # 0 -> 1 -> 0, courbe douce (inspiration / expiration)
        b = 0.5 - 0.5 * math.cos(2 * math.pi * time.monotonic() / BREATH_PERIOD_S)
        self.breath = b * b * (3 - 2 * b)
        snow_k *= 0.15 + 0.85 * self.breath
        fire_k *= 0.15 + 0.85 * self.breath

        # neige : [x, y, vitesse, phase, rayon]
        for _ in range(int(snow_k * 2 + random.random() * snow_k * 2)):
            self.snow.append([random.uniform(20, 220), -4.0, random.uniform(0.8, 2.0),
                              random.uniform(0, 6.28), random.choice((1, 1, 2))])
        for p in self.snow:
            p[1] += p[2]
            p[3] += 0.08
            p[0] += math.sin(p[3]) * 0.6
        self.snow = [p for p in self.snow if p[1] < SIZE + 4][-120:]

        # feu : [x, y, vx, vy, vie, vie_max]
        for _ in range(int(fire_k * 5 + random.random() * fire_k * 4)):
            life = random.uniform(18, 34)
            self.fire.append([random.gauss(CENTER, 45), SIZE - 8.0, random.uniform(-0.5, 0.5),
                              random.uniform(-3.2, -1.6), life, life])
        for p in self.fire:
            p[0] += p[2] + random.uniform(-0.4, 0.4)
            p[1] += p[3]
            p[4] -= 1
        self.fire = [p for p in self.fire if p[4] > 0][-220:]

    def background(self) -> Image.Image:
        """Fond noir + halo qui respire (bleu glacé ou rouge braise)."""
        a = np.zeros((SIZE, SIZE, 3), dtype=np.float32)
        lvl = 0.25 + 0.75 * self.breath
        if self.snow_k:
            a += _GLOW_SNOW[..., None] * (np.array((90, 150, 255), np.float32) * self.snow_k * lvl)
        if self.fire_k:
            a += _GLOW_FIRE[..., None] * (np.array((255, 70, 10), np.float32) * self.fire_k * lvl)
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

    def draw(self, d: ImageDraw.ImageDraw) -> None:
        dim = 0.45 + 0.55 * self.breath  # les particules s'éclairent avec le souffle
        for x, y, _, _, r in self.snow:
            d.ellipse((x - r, y - r, x + r, y + r),
                      fill=(int(220 * dim), int(235 * dim), int(255 * dim)))
        for x, y, _, _, life, life_max in self.fire:
            k = life / life_max  # 1 = naissance (jaune), 0 = fin (rouge sombre)
            col = (255, int(60 + 180 * k), int(40 * k)) if k > 0.4 else (int(120 + 300 * k), int(30 * k), 0)
            col = tuple(int(c * dim) for c in col)
            r = 1 + 3 * k
            d.ellipse((x - r, y - r, x + r, y + r), fill=col)


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
