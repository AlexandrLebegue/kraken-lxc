"""Rendu du tableau de bord 240x240 pour l'écran rond du Kraken.

Disposition : robot (état des LXC : content, ou triste avec un « ! » rouge),
homard OpenClaw (pastille de notifications), grande température CPU, barre de
température animée (bleu/violet froid -> rouge/orange chaud), charge CPU et RAM.
"""
from __future__ import annotations

import math
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

# Bornes de la barre de température (°C, Tctl du Ryzen)
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


# --------------------------------------------------------------- barre animée
# Barre de température « vivante » : un plasma qui grouille. Bleu / violet quand
# le CPU est froid ; le rouge / orange gagne du terrain à mesure qu'il chauffe,
# jusqu'à occuper toute la barre.
BAR_X, BAR_Y, BAR_W, BAR_H = 50, 177, 140, 12
_bx, _by = np.meshgrid(np.arange(BAR_W, dtype=np.float32), np.arange(BAR_H, dtype=np.float32))
# masque à bouts arrondis
_cap = BAR_H / 2
_dxc = np.maximum(0, np.maximum(_cap - _bx - 0.5, _bx + 0.5 - (BAR_W - _cap)))
_BAR_MASK = np.clip(_cap + 0.5 - np.hypot(_dxc, _by + 0.5 - _cap), 0, 1)
_rng = np.random.default_rng(7)
_SEED = _rng.random((BAR_H, BAR_W), dtype=np.float32)   # grain fixe, décalé dans le temps
_C_BLUE = np.array((40, 90, 255), np.float32)
_C_VIOLET = np.array((150, 50, 255), np.float32)
_C_RED = np.array((255, 35, 20), np.float32)
_C_ORANGE = np.array((255, 150, 20), np.float32)


class Anim:
    """État des animations (temps, température lissée)."""

    def __init__(self):
        self._t0 = time.monotonic()
        self.heat = None   # fraction de température lissée, 0 (froid) .. 1 (chaud)

    def step(self, temp: float | None) -> None:
        f = 0.5 if temp is None else min(1.0, max(0.0, (temp - BAR_MIN) / (BAR_MAX - BAR_MIN)))
        self.heat = f if self.heat is None else self.heat + (f - self.heat) * 0.05

    def bar(self) -> np.ndarray:
        """Pixels RGB (BAR_H x BAR_W x 3, float) de la barre animée."""
        t = time.monotonic() - self._t0
        x, y = _bx, _by
        # deux champs de plasma : couleur à l'intérieur d'une famille, et frontière chaud/froid
        p = (np.sin(x * 0.13 + t * 2.1) + np.sin(y * 0.9 - t * 1.7 + x * 0.05)
             + np.sin((x * 0.07 - y * 0.4) + t * 2.9)) / 3
        q = (np.sin(x * 0.09 - t * 1.3) + np.sin(x * 0.21 + y * 0.6 + t * 2.3)) / 4 + 0.5
        p = 0.5 + 0.5 * p
        grain = np.roll(_SEED, int(t * 24) % BAR_W, axis=1)
        p = np.clip(p * 0.85 + grain * 0.15, 0, 1)[..., None]
        # proportion de pixels « chauds » : 0 sous BAR_MIN, tout au-dessus de BAR_MAX
        h = self.heat * 1.2 - 0.1
        hot = np.clip((h - q) * 5 + 0.5, 0, 1)[..., None]
        cold_col = _C_BLUE * (1 - p) + _C_VIOLET * p
        hot_col = _C_RED * (1 - p) + _C_ORANGE * p
        col = cold_col * (1 - hot) + hot_col * hot
        shimmer = (0.7 + 0.3 * np.sin(x * 0.5 + y * 1.3 - t * 6.0) * grain)[..., None]
        return col * shimmer * _BAR_MASK[..., None]


