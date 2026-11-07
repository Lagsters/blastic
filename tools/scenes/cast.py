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


# ── the cartoon cast: drawn by hand, one character a design pixel ────────────
# k black, r red, o orange (the shadow on skin), y yellow, g green, b brown, u blue, s skin,
# w white, l light grey, e grey, d dark; '.' is transparent. Everyone faces right.
KEY = {'.': T, 'k': K, 'r': RED, 'o': ORANGE, 'y': YELLOW, 'g': GREEN, 'b': BROWN, 'u': BLUE,
       's': SKIN, 'w': WHITE, 'l': LIGHT, 'e': GREY, 'd': DARK}

ART = {}
ART["dratewka"] = [
    "...........w..........",
    "..........ww..........",
    "......rrrrwrrr........",
    "....rrrrrrrrrrrr......",
    "...rrrrrrrrrrrrrrr....",
    "...rrrrrrrrrrrrrrrrrr.",
    "...bbbbbbbbbbbbbbbbb..",
    "..bbbbbbbbbbsbbsss....",
    "..bbbbbbssssssssss....",
    "..bbbbbsswwwssswwws...",
    "..bbbbbsswkkssswkks...",
    "..bboobsswkkssswkkss..",
    "...booosssssssssssss..",
    "...bbossssssssssssooo.",
    "....bosssssssssssss...",
    ".....ossskkkkkksss....",
    "......osssrrrrsss.....",
    ".......ooosssss.......",
    ".........oooss........",
    ".....wwwwwwwwwww......",
    "....wwwwbbbbbwwww.....",
    "....wwwwbbbbbwwwww....",
    "....lwwwbbbbbwwwsw....",
    "....lwwwbbbbbbwwss....",
    "....lwwbbbbbbbb.......",
    "....llwbbbbbbbb.......",
]
ART["wanda"] = [
    "......g.r.g.r.g.......",
    ".....ggggggggggggg....",
    "....gyyyyyyyyyyyyg....",
    "...yyyyyyyyyyyyyyyy...",
    "...yyyyyyyyyyyyyyyyy..",
    "..yyyyyyysyyyyssyyy...",
    "..yyyyysssssssssssy...",
    "..yyyyssskssssssks....",
    "..yyyysswwwssssswww...",
    "..yyyysswkkssssswkk...",
    "..yyyosswkkssssswkks..",
    "..yyyossssssssssssoo..",
    "..yyyyooosssssssss....",
    "..yyy.oossskrrkss.....",
    "..yyy...ooosrrss......",
    "..yyy....oosss........",
    "..yy..wwwwwwwwwww.....",
    "..yy.wwwwrrrrrrwww....",
    "..yy.wwwwrrrrrrwwsw...",
    "...y.lwwrrrrrrrrrss...",
    ".....lwrrrrrrrrrr.....",
    "....rrrrrrrrrrrrrr....",
    "....rrrrrrrrrrrrrrr...",
    "...rrrrrrrrrrrrrrrr...",
    "...rrrrrrrrrrrrrrrrr..",
    "..rrrrrrrrrrrrrrrrrr..",
    "..rrrrrrrrrrrrrrrrrrr.",
    "..rrrrrrrrrrrrrrrrrrr.",
    ".rrrrrrrrrrrrrrrrrrrr.",
    ".wwwwwwwwwwwwwwwwwwww.",
]
ART["krak"] = [
    "...y...y...y...y....",
    "...yy.yyy.yyy.yy....",
    "...yyyyyyyyyyyyyy...",
    "...yuyyyryyyuyyyy...",
    "...yyyyyyyyyyyyyy...",
    "..llssssssssssssl...",
    "..lsssssssssssssss..",
    "..lsskkkssssskkkss..",
    "..lsswwkssssswwkss..",
    "..losswkssssswkkss..",
    "..loossssssssssssoo.",
    "..lossssssssssssso..",
    "..lwwwwsssssssswww..",
    "..lwwwwwwkkkkwwwww..",
    "...wwwwwwwwwwwwwww..",
    "...wwwwwwwwwwwwwww..",
    "....wwwwwwwwwwwww...",
    "...rrrwwwwwwwwwrrr..",
    "..rrrrrwwwwwwwrrrrr.",
    "..rrrrrrwwwwwrrrrrr.",
    "..rrrrrrrwwwrrrrrrr.",
    "..rrrrrrrrwrrrrrrrr.",
    "..rrrrrrrrwrrrrrrsr.",
    "..rrrrrrrrwrrrrrrss.",
    "..rrrrrrrrwrrrrrrr..",
    "..rrrrrrrrwrrrrrrr..",
    "..rrrrrrrrwrrrrrrrr.",
    "..rrrrrrrrwrrrrrrrr.",
    ".rrrrrrrrrwrrrrrrrrr",
    ".rrrrrrrrrwrrrrrrrrr",
    ".rrrrrrrrrwrrrrrrrrr",
    ".rrrrrrrrrwrrrrrrrrr",
    ".wwwwwwwwwwwwwwwwwww",
    ".wlwwlwwlwwlwwlwwlww",
]
ART["twardowski"] = [
    "................w.....",
    "......bbbbbbbbbww.....",
    ".....bbbbbbbbbbbb.....",
    ".....bbbbbbbbbbbb.....",
    ".....bbbbbbbbbbbb.....",
    ".....bbbbbbbbbbbb.....",
    "....rrrrrrrrrrrrrr....",
    ".....ssssssssssss.....",
    ".....sskkksssskkk.....",
    ".....sswwkssssswk.....",
    ".....oswkkssssswkk....",
    ".....osssssssssssoo...",
    "...kkkkkkksssskkkkkkk.",
    "..kk...kkkkkkkkk....kk",
    ".....oossssssssss.....",
    ".......ooosssss.......",
    "....uuuuuuuuuuuuu.....",
    "...uuuuurrrrruuuuu....",
    "...uuuuurrrrruuuuu....",
    "...uuuuurrrrruuuuuu...",
    "...uuuuurrrrruuuuss...",
    "...yyyyyyyyyyyyyss....",
    "...uuuuurrrrruuuu.....",
    "...uuuuurrrrruuuu.....",
    "..uuuuuurrrrruuuuu....",
    "..uuuuuurrrrruuuuuu...",
    "..uuuuuurrrrruuuuuu...",
    "..uuuuuurrrrruuuuuuu..",
]
ART["devil"] = [
    "...k............k.......",
    "...kk..........kk.......",
    "....kk........kk........",
    "....kkk.kkkkkkkk........",
    ".....kkkkkkkkkkk........",
    "....rkkkkkkkkkkkr.......",
    "....rrrrrrrrrrrrrr......",
    "....rrkkkrrrrrkkkr......",
    "....rryykrrrrryykr......",
    "....orrykrrrrrrykrr.....",
    "....orrrrrrrrrrrrrrr....",
    "..kkkkkkrrrrrrkkkkkkk...",
    ".kk...kkkkkkkkkk....kk..",
    ".....orrwkwkwkrr........",
    "......orrrkkkrr.........",
    ".......ooorrrr..........",
    "....ddddddddddddd.......",
    "...ddddddrrrrdddddd.....",
    "...ddddddrrrrddddddd....",
    "...dddddddrrddddddrr....",
    "...dddddddrrdddddrr.....",
    "...dddddddrrdddddd......",
    "...dddddddrrdddddd......",
    "..ddddddddrrddddddd.....",
    "..ddddddddrrdddddddd....",
    "..ddddddddrrdddddddd....",
    "..ddddddddrrddddddddd...",
    "..ddddddddrrddddddddd...",
]
ART["dwarf"] = [
    ".......r........",
    "......rrr.......",
    "......rrr.......",
    ".....rrrrr......",
    ".....rrrrr......",
    "....rrrrrrr.....",
    "...rrrrrrrrr....",
    "..rrrrrrrrrrr...",
    "...sssssssss....",
    "...sswksswks....",
    "...ossssssoss...",
    "..wwwwssssswww..",
    "..wwwwwkkwwwww..",
    "..uwwwwwwwwwwu..",
    "..uuwwwwwwwwuu..",
    "..uuuwwwwwwuuu..",
    "..uuuuwwwwuuuu..",
    "..uuuuuwwuuuuu..",
    ".uuuuuuuuuuuuuu.",
]
ART["jaga"] = [
    ".........rrrrrr.......",
    ".......rrrrwrrrrr.....",
    "......rrrrrrrrrrrr....",
    ".....rrwrrrrrrwrrrr...",
    ".....rrrrrlllssssrr...",
    ".....rrrrllsssssssrr..",
    "....rrrrllskkssskksr..",
    "....rrrrlssswksssswk..",
    "....rrwrrssssssssssss.",
    "....rrrrrossssssssooss",
    "....rrrrrossssssssooss",
    ".....rrrrosskkkksssoo.",
    "......rrroossswssss...",
    ".......rrrooooosss....",
    ".......eeeeeeeeeee....",
    "......eeeeeeeeeeeee...",
    "......eeeeeeeeeeeeee..",
    "......eeeeeeeeeeeess..",
    ".....eeeeeeeeeeeeess..",
    ".....eeeeeeeeeeeeee...",
    ".....eeeeeeeeeeeeee...",
    "....eeeeeeeeeeeeeeee..",
    "....eeeeeeeeeeeeeeee..",
    "....eeeeeeeeeeeeeeeee.",
    "...eeeeeeeeeeeeeeeeee.",
    "...eeeeeeeeeeeeeeeeee.",
    "...eeeeeeeeeeeeeeeeeee",
    "...eeeeeeeeeeeeeeeeeee",
    "...eeeeeeeeeeeeeeeeeee",
    "...eeeeeeeeeeeeeeeeeee",
    "...eeeeeeeeeeeeeeeeeee",
    "...kk..kk.........kk..",
]
ART["witch"] = [
    "......ddddddddd.......",
    ".....ddddddddddddd....",
    "....ddddddddddddddd...",
    "....dddddddddssssdd...",
    "...ddddddssssssssss...",
    "...ddddddsskkssskks...",
    "...dddddsswgkssswgk...",
    "...dddddsswkkssswkk...",
    "...ddddosssssssssssss.",
    "...dddddossssssssssoo.",
    "...ddddddosssrrrrss...",
    "...ddddddoosssssss....",
    "...dddddd..ooosss.....",
    "...ddddd..ggggggggg...",
    "...dddd..ggggggggggg..",
    "...dddd..gggggggggggg.",
    "...ddd..ggggggggggggg.",
    "....dd..ggggggggggggg.",
    "........ggggggggggggg.",
    ".......gggggggggggggg.",
    ".......ggggggggggggggg",
    "......gggggggggggggggg",
    "......gggggggggggggggg",
    ".....ggggggggggggggggg",
    ".....ggggggggggggggggg",
    "....gggggggggggggggggg",
    "....gggggggggggggggggg",
    "....gggggggggggggggggg",
    "....gggggggggggggggggg",
    "....gggggggggggggggggg",
    "....gggggggggggggggggg",
]
# where the faces are: eye rows, the mouth's row (and its columns when it hides under a
# moustache), the colour of the skin round the eyes
FACE = {"dratewka": ((9, 10, 11), 15, None, 's'), "wanda": ((8, 9, 10), 13, None, 's'),
        "krak": ((8, 9), 13, None, 's'), "twardowski": ((9, 10), 14, range(9, 13), 's'),
        "devil": ((8, 9), 13, None, 'r'), "jaga": ((6, 7), 11, None, 's')}


