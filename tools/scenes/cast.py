"""The cast of the story scenes as pixel art, for paint.py to pack next to the backdrops.

Every sprite is drawn facing right in palette indices, from layered shapes: each layer is shaded
by a light from the upper right, the side the face turns to, and the silhouette gets a dark
outline. Colours stay off the four
that backdrops redefine (1, 5, 7, 11); 11 marks transparent pixels.

Busts (close-ups) come with a talking mouth and closed eyes as small patches drawn over them;
walkers with the two moments of a step (_a, _b), the dragon with its wings raised and lowered
(_a, _b) and its jaws open (_roar).
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


# pixels per design unit: designs are written once, drawn at 2 for close and middle shots and
# at 1 for far ones, so a sprite always shows on screen pixel for pixel
RES = 2


class Canvas:
    def __init__(self, w, h):
        self.s = RES
        self.w, self.h = w * RES, h * RES
        self.img = np.full((self.h, self.w), T)
        fy, fx = np.mgrid[0:self.h, 0:self.w]
        self.yy, self.xx = (fy + 0.5) / RES - 0.5, (fx + 0.5) / RES - 0.5

    def mask_poly(self, pts):
        m = Image.new("1", (self.w, self.h))
        ImageDraw.Draw(m).polygon([(x * self.s, y * self.s) for x, y in pts], fill=1)
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
        k = self.s
        if shade:
            inner = mask.copy()
            inner[:, k:] &= mask[:, :-k]
            inner[:-k, :] &= mask[k:, :]
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
        """Design pixels: a block of RES x RES."""
        k = self.s
        for x, y in pts:
            if 0 <= x * k < self.w and 0 <= y * k < self.h:
                self.img[y * k:(y + 1) * k, x * k:(x + 1) * k] = col

    def fine(self, pts, col):
        """Screen pixels, for details only a close sprite has (none at RES 1)."""
        if self.s < 2:
            return
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

def eyes(c, x, y, gap=5, brow=BROWN, lid=False, iris=BLUE):
    """Two eyes looking right, x,y the left eye's top left (design units)."""
    for ex in (x, x + gap):
        if c.s < 2:
            if lid:
                c.px([(ex, y + 1), (ex + 1, y + 1), (ex + 2, y + 1)], K)
            else:
                c.px([(ex, y), (ex + 1, y), (ex, y + 1)], WHITE)
                c.px([(ex + 1, y + 1), (ex + 2, y), (ex + 2, y + 1)], K)
            if brow is not None:
                c.px([(ex, y - 2), (ex + 1, y - 2), (ex + 2, y - 2)], brow)
            continue
        X, Y = ex * 2, y * 2
        if lid:
            c.fine([(X + i, Y + 2) for i in range(5)] + [(X + 1, Y + 3), (X + 3, Y + 3)], K)
        else:
            c.fine([(X + i, Y) for i in range(5)], K)                          # upper lid
            c.fine([(X + i, Y + 1) for i in range(5)] + [(X + i, Y + 2) for i in range(5)], WHITE)
            c.fine([(X + 2, Y + 1), (X + 3, Y + 1), (X + 2, Y + 2), (X + 3, Y + 2), (X + 2, Y + 3), (X + 3, Y + 3)], iris)
            c.fine([(X + 3, Y + 2)], K)                                         # pupil
            c.fine([(X + 2, Y + 1)], WHITE)                                     # glint
            c.fine([(X + 4, Y + 1)], K)
        if brow is not None:
            c.fine([(X, Y - 2), (X + 1, Y - 3), (X + 2, Y - 3), (X + 3, Y - 3), (X + 4, Y - 2)], brow)