# --------------------------------------------------------------- icônes
def _robot(d: ImageDraw.ImageDraw, cx: int, cy: int, col, happy: bool = True) -> None:
    d.line((cx, cy - 26, cx, cy - 18), fill=col, width=2)
    d.ellipse((cx - 3, cy - 31, cx + 3, cy - 25), outline=col, width=2)
    d.rounded_rectangle((cx - 22, cy - 18, cx + 22, cy + 16), radius=10, outline=col, width=3)
    d.rectangle((cx - 27, cy - 5, cx - 23, cy + 5), fill=col)
    d.rectangle((cx + 23, cy - 5, cx + 27, cy + 5), fill=col)
    if happy:  # yeux plissés et sourire
        d.arc((cx - 14, cy - 8, cx - 4, cy + 2), 200, 340, fill=col, width=2)
        d.arc((cx + 4, cy - 8, cx + 14, cy + 2), 200, 340, fill=col, width=2)
        d.arc((cx - 9, cy - 2, cx + 9, cy + 10), 20, 160, fill=col, width=2)
    else:      # sourcils tombants, yeux ronds et bouche à l'envers
        d.line((cx - 15, cy - 6, cx - 6, cy - 10), fill=col, width=2)
        d.line((cx + 15, cy - 6, cx + 6, cy - 10), fill=col, width=2)
        d.ellipse((cx - 12, cy - 4, cx - 7, cy + 1), fill=col)
        d.ellipse((cx + 7, cy - 4, cx + 12, cy + 1), fill=col)
        d.arc((cx - 9, cy + 5, cx + 9, cy + 15), 200, 340, fill=col, width=2)


def _lobster(d: ImageDraw.ImageDraw, cx: int, cy: int, col) -> None:
    # pinces
    for s in (-1, 1):
        px = cx + s * 17
        d.pieslice((px - 9, cy - 32, px + 9, cy - 14), 300, 240, outline=col, width=2)
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
def _badge(d: ImageDraw.ImageDraw, x: int, y: int, text: str) -> None:
    d.ellipse((x - 10, y - 10, x + 10, y + 10), fill=RED)
    w = d.textlength(text, font=F_BADGE)
    d.text((x - w / 2, y - 6), text, fill=WHITE, font=F_BADGE)


def render(v: View, anim: Anim) -> Image.Image:
    im = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    d = ImageDraw.Draw(im)

    # icônes : robot = état des LXC, homard = notifications OpenClaw
    lx, ox, iy = 80, 160, 56
    _robot(d, lx, iy, WHITE, happy=v.lxc_ok)
    if not v.lxc_ok:
        _badge(d, lx + 20, iy + 18, "!")
    _lobster(d, ox, iy, WHITE)
    if v.notifications:
        _badge(d, ox + 16, iy + 18, str(min(v.notifications, 99)))
    w2 = d.textlength("OPENCLAW", font=F_LABEL)
    d.text((ox - w2 / 2, 90), "OPENCLAW", fill=WHITE, font=F_LABEL)

    # température
    t = v.cpu_temp
    txt = "--" if t is None else f"{t:.0f}"
    tw = d.textlength(txt, font=F_BIG)
    uw = d.textlength("°C", font=F_UNIT)
    x0 = CENTER - (tw + uw) / 2
    d.text((x0, 102), txt, fill=WHITE, font=F_BIG, stroke_width=2, stroke_fill=(0, 0, 0))
    d.text((x0 + tw + 2, 110), "°C", fill=WHITE, font=F_UNIT)
    _center_text(d, 161, [("CPU TEMP", GREY, F_SMALL)])

    # barre de température animée
    a = np.asarray(im, dtype=np.float32).copy()
    zone = a[BAR_Y:BAR_Y + BAR_H, BAR_X:BAR_X + BAR_W]
    m = _BAR_MASK[..., None]
    a[BAR_Y:BAR_Y + BAR_H, BAR_X:BAR_X + BAR_W] = zone * (1 - m) + anim.bar()
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)

    load_col = GREEN if v.cpu_load < 50 else ORANGE if v.cpu_load < 85 else RED
    _center_text(d, 194, [("CPU LOAD: ", WHITE, F_LABEL), (f"{v.cpu_load:.0f}%", load_col, F_LABEL)])
    _center_text(d, 211, [(f"RAM: {v.ram_used:.1f} / {v.ram_total:.0f} GB", WHITE, F_SMALL)])
    return im


def to_rgb565(im: Image.Image) -> bytes:
    """Format attendu par l'écran : RGB565 big-endian (identique à liquidctl)."""
    a = np.asarray(im.convert("RGB"), dtype=np.uint16)
    v = ((a[..., 0] >> 3) << 11) | ((a[..., 1] >> 2) << 5) | (a[..., 2] >> 3)
    return v.astype(">u2").tobytes()
