"""Paint the backdrops of the story scenes and pack them into scenes.bin for blastic.lua.

Usage: python tools/scenes/paint.py <out.bin> [--preview dir]
Needs numpy and Pillow. Each backdrop is 240x96 pixels (the screen between the letterbox
bars), painted straight in palette indices: twelve colours are shared with the cast, four
(1, 5, 7, 11) belong to the backdrop, and 11 is the sky, which blastic.lua re-colours on
every scanline (BDR) into a smooth gradient, as the Amiga copper did.
Shading is ordered dithering with a horizontal period of two pixels, so rows repeat and LZ
packs them well.

The cast (cast.py) comes with them. scenes.bin holds the pieces of RAM they occupy (REGIONS, and
the MAP of memory banks 1..7, which blastic.lua loads with sync): per piece u8 bank, u24 address,
u16 length and its bytes.

In RAM at 0x08000 (bank 0): u8 backdrop count, u8 sprite count; per backdrop u8 name length, the
name, u8 bank, u24 address, 3 RGB colours (indices 1, 5, 7) and 3 RGB sky stops (top, middle, bottom); then
u24 address and u16 length of the cast, LZ-packed (see below). A backdrop is its 4-bit pixels (low nibble left), rows top down, packed by
make_tic.lz_pack: c<128 copies the next c+1 bytes, c>=128 repeats c-125 bytes from u16
distance back. A sprite is u8 name length,
the name, u8 width, height, x and y offset (of a patch over its bust), then per row runs of
colour<<4 | length-1 (11 is transparent); the sprites follow one another and are packed together.
"""
import sys, os
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import cast
from make_tic import lz_pack, lz_unpack

W, H = 240, 96
SHARED = {0: "1a1c2c", 2: "b13e53", 3: "ef7d57", 4: "ffcd75", 6: "38b764", 8: "5c3a1a",
          9: "3b5dc9", 10: "ffccaa", 12: "f4f4f4", 13: "94b0c2", 14: "566c86", 15: "333c57"}
SKY = 11
NAMES = ["rynek", "odra", "workshop", "road", "sleza_far", "forest", "sleza", "krakow", "wawel", "hall",
         "cellars", "night"]
yy, xx = np.mgrid[0:H, 0:W]
rng = np.random.default_rng(1957)

# five dither levels, each with a horizontal period of two pixels
LEVELS = [np.zeros((H, W), bool),
          (yy % 2 == 0) & (xx % 2 == 0),
          (xx + yy) % 2 == 0,
          ~((yy % 2 == 1) & (xx % 2 == 1)),
          np.ones((H, W), bool)]


