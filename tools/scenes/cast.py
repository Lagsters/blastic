"""The cast of the story scenes as pixel art, for paint.py to pack next to the backdrops.

Every sprite is drawn facing right in palette indices, from layered shapes: each layer is shaded
by a light from the upper right, the side the face turns to, and the silhouette gets a dark
outline. Colours stay off the four
that backdrops redefine (1, 5, 7, 11); 11 marks transparent pixels.

Busts (close-ups) come with a talking mouth and closed eyes as small patches drawn over them;
walkers come with a second step.
"""
import numpy as np
from PIL import Image, ImageDraw

T = 11  # transparent
K, RED, ORANGE, YELLOW, GREEN, BROWN, BLUE, SKIN, WHITE, LIGHT, GREY, DARK = 0, 2, 3, 4, 6, 8, 9, 10, 12, 13, 14, 15
# shadow and light of each colour
SHADE = {SKIN: ORANGE, WHITE: LIGHT, LIGHT: GREY, GREY: DARK, DARK: K, RED: BROWN, ORANGE: RED,
         YELLOW: ORANGE, GREEN: DARK, BLUE: DARK, BROWN: K, K: K}
LIGHTEN = {SKIN: WHITE, RED: ORANGE, ORANGE: YELLOW, YELLOW: WHITE, BLUE: LIGHT, GREY: LIGHT,
           DARK: GREY, BROWN: RED, GREEN: GREEN, LIGHT: WHITE, WHITE: WHITE, K: DARK}


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.img = np.full((h, w), T)
        self.yy, self.xx = np.mgrid[0:h, 0:w]

    def mask_poly(self, pts):
        m = Image.new("1", (self.w, self.h))
        ImageDraw.Draw(m).polygon([tuple(p) for p in pts], fill=1)
        return np.array(m, bool)

    def mask_ellipse(self, cx, cy, rx, ry):
        return ((self.xx - cx) / rx) ** 2 + ((self.yy - cy) / ry) ** 2 <= 1

    def fill(self, mask, col, shade=True, light=True, round_=None):
        """Paint mask in col; the lower left rim in shadow, the upper rim lit.
        round_=(cx,cy,rx,ry) shades as a rounded form instead of along the rim."""
        img = self.img
        if round_:
            cx, cy, rx, ry = round_
            nx, ny = (self.xx - cx) / rx, (self.yy - cy) / ry
            lit = nx * 0.5 + ny * -0.8
            img[mask] = col
            if shade:
                img[mask & (lit < -0.62)] = SHADE[col]
            if light:
                img[mask & (lit > 0.78)] = LIGHTEN[col]
            return
        img[mask] = col
        if shade:
            inner = mask.copy()
            inner[:, 1:] &= mask[:, :-1]
            inner[:-1, :] &= mask[1:, :]
            img[mask & ~inner] = SHADE[col]
        if light:
            top = mask.copy()
            top[1:, :] &= ~mask[:-1, :]
            img[top & (img == col)] = LIGHTEN[col]

    def ellipse(self, cx, cy, rx, ry, col, **kw):
        m = self.mask_ellipse(cx, cy, rx, ry)
        if "round_" not in kw and kw.get("shade", True):
            kw["round_"] = (cx, cy, rx, ry)
        self.fill(m, col, **kw)
        return m

    def poly(self, pts, col, **kw):
        m = self.mask_poly(pts)
        self.fill(m, col, **kw)
        return m

    def rect(self, x0, y0, x1, y1, col, **kw):
        m = (self.xx >= x0) & (self.xx < x1) & (self.yy >= y0) & (self.yy < y1)
        self.fill(m, col, **kw)
        return m

    def px(self, pts, col):
        for x, y in pts:
            if 0 <= x < self.w and 0 <= y < self.h:
                self.img[y, x] = col

    def outline(self):
        o = self.img != T
        edge = np.zeros_like(o)
        edge[1:, :] |= o[:-1, :]
        edge[:-1, :] |= o[1:, :]
        edge[:, 1:] |= o[:, :-1]
        edge[:, :-1] |= o[:, 1:]
        self.img[edge & ~o] = K
        return self.img


