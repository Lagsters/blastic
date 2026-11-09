"""The cast of the story scenes as pixel art, for paint.py to pack next to the backdrops.

Every sprite faces right, in palette indices, and its silhouette gets a dark outline. The people
are cartoons drawn by hand, a character a design pixel (ART); their busts (close-ups) are the same
drawing's head and shoulders scaled up with Scale2x, so a face is one face in every shot. Animals,
the dragon and things are built from shapes, each shaded by a light from the upper right.
Colours stay off the four that backdrops redefine (1, 5, 7, 11); 11 marks transparent pixels.

Busts come with a talking mouth and closed eyes as small patches drawn over them;
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


# ── people: realistic figures, from the skeleton in body.py ──────────────────
import body as B

# dress, height in pixels at RES 2, skeleton, how far the body leans forward (degrees)
PEOPLE = {
    "dratewka": (B.dress_dratewka, 64, B.SEG, 0),
    "wanda": (B.dress_wanda, 60, B.SEG, 0),
    "krak": (B.dress_krak, 66, B.SEG, 0),
    "twardowski": (B.dress_twardowski, 64, B.SEG, 0),
    "devil": (B.dress_devil, 66, B.SEG, 0),
    "dwarf": (B.dress_dwarf, 40, B.DWARF, 0),
    "jaga": (B.dress_jaga, 60, B.SEG, 22),
    "witch": (B.dress_witch, 62, B.SEG, 0),
}
# the sprite round a figure px tall: room for a stride, a hat, a plume or horns
SPRITE_W, SPRITE_H = 0.84, 1.12


def person(name, pose=None, wide=SPRITE_W, **kw):
    dress, px, seg, lean = PEOPLE[name]
    px = px * RES // 2
    w, h = int(px * wide) // 2 * 2, int(px * SPRITE_H)
    return B.figure(dress, pose or B.stand_pose(lean), px, w, h, seg, **kw)


def walking(name, k):
    """Frame k of eight of a walk; a gait cycle is body.cycle_of(seg) of the figure's height."""
    _, _, seg, lean = PEOPLE[name]
    return person(name, B.walk_pose(k / 8, seg=seg, lean=lean or 3))


BUST_PX = 360          # a close-up: the figure rendered this tall, its head and shoulders kept
BUST_W, BUST_H = 88, 88


def bust(name, talk=False, blink=False):
    dress, px, seg, lean = PEOPLE[name]
    big = BUST_PX * px // 64
    w, h = big * 7 // 10, big * 28 // 25
    pose = B.stand_pose(lean)
    img = B.figure(dress, pose, big, w, h, seg, talk=talk, blink=blink)
    hx, hy = B.head_at(pose, big, h, w, seg)
    x0, y0 = int(hx) - BUST_W // 2 - 6, max(0, int(hy) - 42)
    return img[y0:y0 + BUST_H, x0:x0 + BUST_W]


for _n in PEOPLE:
    globals()["bust_" + _n] = lambda talk=False, blink=False, _n=_n: bust(_n, talk, blink)


def figure_dratewka(pose=0):
    return person("dratewka")


def figure_wanda(pose=0):
    return person("wanda")


def figure_krak(pose=0):
    return person("krak")


def figure_twardowski(pose=0):
    return person("twardowski")


def figure_devil(pose=0):
    return person("devil")


def figure_dwarf(pose=0):
    return person("dwarf")


def figure_jaga(pose=0):
    """Baba Jaga leaning on her broom; pose 1 casts a spell, 2 rides the broom."""
    if pose == 2:
        return person("jaga", B.ride_pose(30), wide=1.2, before=B.broom_ridden)
    if pose == 1:
        return person("jaga", B.cast_pose(22), after=B.broom_in_hand)
    return person("jaga", after=B.broom_in_hand)


def figure_witch(pose=0):
    """A witch of Sleza; poses 0, 1 dance, 2 rides a broom."""
    if pose == 2:
        return person("witch", B.ride_pose(20), wide=1.2, before=B.broom_ridden)
    return person("witch", B.dance_pose(pose))


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


class Lowered:
    """A canvas whose drawing calls land dy design pixels lower."""
    def __init__(self, c, dy):
        self.c, self.dy = c, dy

    def poly(self, pts, col, **kw):
        return self.c.poly([(x, y + self.dy) for x, y in pts], col, **kw)

    def ellipse(self, cx, cy, rx, ry, col, **kw):
        return self.c.ellipse(cx, cy + self.dy, rx, ry, col, **kw)

    def rect(self, x0, y0, x1, y1, col, **kw):
        return self.c.rect(x0, y0 + self.dy, x1, y1 + self.dy, col, **kw)

    def px(self, pts, col):
        self.c.px([(x, y + self.dy) for x, y in pts], col)


def figure_rider(pose=0):
    """Master Twardowski riding his giant rooster through the night; pose 1 beats the wings."""
    whole = Canvas(48, 48)
    c = Lowered(whole, 8)
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
    # the rider, sitting astride, hands on the reins
    dress, px, seg, _ = PEOPLE["twardowski"]
    px = px * RES // 2
    rider = B.figure(dress, B.ride_pose(10, 0.3), px, whole.w, int(px * SPRITE_H), seg, at=whole.w * 0.5)
    seat = int(whole.h * 0.62)                                   # his hips on the rooster's back
    hip_row = rider.shape[0] - 1 - int(0.3 * px)
    dy = seat - hip_row
    for y, x in zip(*np.nonzero(rider != T)):
        if 0 <= y + dy < whole.h and 0 <= x < whole.w:
            whole.img[y + dy, x] = rider[y, x]
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
    return whole.outline()


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
WALKERS = ["dratewka", "wanda", "devil", "dwarf", "twardowski"]
FAR = ["dratewka", "wanda", "sheep", "poster", "egg", "jaga", "devil", "dwarf", "rider", "cheese"]  # far shots, chapter cards
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
                for k in range(8):
                    out[n + tag + "_w%d" % k] = (0, 0, walking(n, k))
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