def mouth(c, x, y, w=4, open_=False):
    if c.s < 2:
        if open_:
            c.px([(x + i, y) for i in range(w)], K)
            c.px([(x + i, y + 1) for i in range(1, w - 1)], RED)
            c.px([(x + i, y + 2) for i in range(1, w - 1)], K)
        else:
            c.px([(x + i, y) for i in range(w)], RED)
            c.px([(x, y - 1), (x + w - 1, y - 1)], ORANGE)
        return
    X, Y, L = x * 2, y * 2, w * 2
    if open_:
        c.fine([(X + i, Y) for i in range(1, L - 1)] + [(X, Y + 1), (X + L - 1, Y + 1)], K)
        c.fine([(X + i, Y + 1) for i in range(1, L - 1)], WHITE)                # teeth
        c.fine([(X + i, Y + 2) for i in range(1, L - 1)] + [(X + i, Y + 3) for i in range(2, L - 2)], K)
        c.fine([(X + i, Y + 3) for i in range(3, L - 3)], RED)                  # tongue
        c.fine([(X + i, Y + 4) for i in range(2, L - 2)], BROWN)
    else:
        c.fine([(X + i, Y) for i in range(1, L - 1)], BROWN)
        c.fine([(X, Y - 1), (X + L - 1, Y - 1)], BROWN)                        # smiling corners
        c.fine([(X + i, Y + 1) for i in range(2, L - 2)], RED)
        c.fine([(X + i, Y + 2) for i in range(3, L - 3)], ORANGE)