# ── faces ────────────────────────────────────────────────────────────────────

def eyes(c, x, y, gap=5, brow=BROWN, lid=False):
    """Two eyes looking right, x,y the left eye's top left."""
    for ex in (x, x + gap):
        if lid:
            c.px([(ex, y + 1), (ex + 1, y + 1), (ex + 2, y + 1)], K)
        else:
            c.px([(ex, y), (ex + 1, y), (ex, y + 1)], WHITE)
            c.px([(ex + 1, y + 1), (ex + 2, y), (ex + 2, y + 1)], K)
        if brow is not None:
            c.px([(ex, y - 2), (ex + 1, y - 2), (ex + 2, y - 2)], brow)


def mouth(c, x, y, w=4, open_=False):
    if open_:
        c.px([(x + i, y) for i in range(w)], K)
        c.px([(x + i, y + 1) for i in range(1, w - 1)], RED)
        c.px([(x + i, y + 2) for i in range(1, w - 1)], K)
    else:
        c.px([(x + i, y) for i in range(w)], RED)
        c.px([(x, y - 1), (x + w - 1, y - 1)], ORANGE)


# ── busts: 36x44, the face turned slightly right ─────────────────────────────

BW, BH = 36, 44


def bust_dratewka(talk=False, blink=False):
    c = Canvas(BW, BH)
    c.poly([(2, 44), (5, 33), (12, 30), (24, 30), (31, 33), (34, 44)], WHITE)  # shirt
    c.poly([(11, 44), (12, 34), (24, 34), (25, 44)], BROWN)                    # apron
    c.rect(13, 30, 15, 35, BROWN, light=False)
    c.rect(22, 30, 24, 35, BROWN, light=False)
    c.rect(15, 25, 22, 31, SKIN, light=False)                                   # neck
    c.ellipse(9, 18, 4, 9, BROWN)                                               # hair at the back
    c.ellipse(19, 17, 9, 10, SKIN)                                              # head
    c.ellipse(10, 18, 2, 3, SKIN)                                               # ear
    c.poly([(9, 12), (12, 6), (22, 5), (28, 9), (27, 12), (20, 10), (13, 13)], BROWN)  # fringe
    c.ellipse(17, 6, 11, 4, RED)                                                # cap
    c.poly([(22, 7), (33, 8), (31, 10), (22, 10)], RED)                         # its peak
    c.px([(23, 3), (24, 2), (25, 1), (26, 0)], WHITE)                           # feather
    eyes(c, 19, 16, lid=blink)
    c.px([(27, 19), (28, 20), (27, 21)], ORANGE)                                # nose
    c.px([(17, 21), (18, 21)], ORANGE)                                          # cheek
    mouth(c, 21, 24, 4, talk)
    return c.outline()


def bust_wanda(talk=False, blink=False):
    c = Canvas(BW, BH)
    c.poly([(1, 44), (4, 34), (12, 31), (24, 31), (32, 34), (35, 44)], WHITE)  # blouse sleeves
    c.poly([(9, 44), (11, 35), (25, 35), (27, 44)], RED)                        # bodice
    c.px([(14 + i * 2, 33) for i in range(5)], RED)                             # corals
    c.px([(15 + i * 2, 34) for i in range(4)], RED)
    c.ellipse(18, 20, 12, 14, YELLOW)                                           # hair
    c.poly([(6, 22), (10, 40), (14, 40), (12, 22)], YELLOW)                     # braid behind
    c.rect(15, 26, 22, 32, SKIN, light=False)
    c.ellipse(19, 18, 8, 10, SKIN)
    c.poly([(10, 12), (14, 7), (24, 6), (28, 11), (24, 10), (16, 12)], YELLOW)  # fringe
    c.poly([(7, 8), (11, 4), (26, 3), (30, 7), (26, 7), (11, 9)], GREEN)        # wreath
    c.px([(10, 6), (15, 4), (20, 3), (25, 4), (29, 6)], RED)
    c.px([(12, 5), (18, 3), (23, 3), (27, 5)], WHITE)
    c.px([(14, 5), (22, 4)], BLUE)
    eyes(c, 19, 16, brow=ORANGE, lid=blink)
    c.px([(19, 15), (24, 15)], K)                                               # lashes
    c.px([(26, 19), (27, 20)], ORANGE)
    c.px([(17, 21), (18, 21), (25, 22)], ORANGE)
    mouth(c, 20, 24, 4, talk)
    return c.outline()