def art(c, rows, x0=0, y0=0):
    """Paint hand-drawn rows onto a canvas, one design pixel a character."""
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != '.':
                c.px([(x0 + x, y0 + y)], KEY[ch])


def blinking(rows, eyes_at, skin):
    """The eyes shut: whites and pupils become skin, a lid line across the middle row."""
    rows = list(rows)
    cols = {x for y in eyes_at for x, ch in enumerate(rows[y]) if ch in "wgy"}
    cols = {x for x in range(min(cols) - 1, max(cols) + 2)} if cols else set()
    for y in eyes_at:
        rows[y] = "".join(skin if x in cols and ch in "wkgy" else ch for x, ch in enumerate(rows[y]))
    mid = eyes_at[len(eyes_at) // 2]
    rows[mid] = "".join('k' if x in cols and rows[mid][x] == skin else ch for x, ch in enumerate(rows[mid]))
    return rows


def talking(rows, m, cols=None):
    """The mouth open: its row goes dark, the row under it too, the tongue below."""
    rows = list(rows)
    cols = list(cols) if cols else [x for x, ch in enumerate(rows[m]) if ch in "kr"]

    def put(y, xs, ch):
        rows[y] = "".join(ch if x in xs else c for x, c in enumerate(rows[y]))
    put(m, cols, 'k')
    put(m + 1, cols, 'k')
    put(m + 2, cols[1:-1], 'r')
    return rows


def scale2x(rows):
    """Scale2x (EPX): twice the size, with the staircase of diagonals smoothed."""
    h, w = len(rows), len(rows[0])
    g = lambda y, x: rows[y][x] if 0 <= y < h and 0 <= x < w else '.'
    out = [[None] * (w * 2) for _ in range(h * 2)]
    for y in range(h):
        for x in range(w):
            p, a, b, c, d = g(y, x), g(y - 1, x), g(y, x + 1), g(y, x - 1), g(y + 1, x)
            out[2 * y][2 * x] = a if c == a and c != d and a != b else p
            out[2 * y][2 * x + 1] = b if a == b and a != c and b != d else p
            out[2 * y + 1][2 * x] = c if d == c and d != b and c != a else p
            out[2 * y + 1][2 * x + 1] = d if b == d and b != a and d != c else p
    return ["".join(r) for r in out]


# ── busts: the figure's head and shoulders at twice the size ─────────────────

BUST_ROWS = 22


def bust(name, talk=False, blink=False):
    rows = ART[name][:BUST_ROWS]
    eyes_at, m, mcols, skin = FACE[name]
    if blink:
        rows = blinking(rows, eyes_at, skin)
    if talk:
        rows = talking(rows, m, mcols)
    big = scale2x(rows)
    c = Canvas(len(big[0]), len(big))
    art(c, big)
    return c.outline()


for _n in FACE:
    globals()["bust_" + _n] = lambda talk=False, blink=False, _n=_n: bust(_n, talk, blink)


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
    art(c, ART["dratewka"])
    return c.outline()


def figure_wanda(pose=0):
    c = Canvas(22, 34)
    legs(c, 10, 30, 32, pose, K)
    art(c, ART["wanda"])
    return c.outline()


def figure_krak(pose=0):
    c = Canvas(20, 34)
    art(c, ART["krak"])
    return c.outline()


def figure_twardowski(pose=0):
    c = Canvas(22, 34)
    legs(c, 10, 28, 32, pose, K)
    art(c, ART["twardowski"])
    return c.outline()


def figure_devil(pose=0):
    c = Canvas(24, 34)
    legs(c, 11, 28, 32, pose, K, K)
    c.poly([(1, 26), (0, 20), (2, 18), (3, 24), (6, 27)], RED, light=False)      # tail
    art(c, ART["devil"])
    return c.outline()


def figure_dwarf(pose=0):
    c = Canvas(16, 22)
    # short waddling steps: the feet stay under the coat
    back, front = {0: (4, 7), 1: (3, 8), 2: (5, 7)}[pose]
    c.rect(back, 19 - (pose == 2), back + 3, 21 - (pose == 2), K)
    c.rect(front, 19, front + 3, 21, K)
    art(c, ART["dwarf"])
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


def broom_ride(head, body_col, cloak=None):
    """Riding a broom through the air: the head (the art's first 14 rows) over a body bent
    forward, the broomstick under it, bristles trailing."""
    c = Canvas(36, 24)
    c.rect(0, 18, 34, 20, BROWN, shade=False)
    c.poly([(0, 15), (-2, 23), (8, 21), (8, 16)], YELLOW, light=False)
    if cloak:
        c.poly([(8, 8), (14, 4), (16, 16), (6, 14)], cloak, light=False)          # hair in the wind
    c.poly([(12, 19), (14, 11), (26, 11), (28, 19)], body_col)
    c.poly([(14, 19), (26, 19), (28, 24), (16, 24)], body_col, light=False)
    c.rect(26, 15, 33, 17, body_col, shade=False, light=False)                   # arm to the stick
    c.rect(32, 15, 34, 18, SKIN, shade=False, light=False)
    art(c, head, 12, -2)
    return c.outline()


def figure_jaga(pose=0):
    """Baba Jaga with her broom; pose 1 casts a spell, 2 rides the broom."""
    if pose == 2:
        return broom_ride(ART["jaga"][:14], GREY)
    c = Canvas(24, 32)
    c.rect(1, 4, 3, 30, BROWN, shade=False, light=False)                         # the broom
    c.poly([(-1, 32), (1, 25), (3, 25), (5, 32)], YELLOW, light=False)
    art(c, ART["jaga"], 1, 0)
    if pose == 1:                                                                # an arm raised
        c.poly([(16, 16), (21, 7), (23, 8), (19, 17)], GREY, light=False)
        c.rect(21, 4, 24, 7, SKIN, shade=False, light=False)
    else:
        c.rect(3, 16, 7, 18, GREY, shade=False, light=False)                     # a hand on the broom
        c.rect(2, 15, 4, 17, SKIN, shade=False, light=False)
    return c.outline()


def figure_witch(pose=0):
    """A witch of Sleza: long dark hair, a green dress; poses 0, 1 dance, 2 rides a broom."""
    if pose == 2:
        return broom_ride(ART["witch"][:13], GREEN, DARK)
    c = Canvas(24, 34)
    legs(c, 12, 31, 32, 0, K)
    art(c, ART["witch"], 1, 0)
    up = pose == 1
    for side, (sx, hx) in ((1, (17, 22)), (-1, (10, 3))):                        # both arms
        hy = 4 if (up == (side > 0)) else 24
        c.poly([(sx, 15), (hx, hy), (hx + side, hy + 2), (sx + side, 18)], GREEN, light=False)
        c.rect(hx - 1, hy - 2, hx + 2, hy + 1, SKIN, shade=False, light=False)
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
    # the rider
    c.poly([(19, 21), (22, 8), (30, 8), (32, 21)], BLUE)                        # kontusz
    c.poly([(24, 9), (27, 9), (27, 21), (24, 21)], RED, light=False)
    c.rect(21, 15, 31, 17, YELLOW, light=False)                                 # sash
    c.poly([(24, 20), (20, 30), (24, 31), (27, 21)], BLUE, light=False)         # leg down the side
    c.rect(19, 29, 24, 32, K)
    c.poly([(31, 12), (38, 14), (38, 16), (31, 15)], BLUE, light=False)         # arm to the reins
    art(whole, ART["twardowski"][:16], 15, 0)
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