def hair_strands(c, mask, col):
    """Fine strands across a hair shape, every fourth column a shade darker."""
    if c.s < 2:
        return
    fx = np.arange(c.w)[None, :]
    fy = np.arange(c.h)[:, None]
    strand = mask & (((fx + fy // 3) % 4) == 0) & (fy % 5 != 0)
    c.img[strand & (c.img == col)] = SHADE[col]


# ── busts: 36x44, the face turned slightly right ─────────────────────────────

BW, BH = 36, 44


def bust_dratewka(talk=False, blink=False):
    c = Canvas(BW, BH)
    c.poly([(2, 44), (5, 33), (12, 30), (24, 30), (31, 33), (34, 44)], WHITE)  # shirt
    c.poly([(11, 44), (12, 34), (24, 34), (25, 44)], BROWN)                    # apron
    c.rect(13, 30, 15, 35, BROWN, light=False)
    c.rect(22, 30, 24, 35, BROWN, light=False)
    c.rect(15, 25, 22, 31, SKIN, light=False)                                   # neck
    back = c.ellipse(9, 18, 4, 9, BROWN)                                        # hair at the back
    hair_strands(c, back, BROWN)
    c.ellipse(19, 17, 9, 10, SKIN)                                              # head
    c.ellipse(10, 18, 2, 3, SKIN)                                               # ear
    c.fine([(19, 34), (20, 35), (19, 36)], ORANGE)
    fringe = c.poly([(9, 12), (12, 6), (22, 5), (28, 9), (27, 12), (20, 10), (13, 13)], BROWN)  # fringe
    hair_strands(c, fringe, BROWN)
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
    hair = c.ellipse(18, 20, 12, 14, YELLOW)                                    # hair
    braid = c.poly([(6, 22), (10, 40), (14, 40), (12, 22)], YELLOW)             # braid behind
    hair_strands(c, hair | braid, YELLOW)
    c.rect(15, 26, 22, 32, SKIN, light=False)
    c.ellipse(19, 18, 8, 10, SKIN)
    hair_strands(c, c.poly([(10, 12), (14, 7), (24, 6), (28, 11), (24, 10), (16, 12)], YELLOW), YELLOW)  # fringe
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
    hair_strands(c, c.poly([(10, 20), (14, 33), (19, 38), (25, 33), (28, 21), (24, 25), (14, 25)], WHITE), WHITE)  # beard
    c.poly([(13, 22), (24, 22), (26, 25), (11, 25)], WHITE)                     # moustache
    c.poly([(9, 11), (11, 2), (14, 6), (17, 0), (20, 6), (23, 1), (26, 6), (29, 2), (29, 11)], YELLOW)  # crown
    c.px([(13, 8), (19, 8), (25, 8)], RED)
    c.px([(16, 9), (22, 9)], BLUE)
    eyes(c, 18, 15, brow=WHITE, lid=blink)
    c.px([(27, 18), (28, 19), (27, 20)], ORANGE)
    if talk:
        mouth(c, 17, 25, 4, True)
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
    eyes(c, 18, 16, brow=K, lid=blink, iris=BROWN)
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


# ── full figures: about 20x34, feet on the bottom row ────────────────────────
# pose 0 stands, 1 is the stride of a step (feet apart), 2 its passing moment (feet together,
# the back foot lifted); a walk alternates 1 and 2, and blastic.lua lifts the body on 2

def legs(c, cx, hip, foot, pose, col, shoe=K, w=3):
    """Two legs from hip down to the soles at row foot, facing right."""
    if pose == 1:
        c.poly([(cx - 2, hip), (cx + 1, hip), (cx - 2, foot), (cx - 5, foot)], col, light=False)
        c.poly([(cx - 1, hip), (cx + 2, hip), (cx + 6, foot), (cx + 3, foot)], col, light=False)
        c.rect(cx - 6, foot, cx - 1, foot + 2, shoe)
        c.rect(cx + 3, foot, cx + 8, foot + 2, shoe)
    elif pose == 2:
        c.rect(cx - 2, hip, cx - 2 + w, foot - 2, col, light=False)
        c.rect(cx - 4, foot - 2, cx + 1, foot, shoe)
        c.rect(cx, hip, cx + w, foot, col, light=False)
        c.rect(cx, foot, cx + 5, foot + 2, shoe)
    else:
        c.rect(cx - 3, hip, cx - 3 + w, foot, col, light=False)
        c.rect(cx + 1, hip, cx + 1 + w, foot, col, light=False)
        c.rect(cx - 4, foot, cx, foot + 2, shoe)
        c.rect(cx + 1, foot, cx + 5, foot + 2, shoe)


def figure_dratewka(pose=0):
    c = Canvas(22, 34)
    legs(c, 10, 25, 32, pose, DARK)
    c.poly([(5, 26), (6, 15), (14, 15), (15, 26)], WHITE)
    c.poly([(6, 27), (7, 18), (13, 18), (14, 27)], BROWN)
    c.ellipse(10, 10, 5, 5, SKIN)
    c.ellipse(6, 10, 2, 4, BROWN, light=False)
    c.ellipse(9, 5, 6, 2, RED)
    c.poly([(12, 5), (18, 6), (12, 7)], RED, light=False)
    c.px([(11, 9), (13, 9)], K)
    c.px([(14, 11)], ORANGE)
    c.px([(11, 13), (12, 13)], RED)
    c.poly([(13, 16), (16, 23), (14, 24), (12, 18)], WHITE, light=False)
    c.ellipse(15, 24, 1.5, 1.5, SKIN, shade=False)
    return c.outline()


def figure_wanda(pose=0):
    c = Canvas(22, 34)
    legs(c, 10, 30, 32, pose, K)
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


def figure_krak(pose=0):
    c = Canvas(20, 34)
    c.poly([(2, 34), (6, 14), (14, 14), (18, 34)], RED)
    c.rect(2, 32, 18, 34, WHITE, shade=False)
    c.rect(9, 15, 11, 32, WHITE, shade=False)
    c.ellipse(10, 9, 5, 5, SKIN)
    c.poly([(5, 10), (8, 19), (12, 20), (15, 10), (12, 13), (8, 13)], WHITE)
    c.poly([(5, 5), (6, 0), (8, 3), (10, 0), (12, 3), (14, 0), (15, 5)], YELLOW)
    c.px([(11, 8), (13, 8)], K)
    return c.outline()


def figure_twardowski(pose=0):
    c = Canvas(22, 34)
    legs(c, 10, 28, 32, pose, K)
    c.poly([(3, 31), (6, 14), (14, 14), (17, 31)], BLUE)
    c.poly([(8, 15), (12, 15), (11, 31), (9, 31)], RED, light=False)
    c.rect(5, 21, 15, 23, YELLOW, light=False)
    c.ellipse(10, 9, 4, 5, SKIN)
    c.poly([(9, 12), (4, 13), (9, 11), (13, 11), (17, 13), (13, 12)], K)
    c.rect(6, 1, 15, 6, BROWN)
    c.px([(14, 0), (15, -1), (16, 0)], WHITE)
    c.px([(11, 8), (13, 8)], K)
    return c.outline()


def figure_devil(pose=0):
    c = Canvas(24, 34)
    legs(c, 11, 28, 32, pose, K, K)
    c.poly([(1, 26), (0, 20), (2, 18), (3, 24), (6, 27)], RED, light=False)      # tail
    c.poly([(4, 31), (7, 14), (15, 14), (18, 31)], DARK)
    c.poly([(9, 15), (13, 15), (12, 31), (10, 31)], RED, light=False)
    c.ellipse(11, 9, 5, 5, RED)
    c.poly([(7, 6), (5, 0), (8, 4)], K)
    c.poly([(14, 4), (17, 0), (16, 6)], K)
    c.poly([(9, 12), (4, 11), (9, 11), (14, 11), (19, 10), (14, 12)], K)
    c.px([(12, 8), (14, 8)], YELLOW)
    return c.outline()


def figure_dwarf(pose=0):
    c = Canvas(16, 22)
    legs(c, 7, 17, 20, pose, DARK, K, 2)
    c.poly([(2, 18), (4, 11), (10, 11), (12, 18)], BLUE)
    c.ellipse(7, 9, 3, 3, SKIN)
    c.poly([(4, 10), (7, 17), (10, 10)], WHITE)
    c.poly([(3, 7), (7, -1), (11, 7)], RED)
    c.px([(8, 8)], K)
    return c.outline()


def dragon_wing(c, sx, sy, tips, col, bone):
    """A bat wing from the shoulder sx,sy: membrane between the finger tips, bones on top."""
    pts = [(sx, sy)] + tips + [(sx - 6, sy + 4)]
    c.poly(pts, col)
    for k in range(len(tips) - 1):  # scalloped trailing edge
        (x0, y0), (x1, y1) = tips[k], tips[k + 1]
        c.poly([(x0, y0), (x1, y1), ((x0 + x1) // 2 + 1, (y0 + y1) // 2 + 3)], T, shade=False, light=False)
    for tx, ty in tips:
        n = max(abs(tx - sx), abs(ty - sy))
        c.px([(sx + (tx - sx) * i // n, sy + (ty - sy) * i // n) for i in range(n + 1)], bone)


# wing tips for the flap: raised, level, lowered
WING_TIPS = [[(10, 0), (2, 8), (0, 18), (6, 26)],
             [(4, 10), (0, 20), (4, 28), (12, 32)],
             [(8, 40), (14, 46), (22, 48), (30, 46)]]


def figure_dragon(pose=0, roar=False):
    c = Canvas(76, 52)
    tips = WING_TIPS[pose]
    dragon_wing(c, 36, 26, [(x + 8, y - 2) for x, y in tips], BROWN, K)        # far wing
    # tail with a spade
    c.poly([(20, 36), (6, 40), (0, 36), (2, 33), (8, 36), (22, 31)], RED)
    c.poly([(0, 30), (4, 33), (0, 40), (-3, 35)], RED)
    # body, scales and belly plates
    c.ellipse(32, 34, 15, 10, RED)
    scales = (c.xx + c.yy * 2) % 5 == 0
    body = c.mask_ellipse(32, 34, 15, 10)
    c.img[body & scales & (c.img == RED)] = BROWN
    belly = c.mask_ellipse(34, 40, 11, 5)
    c.img[belly] = YELLOW
    c.img[belly & (c.yy % 2 == 0)] = ORANGE
    # legs with claws
    c.ellipse(22, 40, 6, 7, RED)
    c.rect(18, 44, 25, 50, RED)
    c.px([(16, 50), (17, 51), (20, 51), (23, 51), (24, 50)], WHITE)
    c.rect(40, 42, 46, 50, RED)
    c.px([(39, 50), (42, 51), (45, 51), (47, 50)], WHITE)
    # neck
    c.poly([(40, 30), (48, 14), (56, 12), (50, 32)], RED)
    c.px([(44 + i * 2, 28 - i * 4) for i in range(4)], YELLOW)                  # throat plates
    # spikes along the back
    for x, y in [(14, 27), (20, 24), (27, 23), (34, 23), (41, 22), (46, 16), (50, 10)]:
        c.poly([(x - 2, y + 2), (x, y - 3), (x + 2, y + 2)], YELLOW, light=False)
    # head
    c.ellipse(57, 13, 8, 7, RED)
    jaw = 6 if roar else 0
    c.poly([(58, 9), (74, 11), (75, 15), (60, 17)], RED)                       # snout
    c.poly([(58, 16), (72, 17 + jaw), (70, 20 + jaw), (57, 20)], RED)            # lower jaw
    if roar:
        c.poly([(60, 16), (73, 15), (71, 18 + jaw), (60, 19)], K, shade=False, light=False)
        c.px([(62 + i * 3, 15) for i in range(4)] + [(63 + i * 3, 17 + jaw) for i in range(3)], WHITE)
    else:
        c.px([(63 + i * 3, 17) for i in range(4)], WHITE)                       # teeth
    c.px([(72, 11), (73, 12)], K)                                               # nostril
    c.poly([(52, 6), (56, 0), (50, -2), (54, 3)], LIGHT)                        # horns
    c.poly([(57, 6), (62, 1), (58, -1), (56, 4)], LIGHT)
    c.px([(58, 10), (59, 10), (60, 10)], K)                                     # brow
    c.px([(59, 11), (60, 11)], YELLOW)                                          # eye
    c.px([(60, 12)], K)
    dragon_wing(c, 34, 28, tips, RED, K)                                       # near wing
    return c.outline()


def figure_cheese(pose=0):
    c = Canvas(14, 9)
    c.poly([(0, 8), (0, 3), (13, 0), (13, 8)], YELLOW)
    c.px([(3, 5), (8, 4), (10, 6), (5, 7)], ORANGE)
    return c.outline()


def figure_egg(pose=0):
    c = Canvas(10, 13)
    c.ellipse(5, 7, 4, 5, WHITE)
    c.px([(3, 5), (6, 8), (4, 10)], GREEN)
    return c.outline()


def figure_jaga(pose=0):
    """Baba Jaga; pose 2 rides her broom through the air."""
    if pose == 2:
        c = Canvas(34, 22)
        c.rect(0, 15, 30, 17, BROWN, shade=False)                                 # broomstick
        c.poly([(0, 12), (-2, 21), (8, 18), (8, 14)], YELLOW, light=False)     # bristles
        c.poly([(10, 16), (13, 6), (22, 5), (26, 16)], GREY)                   # hunched body
        c.poly([(14, 16), (22, 16), (24, 22), (16, 22)], GREY, light=False)    # skirt down
        c.ellipse(22, 5, 5, 5, RED)
        c.ellipse(23, 6, 3, 3, SKIN)
        c.poly([(25, 5), (30, 9), (25, 8)], SKIN, light=False)
        c.px([(24, 5)], K)
        c.rect(23, 9, 30, 10, GREY, shade=False, light=False)                  # arm to the stick
        return c.outline()
    c = Canvas(22, 32)
    c.rect(3, 6, 4, 32, BROWN, shade=False, light=False)                        # broom
    c.poly([(0, 32), (3, 24), (5, 24), (8, 32)], YELLOW, light=False)
    c.poly([(5, 31), (8, 14), (16, 12), (19, 31)], GREY)
    c.ellipse(13, 9, 6, 6, RED)
    c.ellipse(14, 10, 4, 4, SKIN)
    c.poly([(17, 9), (21, 13), (17, 12)], SKIN, light=False)
    c.px([(15, 9)], K)
    if pose == 1:                                                               # arms up, casting
        c.poly([(15, 14), (20, 4), (22, 5), (18, 15)], GREY, light=False)
    return c.outline()


def figure_witch(pose=0):
    """A witch of Sleza: long dark hair, a green dress; poses 0, 1 dance, 2 flies on a broom."""
    if pose == 2:
        c = Canvas(34, 22)
        c.rect(0, 15, 30, 17, BROWN, shade=False)
        c.poly([(0, 12), (-2, 21), (8, 18), (8, 14)], YELLOW, light=False)
        c.poly([(11, 16), (14, 6), (22, 6), (25, 16)], GREEN)
        c.poly([(13, 16), (24, 16), (27, 22), (14, 21)], GREEN, light=False)
        c.poly([(16, 1), (19, -2), (23, 2), (18, 12), (14, 12)], K)             # hair flying back
        c.ellipse(20, 4, 3, 4, SKIN)
        c.px([(21, 3)], K)
        return c.outline()
    c = Canvas(22, 34)
    up = pose == 1
    c.rect(8, 31, 11, 34, K)
    c.rect(12, 31, 15, 34, K)
    c.poly([(3, 32), (7, 15), (14, 15), (18, 32)], GREEN)
    c.poly([(6, 10), (5, 26), (9, 26), (10, 10)], K, light=False)               # long dark hair
    c.ellipse(11, 9, 5, 6, K)
    c.ellipse(12, 9, 4, 5, SKIN)
    c.px([(13, 8), (15, 8)], K)
    c.px([(13, 11), (14, 11)], RED)
    arm = [(15, 16), (21, 4 if up else 24), (22, 6 if up else 26), (16, 19)]
    c.poly(arm, GREEN, light=False)
    c.ellipse(21.5, 3 if up else 26, 1.5, 1.5, SKIN, shade=False)
    arm2 = [(6, 16), (0, 4 if not up else 24), (1, 3 if not up else 26), (8, 19)]
    c.poly(arm2, GREEN, light=False)
    return c.outline()


def figure_rider(pose=0):
    """Master Twardowski riding his giant rooster through the night; pose 1 beats the wings."""
    c = Canvas(48, 40)
    down = pose == 1
    # tail: sickle feathers
    for k, col in enumerate((GREEN, BLUE, K)):
        c.poly([(12, 22), (0 + k * 2, 4 + k * 4), (4 + k * 2, 8 + k * 4), (14, 26)], col, light=False)
    c.ellipse(22, 26, 13, 9, ORANGE)                                            # body
    c.ellipse(24, 30, 9, 5, YELLOW, shade=False)
    c.poly([(30, 22), (36, 8), (42, 10), (38, 26)], ORANGE)                     # neck
    c.ellipse(40, 9, 5, 5, ORANGE)
    c.poly([(37, 4), (39, 0), (41, 3), (43, 0), (45, 5)], RED, light=False)     # comb
    c.poly([(44, 8), (48, 10), (44, 11)], YELLOW, light=False)                  # beak
    c.poly([(42, 12), (44, 16), (41, 15)], RED, light=False)                    # wattle
    c.px([(41, 8)], K)
    c.poly([(18, 34), (16, 40), (19, 38)], YELLOW, light=False)                 # legs tucked
    c.poly([(26, 34), (25, 40), (28, 38)], YELLOW, light=False)
    # the rider
    c.poly([(19, 21), (22, 8), (30, 8), (32, 21)], BLUE)                        # kontusz
    c.poly([(24, 9), (27, 9), (27, 21), (24, 21)], RED, light=False)
    c.rect(21, 15, 31, 17, YELLOW, light=False)                                 # sash
    c.poly([(24, 20), (20, 30), (24, 31), (27, 21)], BLUE, light=False)         # leg down the side
    c.rect(19, 29, 24, 32, K)
    c.ellipse(27, 5, 4, 4, SKIN)
    c.poly([(26, 7), (21, 8), (26, 6), (29, 6), (34, 8), (29, 7)], K)           # moustache
    c.rect(23, -2, 31, 3, BROWN)                                                # kolpak
    c.px([(30, -3), (31, -4), (32, -5)], WHITE)
    c.px([(28, 4)], K)
    c.poly([(31, 12), (38, 14), (38, 16), (31, 15)], BLUE, light=False)         # arm to the reins
    # the wing over all: a fan of long feathers from the shoulder, raised or beating down
    sx, sy = 20, 22
    tips = [(28, 40), (22, 42), (15, 40), (9, 36)] if down else [(6, 2), (1, 8), (-2, 15), (0, 21)]
    for k, (tx, ty) in enumerate(tips):
        nx, ny = -(ty - sy), tx - sx
        n = max(1.0, (nx * nx + ny * ny) ** 0.5)
        w = 3.2
        c.poly([(sx + nx / n * w, sy + ny / n * w), (tx, ty), (sx - nx / n * w, sy - ny / n * w)],
               BROWN if k % 2 else ORANGE)
    c.ellipse(sx + 2, sy + 1, 6, 4, ORANGE)                                      # its root
    return c.outline()


def figure_fox(pose=0):
    """A fox running through the wood; two strides."""
    c = Canvas(24, 12)
    c.poly([(0, 4), (8, 3), (8, 7), (2, 8)], ORANGE)                            # brush
    c.px([(0, 4), (1, 4), (0, 5), (1, 5)], WHITE)
    c.ellipse(13, 6, 6, 3, ORANGE)
    c.ellipse(20, 4, 3, 3, ORANGE)
    c.poly([(21, 4), (24, 6), (21, 7)], ORANGE, light=False)
    c.poly([(18, 2), (19, -1), (20, 2)], ORANGE, light=False)
    c.px([(23, 6)], K)
    c.px([(20, 4)], K)
    if pose:
        c.poly([(9, 7), (5, 11), (7, 11), (11, 8)], K, light=False)
        c.poly([(16, 7), (21, 11), (23, 11), (17, 7)], K, light=False)
    else:
        c.poly([(10, 7), (11, 12), (13, 12), (12, 7)], K, light=False)
        c.poly([(15, 7), (15, 12), (17, 12), (17, 7)], K, light=False)
    return c.outline()


def figure_sack(pose=0):
    """A sack of brimstone, open, the yellow powder showing."""
    c = Canvas(14, 16)
    c.poly([(1, 16), (2, 4), (12, 4), (13, 16)], BROWN)
    c.ellipse(7, 4, 6, 2, YELLOW, shade=False)
    c.px([(4, 2), (7, 1), (10, 2), (6, 3)], YELLOW)
    c.poly([(5, 9), (9, 9), (7, 13)], YELLOW, shade=False, light=False)         # a mark on it
    return c.outline()


def figure_sheep(pose=0):
    """The sulphur sheep: woolly body, black face and legs, a fuse sticking out of its back."""
    c = Canvas(16, 12)
    for x, y, r in ((4, 5, 3), (7, 4, 3.5), (10, 5, 3), (6, 7, 3), (9, 7, 3)):
        c.ellipse(x, y, r, r, WHITE)
    c.ellipse(13.5, 6, 2.5, 2, K, shade=False, light=False)                     # face
    c.px([(12, 4), (15, 5)], K)                                                 # ears
    c.px([(14, 6)], WHITE)
    c.rect(4, 9, 5, 12, K)
    c.rect(10, 9, 11, 12, K)
    c.poly([(6, 2), (5, -1), (6, -2), (7, 1)], GREY, shade=False, light=False)  # the fuse
    return c.outline()


def figure_poster(pose=0):
    """The king's notice: a dragon, and a crown cut in half beneath it."""
    c = Canvas(20, 26)
    c.rect(0, 0, 20, 26, YELLOW, light=False)
    c.px([(0, 0), (19, 0), (0, 25), (19, 25)], T)
    c.rect(1, 1, 19, 2, ORANGE, shade=False, light=False)
    c.poly([(3, 12), (6, 8), (12, 8), (16, 5), (18, 7), (15, 10), (10, 13), (5, 14)], RED, shade=False, light=False)
    c.poly([(7, 8), (9, 2), (12, 8)], RED, shade=False, light=False)            # wing
    c.px([(16, 6)], K)
    c.poly([(4, 22), (4, 16), (6, 18), (8, 15), (10, 18), (10, 22)], ORANGE, shade=False, light=False)
    c.poly([(11, 22), (11, 15), (13, 18), (15, 16), (16, 22)], ORANGE, shade=False, light=False)
    c.px([(10 + d, 14 + d) for d in range(10)], K)                               # the cut
    c.px([(9, 24), (10, 24), (11, 24)], RED)                                     # the seal
    return c.outline()


BUSTS = ["dratewka", "wanda", "krak", "twardowski", "devil", "jaga"]
FIGURES = ["dratewka", "wanda", "krak", "twardowski", "devil", "jaga", "dwarf", "dragon", "sheep",
           "poster", "cheese", "egg", "witch", "rider", "fox", "sack"]
WALKERS = ["dratewka", "wanda", "devil", "dwarf"]
FAR = ["dratewka", "wanda", "sheep", "poster", "egg", "jaga", "devil", "dwarf", "rider"]  # far shots, chapter cards
# poses beyond standing: walkers step (_a, _b); these dance, beat wings or run (_a, _b) and fly (_fly)
POSES = {"witch": (0, 1, 2), "jaga": (0, 1, 2), "rider": (0, 1, None), "fox": (0, 1, None)}


def patch(full, base):
    """The smallest box where full differs from base: (x, y, pixels)."""
    diff = full != base
    ys, xs = np.nonzero(diff)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    return int(x0), int(y0), full[y0:y1, x0:x1]


def sprites():
    """name -> (ox, oy, pixels); the talk/blink patches sit at their offset over the bust.
    Figures come close (RES 2) and far (RES 1, named _far)."""
    global RES
    out = {}
    RES = 2
    for n in BUSTS:
        f = globals()["bust_" + n]
        base = f()
        out["bust_" + n] = (0, 0, base)
        out["talk_" + n] = patch(f(talk=True), base)
        out["blink_" + n] = patch(f(blink=True), base)
    for RES, tag in ((2, ""), (1, "_far")):
        for n in FIGURES if tag == "" else FAR:
            f = globals()["figure_" + n]
            out[n + tag] = (0, 0, f())
            if n in WALKERS and (tag == "" or n in ("dratewka", "wanda")):
                out[n + tag + "_a"] = (0, 0, f(1))
                out[n + tag + "_b"] = (0, 0, f(2))
            if n in POSES and (tag == "" or n == "rider"):
                a, b_, fly = POSES[n]
                out[n + tag + "_a"] = (0, 0, f(a))
                out[n + tag + "_b"] = (0, 0, f(b_))
                if fly is not None:
                    out[n + tag + "_fly"] = (0, 0, f(fly))
        out["dragon" + tag + "_a"] = (0, 0, figure_dragon(0))
        out["dragon" + tag] = (0, 0, figure_dragon(1))
        out["dragon" + tag + "_b"] = (0, 0, figure_dragon(2))
        out["dragon" + tag + "_roar"] = (0, 0, figure_dragon(1, roar=True))
    RES = 2
    return out