def bust_krak(talk=False, blink=False):
    c = Canvas(BW, BH)
    c.poly([(0, 44), (3, 32), (12, 28), (24, 28), (33, 32), (36, 44)], RED)     # cloak
    c.poly([(3, 34), (10, 29), (26, 29), (33, 34), (26, 35), (10, 35)], WHITE)  # ermine
    c.px([(8, 32), (14, 33), (20, 32), (26, 33), (30, 32)], K)
    c.ellipse(19, 17, 9, 10, SKIN)
    c.poly([(10, 20), (14, 33), (19, 38), (25, 33), (28, 21), (24, 25), (14, 25)], WHITE)  # beard
    c.poly([(13, 22), (24, 22), (26, 25), (11, 25)], WHITE)                     # moustache
    c.poly([(9, 11), (11, 2), (14, 6), (17, 0), (20, 6), (23, 1), (26, 6), (29, 2), (29, 11)], YELLOW)  # crown
    c.px([(13, 8), (19, 8), (25, 8)], RED)
    c.px([(16, 9), (22, 9)], BLUE)
    eyes(c, 18, 15, brow=WHITE, lid=blink)
    c.px([(27, 18), (28, 19), (27, 20)], ORANGE)
    if talk:
        c.px([(18, 26), (19, 26), (20, 26), (21, 26)], K)
        c.px([(19, 27), (20, 27)], RED)
    return c.outline()


def bust_twardowski(talk=False, blink=False):
    c = Canvas(BW, BH)
    c.poly([(0, 44), (3, 32), (12, 29), (24, 29), (33, 32), (36, 44)], BLUE)    # kontusz
    c.poly([(13, 29), (23, 29), (21, 44), (15, 44)], RED)                      # zupan
    c.px([(18, 33), (18, 36), (18, 39), (18, 42)], YELLOW)                      # buttons
    c.rect(15, 25, 22, 31, SKIN, light=False)
    c.ellipse(19, 18, 8, 10, SKIN)
    c.poly([(17, 23), (8, 27), (11, 24), (17, 21), (24, 21), (30, 24), (32, 28), (24, 23)], K)  # moustache
    c.poly([(19, 26), (23, 26), (21, 32)], K)                                   # goatee
    c.poly([(9, 13), (10, 1), (28, 1), (29, 13)], BROWN)                        # fur kolpak
    c.poly([(11, 3), (14, -2), (26, -2), (27, 3)], RED)                         # its crown
    c.px([(26, 1), (27, 0), (28, -1)], YELLOW)
    c.px([(25, 4), (26, 3), (27, 2), (28, 1), (29, 0)], WHITE)                  # heron feather
    eyes(c, 18, 16, brow=K, lid=blink)
    c.px([(17, 14), (23, 14)], K)                                               # sly brows
    c.px([(27, 19), (28, 20), (27, 21)], ORANGE)
    if talk:
        c.px([(19, 24), (20, 24), (21, 24), (22, 24)], RED)
    return c.outline()