def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def noise(scale, octaves=3, seed=0):
    """Smooth value noise in 0..1, features about `scale` pixels wide."""
    r = np.random.default_rng(seed)
    out, amp, total = np.zeros((H, W)), 1.0, 0.0
    for o in range(octaves):
        s = max(2, scale // (2 ** o))
        g = r.random((H // s + 3, W // s + 3))
        fy, fx = yy / s, xx / s
        iy, ix = fy.astype(int), fx.astype(int)
        ty, tx = fy - iy, fx - ix
        ty, tx = ty * ty * (3 - 2 * ty), tx * tx * (3 - 2 * tx)
        a = g[iy, ix] * (1 - tx) + g[iy, ix + 1] * tx
        b = g[iy + 1, ix] * (1 - tx) + g[iy + 1, ix + 1] * tx
        out += (a * (1 - ty) + b * ty) * amp
        total += amp
        amp /= 2
    return out / total


def ramp(img, mask, value, cols):
    """Paint mask with value (0..1) shaded across the colour list by dithering."""
    v = np.clip(value, 0, 0.9999) * (len(cols) - 1)
    seg = v.astype(int)
    lvl = ((v - seg) * 4 + 0.5).astype(int)
    for s in range(len(cols) - 1):
        for l in range(5):
            m = mask & (seg == s) & (lvl == l)
            img[m & LEVELS[l]] = cols[s + 1]
            img[m & ~LEVELS[l]] = cols[s]
    return img


def poly(points):
    m = Image.new("1", (W, H))
    ImageDraw.Draw(m).polygon([tuple(p) for p in points], fill=1)
    return np.array(m, bool)


def ellipse(x0, y0, x1, y1):
    m = Image.new("1", (W, H))
    ImageDraw.Draw(m).ellipse((x0, y0, x1, y1), fill=1)
    return np.array(m, bool)


def box(x0, y0, x1, y1):
    return (xx >= x0) & (xx < x1) & (yy >= y0) & (yy < y1)


def ridge(base, amp, scale, seed):
    """Mask under a noisy horizon line."""
    r = np.random.default_rng(seed)
    pts = r.random(W // scale + 3)
    x = np.arange(W) / scale
    i = x.astype(int)
    t = x - i
    t = t * t * (3 - 2 * t)
    h = base - amp * (pts[i] * (1 - t) + pts[i + 1] * t)
    return yy >= h[None, :]


def glow(img, cx, cy, radius, cols, mask=None):
    """Radial light: brightest colour at the centre, dithered out to radius."""
    d = np.hypot(xx - cx, (yy - cy) * 1.2) / radius
    m = d < 1
    if mask is not None:
        m &= mask
    ramp(img, m, 1 - d, cols)


def stars(img, n, mask, seed):
    r = np.random.default_rng(seed)
    for _ in range(n):
        x, y = r.integers(0, W), r.integers(0, H)
        if mask[y, x]:
            img[y, x] = 12 if r.random() < 0.3 else 13


# ── backdrops ────────────────────────────────────────────────────────────────

def gothic_window(img, x, y, w, h, col):
    """A pointed arch window with its top at y."""
    img[poly([(x, y + w // 2), (x + w // 2, y), (x + w, y + w // 2)]) | box(x, y + w // 2, x + w, y + h)] = col


def stepped_gable(img, x0, x1, base, top, col, steps=4):
    w = x1 - x0
    for k in range(steps):
        inset = w * k // (2 * steps)
        img[box(x0 + inset, base - (base - top) * (k + 1) // steps, x1 - inset, base)] = col


def volute_gable(img, x0, x1, base, top, col):
    """A baroque gable: a tall middle with scrolls on its shoulders."""
    w = x1 - x0
    img[box(x0 + w // 4, top, x1 - w // 4, base)] = col
    img[ellipse(x0, base - (base - top) // 2, x0 + w // 2, base + (base - top) // 2) & (yy < base)] = col
    img[ellipse(x1 - w // 2, base - (base - top) // 2, x1, base + (base - top) // 2) & (yy < base)] = col
    img[ellipse(x0 + w // 2 - 3, top - 4, x0 + w // 2 + 3, top + 2)] = col


def tenements(img, x0, x1, top_lo, top_hi, cols, seed, ground):
    """A row of narrow town houses with gables, windows lit here and there."""
    r = np.random.default_rng(seed)
    x = x0
    k = 0
    while x < x1:
        w = int(r.integers(18, 26))
        top = int(r.integers(top_lo, top_hi))
        c = cols[k % len(cols)]
        ramp(img, box(x, top, x + w, ground), 0.85 - (xx - x) / w * 0.45, [15, c, c])
        if k % 2 == 0:
            volute_gable(img, x + 1, x + w - 1, top, top - 12, c)
        else:
            stepped_gable(img, x + 1, x + w - 1, top, top - 14, c)
        img[box(x, top, x + w, top + 1)] = 13                          # cornice
        for wy in range(top + 4, ground - 10, 8):
            for wx in range(x + 3, x + w - 4, 6):
                lit = r.random() < 0.35
                img[box(wx, wy, wx + 3, wy + 5)] = 4 if lit else 15
        for ax in range(x + 2, x + w - 6, 8):                           # arcade below
            img[ellipse(ax, ground - 10, ax + 6, ground - 2) | box(ax, ground - 6, ax + 7, ground)] = 0
        x += w
        k += 1


def cobbles(img, top, cols):
    street = yy >= top
    ramp(img, street, 0.85 - (yy - top) / (H - top) * 0.9, cols)
    img[street & ((xx + (yy // 3) * 3) % 7 == 0) & (yy % 3 == 0)] = cols[0]


def copper_helmet(img, cx, base, col):
    """A renaissance tower helmet: lantern, bulb, lantern, spire."""
    img[box(cx - 5, base - 8, cx + 5, base)] = col
    img[ellipse(cx - 6, base - 16, cx + 6, base - 6)] = col
    img[box(cx - 3, base - 22, cx + 3, base - 14)] = col
    img[ellipse(cx - 4, base - 27, cx + 4, base - 19)] = col
    img[poly([(cx - 2, base - 25), (cx, base - 40), (cx + 2, base - 25)])] = col
    img[box(cx - 2, base - 6, cx - 1, base - 2) | box(cx + 1, base - 6, cx + 2, base - 2)] = 0
    img[box(cx, base - 44, cx + 1, base - 39)] = 4


def rynek():
    """Wroclaw: the gothic town hall with its gable and clock, the tower's copper helmet."""
    img = np.full((H, W), SKY)
    # the cathedral's twin spires on Ostrow Tumski, far away
    for sx in (200, 212):
        img[box(sx, 26, sx + 6, 60) | poly([(sx - 1, 26), (sx + 3, 6), (sx + 7, 26)])] = 7
    tenements(img, -4, 76, 30, 40, [1, 5, 3], 3, 84)
    tenements(img, 164, 244, 30, 42, [5, 13, 1], 7, 84)
    # the tower behind the hall
    img[box(94, 24, 108, 60)] = 14
    img[box(94, 24, 96, 60)] = 15
    copper_helmet(img, 101, 26, 7)
    # the hall: brick body, steep roof, ornate gable with pinnacles and the clock
    ramp(img, box(80, 44, 160, 84), 0.9 - (xx - 80) / 160, [8, 2, 2])
    img[poly([(80, 44), (100, 20), (140, 20), (160, 44)])] = 15
    img[poly([(80, 44), (100, 20), (140, 20), (160, 44)]) & ((xx + yy) % 4 == 0)] = 14
    gable = poly([(104, 44), (120, 6), (136, 44)])
    ramp(img, gable, 0.9 - (xx - 104) / 40, [8, 2, 3])
    for k in range(7):                                                  # pinnacles on its edges
        for side in (-1, 1):
            px = 120 + side * (2 + k * 2.3)
            py = 6 + k * 5.4
            img[poly([(px - 1, py + 2), (px, py - 4), (px + 1, py + 2)])] = 13
    for bx in range(108, 134, 5):                                       # blind tracery
        img[box(bx, 30, bx + 2, 44) & gable] = 13
    img[ellipse(112, 46, 128, 62)] = 4                                  # the astronomical clock
    img[ellipse(114, 48, 126, 60)] = 9
    img[ellipse(118, 52, 122, 56)] = 4
    img[box(119, 49, 120, 54) | box(120, 53, 125, 54)] = 4
    for wx in (86, 96, 140, 150):
        gothic_window(img, wx, 50, 6, 16, 4)
    img[box(84, 70, 156, 84) & ((xx - 84) % 12 < 8)] = 0                # ground floor arcade
    img[ellipse(84, 66, 156, 76) & (yy < 70) & ((xx - 84) % 12 < 8)] = 0
    cobbles(img, 84, [0, 15, 14])
    for lx in (60, 182):                                                # street lamps
        img[box(lx, 52, lx + 2, H)] = 0
        glow(img, lx + 1, 50, 14, [SKY, 3, 4], img == SKY)
        img[box(lx - 2, 46, lx + 4, 52)] = 4
    return img, ["b88a4a", "b0606a", "4a8a7a"], ["1a2050", "6a4a7a", "e09a6a"]


def odra():
    """Wroclaw at dawn from the Oder: the cathedral's twin spires on Ostrow Tumski, the Holy Cross
    church, the green iron Tumski bridge with its lamps, mist on the water."""
    img = np.full((H, W), SKY)
    glow(img, 60, 60, 40, [SKY, 3, 4])
    # the island: trees, the Holy Cross church, the cathedral
    trees = ridge(62, 8, 14, 81) & (yy < 70)
    img[trees] = 5
    hc = box(20, 30, 64, 62) | poly([(20, 30), (42, 16), (64, 30)])
    ramp(img, hc, 0.9 - (xx - 20) / 60, [8, 2, 3])
    img[box(36, 18, 46, 30)] = 2
    img[poly([(35, 18), (41, 2), (47, 18)])] = 7
    for wx in (24, 32, 50, 58):
        gothic_window(img, wx, 36, 4, 14, 15)
    cat = box(120, 24, 196, 62) | poly([(120, 24), (158, 12), (196, 24)])
    ramp(img, cat, 0.9 - (xx - 120) / 90, [8, 2, 3])
    for tx in (128, 148):                                                       # twin towers
        img[box(tx, 24, tx + 12, 62)] = 2
        img[box(tx, 24, tx + 2, 62)] = 8
        img[poly([(tx - 1, 24), (tx + 6, 0), (tx + 13, 24)])] = 7
        img[poly([(tx + 6, 24), (tx + 6, 0), (tx + 13, 24)])] = 6
        gothic_window(img, tx + 4, 30, 4, 12, 15)
    for wx in range(166, 194, 8):
        gothic_window(img, wx, 32, 4, 18, 15)
    # the river, mist and reflections
    river = yy >= 66
    img[river] = SKY
    refl = river & (noise(5, 1, 82) > 0.6) & (yy % 2 == 0)
    img[refl & (xx > 120) & (xx < 196)] = 2
    img[refl & (xx < 70)] = 3
    mist = (yy > 60) & (yy < 70) & (np.sin(xx / 13) + noise(20, 2, 83) * 2 > 1.3)
    img[mist & LEVELS[2]] = 13
    # the Tumski bridge: two low iron spans arching up to the deck from stone piers, lamps
    for ax in (70, 140):
        under = ellipse(ax - 1, 60, ax + 71, 88)
        img[under & ~ellipse(ax + 1, 62, ax + 69, 90) & (yy >= 59)] = 7
        for k in range(ax + 4, ax + 68, 4):
            img[(xx == k) & (yy >= 59) & under & ~ellipse(ax + 1, 62, ax + 69, 90)] = 7
            img[(xx == k) & (yy >= 59) & (yy < 74) & ~under] = 7
    for px0 in (64, 138, 208):
        img[box(px0, 59, px0 + 6, 76)] = 15
        img[box(px0 - 1, 74, px0 + 7, 78)] = 15
    img[box(60, 56, 216, 60)] = 7
    img[box(60, 52, 216, 53)] = 7
    for k in range(62, 214, 3):
        img[box(k, 53, k + 1, 56)] = 7
    for lx in range(66, 214, 24):
        img[box(lx, 46, lx + 1, 56)] = 0
        img[box(lx - 1, 43, lx + 2, 46)] = 4
    img[yy >= 88] = 0
    return img, ["000000", "1a3a2a", "3a8a6a"], ["2a3a6a", "c07a8a", "f0c080"]


def sleza_far():
    """Mount Sleza alone over the plain at dusk; a post windmill and a wayside shrine."""
    img = np.full((H, W), SKY)
    stars(img, 30, yy < 30, 91)
    mount = poly([(60, 64), (110, 22), (128, 18), (150, 24), (210, 64)]) | ridge(64, 6, 40, 92)
    ramp(img, mount, 0.6 - (yy - 18) / 80, [15, 7])
    img[box(126, 10, 128, 18)] = 0                                              # the tower on top
    # the plain in bands, mist between them
    for k, (top, col) in enumerate(((60, 1), (68, 5), (78, 1), (86, 5))):
        band = ridge(top, 3, 30 + k * 10, 93 + k) & (yy < top + 12)
        img[band] = col
    mist = (yy > 58) & (yy < 66) & (noise(18, 2, 97) > 0.45)
    img[mist & LEVELS[1]] = 13
    # the windmill on a hillock
    img[ellipse(26, 66, 66, 90) & (yy < 80)] = 0
    img[box(40, 46, 52, 68)] = 0
    img[poly([(38, 46), (46, 38), (54, 46)])] = 0
    for a in (0.5, 2.07, 3.64, 5.21):
        dx, dy = np.cos(a), np.sin(a)
        px_, py_ = -dy * 3, dx * 3
        img[poly([(46, 50), (46 + dx * 22, 50 + dy * 22), (46 + dx * 22 + px_, 50 + dy * 22 + py_),
                  (46 + dx * 6 + px_, 50 + dy * 6 + py_)])] = 0
    # the shrine by the road
    img[box(196, 62, 200, 84) | box(192, 56, 204, 62) | poly([(190, 56), (198, 48), (206, 56)])] = 0
    img[box(196, 58, 200, 61)] = 4
    img[box(197, 44, 199, 49) | box(195, 46, 201, 47)] = 0
    img[yy >= 90] = 0
    return img, ["3a3a2a", "2a4a3a", "3a3a6a"], ["101a40", "6a4a6a", "d0806a"]


def forest():
    """A night forest on the way up the mountain: rows of trunks, shafts of moonlight, ferns and
    toadstools by the path."""
    img = np.full((H, W), SKY)
    r = np.random.default_rng(101)
    for depth, col, n, wmin in ((0, 7, 18, 3), (1, 5, 12, 5), (2, 15, 8, 8)):
        for _ in range(n):
            x = int(r.integers(-10, W))
            w = int(r.integers(wmin, wmin + 5))
            img[box(x, 0, x + w, 84)] = col
            if depth == 2:
                img[box(x + w - 2, 0, x + w, 84)] = 0
    # moonlight shafts through the canopy
    for sx in (60, 150, 200):
        shaft = poly([(sx, 0), (sx + 10, 0), (sx - 20, 90), (sx - 34, 90)])
        img[shaft & LEVELS[1] & (img != 15)] = 13
    # the ground, the path, ferns, toadstools
    ground = yy >= 80
    ramp(img, ground, 0.6 - (yy - 80) / 20, [0, 5])
    img[poly([(96, 96), (150, 96), (130, 80), (116, 80)])] = 14
    for fx in range(4, W, 13):
        if 90 < fx < 156:
            continue
        for k in range(-2, 3):
            img[poly([(fx, 92), (fx + k * 4, 82 + abs(k) * 2), (fx + k * 4 + 1, 84 + abs(k) * 2)])] = 6
    for mx, my in ((40, 88), (176, 90), (196, 86)):
        img[box(mx + 2, my, mx + 4, my + 5)] = 12
        img[ellipse(mx, my - 3, mx + 6, my + 2) & (yy <= my)] = 2
        img[box(mx + 1, my - 2, mx + 2, my - 1) | box(mx + 4, my - 1, mx + 5, my)] = 12
    return img, ["000000", "1a2a2a", "2a3a4a"], ["05081a", "101a3a", "1a2a4a"]


def workshop():
    img = np.zeros((H, W), int)
    planks = (xx // 14) % 2
    ramp(img, np.ones((H, W), bool), 0.3 + 0.15 * planks + 0.15 * yy / H, [0, 8, 1])
    img[(xx % 14) == 0] = 0
    # window with the night outside
    win = box(150, 14, 196, 54)
    img[win] = SKY
    img[box(172, 14, 174, 54) | box(150, 33, 196, 35)] = 8
    stars(img, 12, win, 4)
    # shelf with boots
    img[box(10, 40, 120, 44)] = 8
    for i, bx in enumerate(range(16, 112, 18)):
        c = [0, 2, 15, 3][i % 4]
        img[box(bx, 28, bx + 6, 40) | box(bx, 34, bx + 12, 40)] = c
    # workbench and the candle's light
    bench = box(20, 70, 140, 76) | box(26, 76, 32, H) | box(128, 76, 134, H)
    img[bench] = 8
    glow(img, 90, 60, 60, [8, 1, 3, 4], ~bench & ~win)
    img[box(88, 58, 92, 70)] = 12
    img[box(89, 54, 91, 58)] = 4
    img[yy >= 88] = 0
    return img, ["8a5a30", "5a4a6a", "6a4a3a"], ["0a1030", "1a2a5a", "2a3a70"]


def road():
    img = np.full((H, W), SKY)
    glow(img, 150, 74, 40, [SKY, 3, 4, 12])
    far = ridge(70, 30, 40, 2) & ~ridge(90, 0, 40, 0)
    far |= poly([(20, 74), (60, 38), (100, 74)])  # Mount Sleza on the horizon
    img[far] = 7
    mid = ridge(82, 12, 30, 3)
    ramp(img, mid, 0.5 - (yy - 60) / 60, [0, 5])
    near = ridge(86, 8, 50, 5)
    img[near] = 0
    for px in [30, 44, 190, 204, 218]:
        img[ellipse(px - 4, 48, px + 4, 80)] = 0
    roadm = poly([(110, H), (130, H), (140, 76), (136, 76)])
    img[roadm] = 15
    return img, ["000000", "3a2050", "6a3a6a"], ["2a1a4a", "c06a50", "f0a050"]


def sleza():
    img = np.full((H, W), SKY)
    stars(img, 90, yy < 60, 11)
    glow(img, 196, 18, 18, [SKY, 7, 13], yy < 60)
    img[ellipse(190, 12, 202, 24)] = 12
    mount = ridge(40, 34, 60, 21) | poly([(60, H), (124, 16), (200, H)])
    ramp(img, mount, 0.65 - yy / H * 0.7 + (xx - 124) / 400, [0, 15, 5])
    # stone circle on the summit, lit by the bonfire
    for sx in [102, 112, 136, 146]:
        img[box(sx, 14, sx + 5, 24)] = 14
    glow(img, 124, 22, 30, [15, 2, 3, 4], mount & (yy < 40))
    img[poly([(118, 26), (124, 10), (130, 26)])] = 4
    img[poly([(120, 26), (124, 16), (128, 26)])] = 12
    # mist in the valley
    mist = (np.sin(xx / 17 + yy / 3) + noise(24, 2, 23) * 2 > 1.4) & (yy > 64) & (yy < 84)
    img[mist & LEVELS[2]] = 13
    img[yy >= 88] = 0
    return img, ["000000", "2a3a4a", "5a8aa0"], ["05081a", "10204a", "2a5a7a"]


def krakow():
    """Krakow: the Cloth Hall with its renaissance attic and St Mary's two unequal towers."""
    img = np.full((H, W), SKY)
    # St Mary's: brick nave, the tall north tower with its crowned spire, the lower one domed
    ramp(img, box(150, 40, 236, 80), 0.9 - (xx - 150) / 120, [8, 2, 3])
    img[poly([(150, 40), (193, 26), (236, 40)])] = 8
    for wx in range(156, 232, 12):
        gothic_window(img, wx, 48, 6, 20, 15)
    ramp(img, box(160, 24, 178, 80), 0.8 - (xx - 160) / 30, [8, 2, 3])  # north tower
    img[poly([(160, 24), (169, 2), (178, 24)])] = 7
    for tx in (159, 177):
        img[poly([(tx - 2, 26), (tx, 14), (tx + 2, 26)])] = 7
    img[box(166, 9, 172, 12)] = 4                                       # the golden crown
    img[box(168, 5, 170, 9)] = 4
    ramp(img, box(206, 32, 222, 80), 0.8 - (xx - 206) / 26, [8, 2, 3])  # south tower
    img[ellipse(205, 22, 223, 40) & (yy < 32)] = 7
    img[poly([(212, 24), (214, 12), (216, 24)])] = 7
    for x0, ys in ((163, (30, 50)), (209, (38, 54))):
        for wy in ys:
            gothic_window(img, x0 + 3, wy, 4, 10, 15)
    # the Cloth Hall
    hall = box(4, 44, 146, 84)
    ramp(img, hall, 0.95 - (yy - 44) / 80, [14, 1, 1])
    img[box(4, 40, 146, 44)] = 2                                        # roof
    for ax in range(6, 144, 9):                                         # the attic's cresting
        img[poly([(ax, 40), (ax + 3, 30), (ax + 6, 40)])] = 1
        img[ellipse(ax + 2, 35, ax + 5, 38)] = 13
    img[box(4, 40, 146, 41)] = 13
    for ax in range(8, 144, 12):                                        # the arcades
        img[ellipse(ax, 60, ax + 9, 70) | box(ax, 65, ax + 10, 84)] = 0
        img[box(ax + 2, 70, ax + 8, 84)] = 15
    for wx in range(10, 144, 12):
        img[box(wx, 48, wx + 4, 56)] = 4 if wx % 3 else 15
    cobbles(img, 84, [0, 14, 13])
    return img, ["d0b070", "000000", "4a8a7a"], ["2a4a8a", "8a9ac0", "f0d090"]


def wawel():
    """Wawel hill over the Vistula: brick walls, the castle, the cathedral's golden dome and
    green spires, the dragon's den at the foot of the hill."""
    img = np.full((H, W), SKY)
    glow(img, 40, 70, 46, [SKY, 3, 4])
    hill = ridge(70, 10, 50, 31) | ellipse(70, 52, 260, 130)
    ramp(img, hill, 0.75 - (yy - 52) / 40, [0, 15, 5])
    # brick fortifications with bastions
    walls = box(96, 46, 236, 66)
    for bx in (96, 150, 206):
        walls |= poly([(bx, 66), (bx + 4, 40), (bx + 22, 40), (bx + 26, 66)])
    ramp(img, walls, 0.85 - (xx - 96) / 200, [8, 2, 3])
    img[walls & ((xx // 6 + yy // 3) % 2 == 0) & (yy % 3 == 0)] = 8
    for cx in range(98, 236, 6):
        img[box(cx, 44, cx + 3, 46) & walls] = 2
    # the castle and its red roofs
    castle = box(150, 22, 232, 44)
    ramp(img, castle, 0.95 - (xx - 150) / 120, [14, 13, 12])
    img[poly([(148, 22), (160, 12), (222, 12), (234, 22)])] = 2
    for wx in range(154, 230, 7):
        img[box(wx, 28, wx + 3, 34)] = 4 if wx % 2 else 15
    # the cathedral: golden Sigismund dome, green-helmeted towers
    img[box(110, 20, 148, 44)] = 13
    img[box(110, 20, 112, 44)] = 14
    img[ellipse(118, 8, 134, 24) & (yy < 18)] = 4
    img[ellipse(118, 8, 126, 24) & (yy < 18)] = 3
    img[box(125, 2, 127, 9)] = 4
    for tx, top in ((104, 0), (140, 6)):
        img[box(tx, top + 14, tx + 10, 44)] = 14
        copper_helmet(img, tx + 5, top + 16, 7)
    # the dragon's den and the Vistula
    img[ellipse(64, 62, 92, 92) & hill] = 0
    img[ellipse(68, 66, 88, 92) & hill] = 15
    river = yy >= 82
    img[river] = 9
    refl = river & (noise(6, 1, 34) > 0.55) & ((yy % 3) == 0)
    img[refl & (xx < 90)] = 4
    img[refl & (xx >= 90)] = 13
    return img, ["000000", "2a4a3a", "4a9a7a"], ["4a2a6a", "b05a6a", "f0b070"]


def hall():
    img = np.zeros((H, W), int)
    ramp(img, np.ones((H, W), bool), 0.75 - np.abs(xx - 120) / 300 - yy / 400, [0, 15, 14])
    mortar = ((yy % 10) == 0) | (((xx + (yy // 10) % 2 * 10) % 20) == 0)
    img[mortar] = 15
    for wx in [30, 190]:
        win = box(wx, 12, wx + 20, 60) | ellipse(wx, 2, wx + 20, 22)
        img[win] = SKY
        img[box(wx + 9, 2, wx + 11, 60)] = 15
    for bx in [70, 150]:  # banners with a white eagle
        img[box(bx, 4, bx + 20, 50)] = 2
        img[poly([(bx, 50), (bx + 10, 44), (bx + 20, 50)])] = 0
        img[ellipse(bx + 6, 18, bx + 14, 30) | box(bx + 3, 22, bx + 17, 25)] = 12
    for tx in [62, 178]:  # torches
        glow(img, tx, 36, 16, [15, 2, 3, 4])
        img[box(tx - 1, 36, tx + 1, 46)] = 8
    floor = yy >= 78
    ramp(img, floor, 0.2 + (yy - 78) / 40, [0, 15, 14])
    img[poly([(96, 78), (144, 78), (170, H), (70, H)])] = 2
    img[box(104, 40, 136, 78)] = 4  # the throne
    img[box(108, 50, 132, 72)] = 2
    img[box(100, 34, 140, 40)] = 4
    return img, ["000000", "000000", "000000"], ["203060", "3a5aa0", "8ab0e0"]


def cellars():
    """The devil's cellars: rock arches, a lava river, cauldrons on the fire, chains, the pact."""
    img = np.full((H, W), SKY)
    # far cavern: hazy columns
    for cx in (30, 90, 150, 210):
        img[box(cx - 8, 0, cx + 8, 80) & (noise(8, 2, cx) > 0.35)] = 1
    # rock vault with stalactites, near arches darker
    vault = ~ellipse(-30, 10, 270, 170)
    ramp(img, vault, 0.3 + yy / H * 0.4, [0, 1, 5])
    for ax in (-10, 120, 250):
        arch = ellipse(ax - 70, -10, ax + 70, 150) & ~ellipse(ax - 58, 2, ax + 58, 160)
        ramp(img, arch, 0.25 + (yy / H) * 0.5, [0, 1, 5])
    for sx in range(4, W, 17):
        img[poly([(sx, 0), (sx + 3, 10 + sx % 11), (sx + 6, 0)])] = 0
    # chains
    for cx in (60, 178):
        img[(xx == cx) & (yy < 44) & ((yy % 4) < 3)] = 14
        img[(xx == cx + 1) & (yy < 44) & ((yy % 4) == 1)] = 14
    # the lava river with a crust
    lava = yy >= 80
    ramp(img, lava, 1 - (yy - 80) / 20, [2, 3, 4])
    crust = lava & (noise(5, 2, 77) > 0.68)
    img[crust] = 0
    # ledge, cauldron on its fire, the pact on a stone lectern
    ledge = box(0, 72, 240, 82)
    ramp(img, ledge, 0.5 - (yy - 72) / 30, [0, 1])
    img[ellipse(26, 52, 62, 78) & (yy > 58)] = 0                        # the cauldron
    img[ellipse(28, 54, 60, 76) & (yy > 60)] = 14
    img[ellipse(26, 56, 62, 64)] = 0
    img[ellipse(30, 57, 58, 63)] = 6                                    # bubbling brew
    glow(img, 44, 80, 16, [0, 2, 3, 4], yy > 74)
    img[box(186, 52, 196, 74)] = 14                                     # lectern
    img[box(182, 48, 200, 54)] = 13
    img[box(186, 44, 198, 50)] = 12                                     # the pact
    img[box(188, 46, 196, 47) | box(188, 48, 194, 49)] = 2
    for cx in (180, 202):                                               # candles
        img[box(cx, 42, cx + 2, 52)] = 12
        glow(img, cx + 1, 40, 6, [SKY, 3, 4], img == SKY)
    return img, ["4a1414", "7a2a1a", "000000"], ["000000", "300808", "c03010"]


def night():
    img = np.full((H, W), SKY)
    stars(img, 120, yy < 80, 61)
    glow(img, 190, 24, 26, [SKY, 7, 13])
    img[ellipse(180, 14, 200, 34)] = 12
    img[ellipse(185, 12, 203, 30)] = SKY
    hill = ridge(76, 10, 40, 62)
    img[hill] = 0
    sil = box(60, 50, 180, 78) | poly([(80, 50), (90, 34), (100, 50)]) | box(120, 30, 132, 50) \
        | poly([(118, 30), (126, 18), (134, 30)]) | box(150, 40, 166, 50)
    img[sil] = 15
    for wx in range(66, 176, 11):
        img[box(wx, 60, wx + 3, 65)] = 4
    return img, ["000000", "000000", "2a4a6a"], ["05051a", "101a40", "2a3a60"]


# ── packing ──────────────────────────────────────────────────────────────────

def pack(img):
    img = img.astype(np.uint8)
    return bytes((img[:, 0::2] | (img[:, 1::2] << 4)).flatten())


# where the art may live in the cart's RAM: MAP, the SPRITES left after the music samples, and
# the sound effect slots the game never writes (9..63)
REGIONS = [(0x08000, 32640), (0x06400, 0x08000 - 0x06400), (0x100E4 + 9 * 66, 55 * 66)]
# backdrops that do not fit there go to the MAP of the other memory banks
BANKS = 8


def preview_png(name, img, own, sky, preview):
    os.makedirs(preview, exist_ok=True)
    pal = {**SHARED, 1: own[0], 5: own[1], 7: own[2]}
    rgb = np.zeros((H, W, 3), np.uint8)
    for i, h in pal.items():
        rgb[img == i] = hexrgb(h)
    stops = [hexrgb(h) for h in sky]
    for y in range(H):
        k = y / (H - 1) * 2
        a, b = stops[int(min(k, 1.999))], stops[int(min(k, 1.999)) + 1]
        f = k - int(min(k, 1.999))
        rgb[y][img[y] == SKY] = [int(a[c] + (b[c] - a[c]) * f) for c in range(3)]
    Image.fromarray(rgb).resize((W * 3, H * 3), Image.NEAREST).save(os.path.join(preview, name + ".png"))


def cast_runs(sprites):
    raw = bytearray()
    for name, (ox, oy, px) in sprites.items():
        raw += bytes([len(name)]) + name.encode() + bytes([px.shape[1], px.shape[0], ox, oy])
        for row in px:
            x = 0
            while x < len(row):
                n = 1
                while x + n < len(row) and row[x + n] == row[x] and n < 16:
                    n += 1
                raw.append(int(row[x]) << 4 | (n - 1))
                x += n
    return bytes(raw)


def main():
    out = sys.argv[1]
    preview = sys.argv[sys.argv.index("--preview") + 1] if "--preview" in sys.argv else None
    sprites = cast.sprites()
    pieces = []  # (name, packed, colours)
    for name in NAMES:
        img, own, sky = globals()[name]()
        raw = pack(img)
        packed = lz_pack(raw)
        assert lz_unpack(packed) == raw
        pieces.append((name, packed, own + sky))
        print(f"{name:9s} {len(packed):5d} B")
        if preview:
            preview_png(name, img, own, sky, preview)
    castp = lz_pack(cast_runs(sprites))
    print(f"cast      {len(sprites)} sprites {len(castp):5d} B")
    # the header and the cast in MAP, the backdrops wherever they fit, largest first: bank 0's
    # regions, MAP last, then the MAP of banks 1..7; places are (bank, region)
    places = [(0, 1), (0, 2), (0, 0)] + [(b, 0) for b in range(1, BANKS)]
    head = 2 + sum(23 + len(n) for n, _, _ in pieces) + 5
    used = {pl: 0 for pl in places}
    used[(0, 0)] = head + len(castp)
    where = {}
    for name, packed, _ in sorted(pieces, key=lambda p: -len(p[1])):
        for pl in places:
            if used[pl] + len(packed) <= REGIONS[pl[1]][1]:
                where[name] = (pl, used[pl])
                used[pl] += len(packed)
                break
        else:
            raise ValueError(f"no room for the backdrop {name}")
    table = bytearray([len(pieces), len(sprites)])
    datas = {pl: bytearray(u) for pl, u in used.items()}
    for name, packed, colours in pieces:
        (bank, r), off = where[name]
        table += bytes([len(name)]) + name.encode() + bytes([bank]) + (REGIONS[r][0] + off).to_bytes(3, "little")
        for h in colours:
            table += bytes(hexrgb(h))
        datas[(bank, r)][off:off + len(packed)] = packed
    table += (REGIONS[0][0] + head).to_bytes(3, "little") + len(castp).to_bytes(2, "little")
    datas[(0, 0)][:head + len(castp)] = table + castp
    # the file: per piece u8 bank, u24 address, u16 length, its bytes (make_tic.py puts them in chunks)
    blob = bytearray()
    for (bank, r), d in datas.items():
        if d:
            blob += bytes([bank]) + REGIONS[r][0].to_bytes(3, "little") + len(d).to_bytes(2, "little") + d
    open(out, "wb").write(blob)
    print(f"{out}: " + ", ".join(f"bank {b} {hex(REGIONS[r][0])} {u}/{REGIONS[r][1]} B"
                               for (b, r), u in used.items() if u))


if __name__ == "__main__":
    main()