def bust_devil(talk=False, blink=False):
    c = Canvas(BW, BH)
    c.poly([(0, 44), (3, 32), (12, 29), (24, 29), (33, 32), (36, 44)], DARK)    # black kontusz
    c.poly([(12, 29), (24, 29), (22, 44), (14, 44)], RED)                      # red lining
    c.rect(15, 25, 22, 31, RED, light=False)
    c.ellipse(19, 18, 9, 10, RED)                                               # red face
    c.poly([(10, 11), (6, 2), (8, 0), (13, 8)], DARK)                           # horns
    c.poly([(24, 9), (28, 0), (30, 2), (28, 11)], DARK)
    c.ellipse(19, 9, 9, 3, K, shade=False, light=False)                         # slick hair
    c.poly([(16, 23), (6, 21), (9, 24), (16, 25), (24, 25), (32, 23), (33, 19), (25, 23)], K)  # moustache
    for ex in (18, 24):
        c.px([(ex, 16), (ex + 1, 16), (ex + 2, 16)], YELLOW if not blink else K)
        if not blink:
            c.px([(ex + 1, 17)], K)
        c.px([(ex - 1, 14), (ex, 13), (ex + 2, 14)], K)
    c.px([(28, 19), (29, 20)], BROWN)
    if talk:
        c.px([(19, 26), (20, 26), (21, 26), (22, 26)], K)
        c.px([(20, 27), (21, 27)], WHITE)
    return c.outline()


def bust_jaga(talk=False, blink=False):
    c = Canvas(BW, BH)
    c.poly([(0, 44), (4, 30), (14, 26), (26, 27), (34, 33), (36, 44)], GREY)    # shawl
    c.ellipse(18, 18, 13, 14, RED)                                              # headscarf
    c.px([(10, 10), (16, 7), (22, 8), (27, 12), (8, 18), (29, 20), (12, 26)], WHITE)
    c.ellipse(20, 20, 7, 9, SKIN)
    c.poly([(13, 14), (16, 12), (14, 22)], LIGHT)                               # grey hair
    c.poly([(26, 19), (33, 25), (31, 27), (26, 25)], SKIN)                      # nose
    c.px([(31, 26)], ORANGE)
    c.px([(18, 25), (19, 26), (20, 26), (21, 26)], ORANGE)                      # wrinkles
    for ex in (19, 24):
        c.px([(ex, 18), (ex + 1, 18)], K if blink else WHITE)
        if not blink:
            c.px([(ex + 1, 18)], K)
        c.px([(ex - 1, 16), (ex, 16), (ex + 1, 16)], LIGHT)
    if talk:
        c.px([(21, 28), (22, 28), (23, 28), (24, 28)], K)
        c.px([(22, 29)], WHITE)
    else:
        c.px([(21, 28), (22, 28), (23, 28)], BROWN)
    return c.outline()


# ── full figures: about 18x34, feet on the bottom row ────────────────────────

def figure_dratewka(step=0):
    c = Canvas(20, 34)
    lx, rx = 7 - step, 11 + step
    c.rect(lx, 25, lx + 3, 32, DARK, light=False)
    c.rect(rx, 25, rx + 3, 32, DARK, light=False)
    c.rect(lx - 1, 32, lx + 3, 34, K)
    c.rect(rx, 32, rx + 4, 34, K)
    c.poly([(5, 26), (6, 15), (14, 15), (15, 26)], WHITE)
    c.poly([(6, 27), (7, 18), (13, 18), (14, 27)], BROWN)
    c.ellipse(10, 10, 5, 5, SKIN)
    c.ellipse(6, 10, 2, 4, BROWN, light=False)
    c.ellipse(9, 5, 6, 2, RED)
    c.poly([(12, 5), (18, 6), (12, 7)], RED, light=False)
    c.px([(11, 9), (13, 9)], K)
    c.px([(14, 11)], ORANGE)
    c.px([(11, 13), (12, 13)], RED)
    # the sheep under his arm
    c.ellipse(15, 20, 4, 3, WHITE)
    c.rect(18, 19, 20, 22, K)
    return c.outline()


def figure_wanda(step=0):
    c = Canvas(20, 34)
    c.rect(7 - step, 31, 10 - step, 34, K)
    c.rect(11 + step, 31, 14 + step, 34, K)
    c.poly([(3, 32), (7, 18), (13, 18), (17, 32)], RED)
    c.rect(4, 31, 17, 32, WHITE, shade=False)
    c.poly([(5, 20), (6, 14), (14, 14), (15, 20)], WHITE)
    c.ellipse(10, 9, 6, 6, YELLOW)
    c.poly([(4, 10), (6, 24), (8, 24), (7, 10)], YELLOW, light=False)
    c.ellipse(11, 9, 4, 5, SKIN)
    c.rect(5, 3, 16, 5, GREEN, light=False)
    c.px([(6, 3), (9, 2), (12, 2), (15, 3)], RED)
    c.px([(12, 8), (14, 8)], K)
    c.px([(12, 12), (13, 12)], RED)
    return c.outline()


def figure_krak(step=0):
    c = Canvas(20, 34)
    c.poly([(2, 34), (6, 14), (14, 14), (18, 34)], RED)
    c.rect(2, 32, 18, 34, WHITE, shade=False)
    c.rect(9, 15, 11, 32, WHITE, shade=False)
    c.ellipse(10, 9, 5, 5, SKIN)
    c.poly([(5, 10), (8, 19), (12, 20), (15, 10), (12, 13), (8, 13)], WHITE)
    c.poly([(5, 5), (6, 0), (8, 3), (10, 0), (12, 3), (14, 0), (15, 5)], YELLOW)
    c.px([(11, 8), (13, 8)], K)
    return c.outline()


def figure_twardowski(step=0):
    c = Canvas(20, 34)
    c.rect(6 - step, 30, 9 - step, 34, K)
    c.rect(11 + step, 30, 14 + step, 34, K)
    c.poly([(3, 31), (6, 14), (14, 14), (17, 31)], BLUE)
    c.poly([(8, 15), (12, 15), (11, 31), (9, 31)], RED, light=False)
    c.rect(5, 21, 15, 23, YELLOW, light=False)
    c.ellipse(10, 9, 4, 5, SKIN)
    c.poly([(9, 12), (4, 13), (9, 11), (13, 11), (17, 13), (13, 12)], K)
    c.rect(6, 1, 15, 6, BROWN)
    c.px([(14, 0), (15, -1), (16, 0)], WHITE)
    c.px([(11, 8), (13, 8)], K)
    return c.outline()


def figure_devil(step=0):
    c = Canvas(22, 34)
    c.rect(7 - step, 30, 10 - step, 34, K)
    c.rect(12 + step, 30, 15 + step, 34, K)
    c.poly([(1, 26), (0, 20), (2, 18), (3, 24), (6, 27)], RED, light=False)      # tail
    c.poly([(4, 31), (7, 14), (15, 14), (18, 31)], DARK)
    c.poly([(9, 15), (13, 15), (12, 31), (10, 31)], RED, light=False)
    c.ellipse(11, 9, 5, 5, RED)
    c.poly([(7, 6), (5, 0), (8, 4)], K)
    c.poly([(14, 4), (17, 0), (16, 6)], K)
    c.poly([(9, 12), (4, 11), (9, 11), (14, 11), (19, 10), (14, 12)], K)
    c.px([(12, 8), (14, 8)], YELLOW)
    return c.outline()


def figure_jaga(step=0):
    c = Canvas(22, 32)
    c.rect(3, 6, 4, 32, BROWN, shade=False, light=False)                        # broom
    c.poly([(0, 32), (3, 24), (5, 24), (8, 32)], YELLOW, light=False)
    c.poly([(5, 31), (8, 14), (16, 12), (19, 31)], GREY)
    c.ellipse(13, 9, 6, 6, RED)
    c.ellipse(14, 10, 4, 4, SKIN)
    c.poly([(17, 9), (21, 13), (17, 12)], SKIN, light=False)
    c.px([(15, 9)], K)
    return c.outline()


def figure_dwarf(step=0):
    c = Canvas(14, 22)
    c.rect(4 - step, 19, 6 - step, 22, K)
    c.rect(8 + step, 19, 10 + step, 22, K)
    c.poly([(2, 20), (4, 12), (10, 12), (12, 20)], BLUE)
    c.ellipse(7, 10, 3, 3, SKIN)
    c.poly([(4, 11), (7, 18), (10, 11)], WHITE)
    c.poly([(3, 8), (7, 0), (11, 8)], RED)
    c.px([(8, 9)], K)
    return c.outline()


def figure_rooster(step=0):
    c = Canvas(24, 22)
    c.poly([(0, 2), (6, 10), (8, 16), (2, 14)], GREEN)                          # tail
    c.poly([(1, 4), (7, 12), (3, 9)], BLUE, light=False)
    c.ellipse(11, 13, 7, 5, ORANGE)
    c.ellipse(17, 7, 3, 4, ORANGE)
    c.poly([(16, 2), (17, 0), (18, 2), (19, 0), (20, 3)], RED, light=False)
    c.poly([(20, 7), (24, 8), (20, 9)], YELLOW, light=False)
    c.px([(19, 11), (19, 12)], RED)
    c.px([(18, 6)], K)
    c.rect(10, 17, 11, 22, YELLOW, shade=False, light=False)
    c.rect(14, 17, 15, 22, YELLOW, shade=False, light=False)
    return c.outline()


def figure_dragon(step=0):
    c = Canvas(60, 46)
    flap = [0, 6][step]
    c.poly([(18, 22), (8, 2 + flap), (30, 14 + flap // 2), (34, 22)], DARK)     # far wing
    c.poly([(0, 34), (12, 30), (20, 34), (8, 38)], RED)                         # tail
    c.ellipse(24, 32, 12, 9, RED)
    c.ellipse(26, 35, 7, 5, ORANGE)
    c.rect(16, 38, 21, 46, RED)
    c.rect(28, 38, 33, 46, RED)
    c.poly([(32, 28), (38, 14), (44, 16), (38, 30)], RED)                       # neck
    c.ellipse(46, 13, 7, 6, RED)
    c.poly([(48, 10), (60, 12), (59, 17), (48, 18)], RED)                       # snout
    c.poly([(42, 8), (44, 0), (46, 8)], LIGHT)                                  # horn
    c.px([(47, 11), (48, 11)], YELLOW)
    c.px([(48, 12)], K)
    c.px([(57, 13)], K)
    c.poly([(22, 24), (10, 6 + flap), (36, 18 + flap // 2), (34, 26)], RED)     # near wing
    return c.outline()


def figure_sheep(step=0):
    c = Canvas(12, 9)
    c.ellipse(5, 4, 5, 3, WHITE)
    c.rect(9, 2, 12, 6, K)
    c.rect(2, 6, 3, 9, K)
    c.rect(7, 6, 8, 9, K)
    return c.outline()


BUSTS = ["dratewka", "wanda", "krak", "twardowski", "devil", "jaga"]
FIGURES = ["dratewka", "wanda", "krak", "twardowski", "devil", "jaga", "dwarf", "rooster", "dragon", "sheep"]
WALKERS = ["dratewka", "wanda", "twardowski", "devil", "dwarf", "dragon"]


def patch(full, base):
    """The smallest box where full differs from base: (x, y, pixels)."""
    diff = full != base
    ys, xs = np.nonzero(diff)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    return int(x0), int(y0), full[y0:y1, x0:x1]


def sprites():
    """name -> (ox, oy, pixels); the talk/blink patches sit at their offset over the bust."""
    out = {}
    for n in BUSTS:
        f = globals()["bust_" + n]
        base = f()
        out["bust_" + n] = (0, 0, base)
        out["talk_" + n] = patch(f(talk=True), base)
        out["blink_" + n] = patch(f(blink=True), base)
    for n in FIGURES:
        f = globals()["figure_" + n]
        out[n] = (0, 0, f())
        if n in WALKERS:
            out[n + "_step"] = (0, 0, f(1))
    return out
