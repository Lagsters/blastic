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
the cast, LZ-packed (see below) and cut into up to three parts: u8 count, three times u24
address and u16 length. A backdrop is its 4-bit pixels (low nibble left), rows top down, packed by
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


DARKER = {1: 8, 5: 2, 3: 2, 10: 3, 13: 14, 12: 13, 4: 3, 7: 15, 2: 8, 14: 15, 8: 0, 9: 15, 6: 15, 15: 0}


def window(img, x, y, w, h, lit):
    img[box(x - 1, y - 1, x + w + 1, y + h)] = 13            # stone frame
    if lit:
        img[box(x, y, x + w, y + h)] = 4
        img[box(x, y + h // 2, x + w, y + h)] = 3
        img[box(x + w // 2, y, x + w // 2 + 1, y + h)] = 8     # mullion
    else:
        img[box(x, y, x + w, y + h)] = 15
        img[box(x, y, x + 1, y + h // 2)] = 9                   # the sky in the glass
    img[box(x - 1, y + h, x + w + 1, y + h + 1)] = 12          # sill
    img[box(x - 1, y + h + 1, x + w + 1, y + h + 2)] = 0


def house(img, r, x, w, top, ground, col, gable):
    shade = DARKER[col]
    body = box(x, top, x + w, ground)
    lit = 0.95 - (xx - x) / w * 0.5                             # low sun from the left
    ramp(img, body, lit, [shade, col, col])
    if gable == "volute":
        g = box(x + w // 4, top - 14, x + w - w // 4, top)
        g |= ellipse(x, top - 9, x + w // 2, top + 9) & (yy < top)
        g |= ellipse(x + w // 2, top - 9, x + w, top + 9) & (yy < top)
        g |= ellipse(x + w // 2 - 3, top - 18, x + w // 2 + 3, top - 12)
        ramp(img, g, lit, [shade, col, col])
        img[box(x + w // 2 - 1, top - 11, x + w // 2 + 2, top - 6)] = 15
        img[box(x + w // 4, top - 15, x + w - w // 4, top - 14)] = 12
    elif gable == "stepped":
        for k in range(4):
            inset = w * k // 8
            st = box(x + inset, top - 4 * (k + 1), x + w - inset, top - 4 * k)
            ramp(img, st, lit, [shade, col, col])
            img[box(x + inset, top - 4 * (k + 1), x + w - inset, top - 4 * (k + 1) + 1)] = 12
    else:
        roof = poly([(x - 1, top), (x + 4, top - 12), (x + w - 4, top - 12), (x + w + 1, top)])
        ramp(img, roof, 0.7 - (xx - x) / w * 0.4 + (yy % 3 == 0) * 0.2, [0, 8, 2])
        img[box(x + w // 2 - 2, top - 9, x + w // 2 + 2, top - 3)] = 13
        img[box(x + w // 2 - 1, top - 8, x + w // 2 + 1, top - 4)] = 4 if r.random() < 0.5 else 15
        img[box(x + 3, top - 16, x + 6, top - 10)] = 8
    img[box(x, top, x + w, top + 2)] = 12                        # cornice
    img[box(x, top + 2, x + w, top + 3)] = shade
    for fy in range(top + 6, ground - 14, 9):
        img[box(x, fy + 7, x + w, fy + 8)] = shade               # string course
        for wx in range(x + 3, x + w - 4, 6):
            window(img, wx, fy, 3, 5, r.random() < 0.3)
    img[box(x, top, x + 1, ground)] = shade
    img[box(x, ground - 12, x + w, ground - 11)] = 13
    for ax in range(x + 2, x + w - 6, 9):
        arch = ellipse(ax, ground - 10, ax + 7, ground - 3) | box(ax, ground - 6, ax + 8, ground)
        img[arch] = 0
        img[arch & (yy > ground - 6) & LEVELS[2]] = 3 if r.random() < 0.5 else 8


def town_hall(img):
    body = box(70, 42, 170, 84)
    ramp(img, body, 0.9 - (xx - 70) / 140, [8, 2, 2])
    img[body & (yy % 3 == 0) & ((xx + (yy // 3) * 2) % 5 != 0)] = 8          # brick courses
    roof = poly([(66, 42), (88, 16), (152, 16), (174, 42)])
    ramp(img, roof, 0.75 - (xx - 66) / 108 * 0.5, [0, 15, 14])
    img[roof & ((xx - yy) % 5 == 0)] = 15
    for dx in (82, 100, 140, 158):
        img[poly([(dx - 3, 34), (dx, 27), (dx + 3, 34)]) | box(dx - 3, 34, dx + 4, 40)] = 14
        img[box(dx - 1, 34, dx + 2, 39)] = 4
    tower = box(146, 14, 160, 42)                                           # the tower over the roof
    ramp(img, tower, 0.9 - (xx - 146) / 14, [8, 2, 2])
    img[tower & (yy % 3 == 0) & ((xx + (yy // 3) * 2) % 5 != 0)] = 8
    img[box(146, 14, 160, 16)] = 13
    for wy in (20, 30):
        img[box(151, wy, 155, wy + 6) | poly([(151, wy), (153, wy - 2), (155, wy)])] = 15
    copper_helmet(img, 153, 16, 7)
    gable = poly([(102, 44), (120, 2), (138, 44)])
    ramp(img, gable, 0.95 - (xx - 102) / 36, [8, 2, 3])
    img[gable & (yy % 3 == 0) & ((xx + (yy // 3) * 2) % 5 != 0)] = 8
    for k in range(8):
        for side in (-1, 1):
            px = 120 + side * (2 + k * 2.2)
            py = 4 + k * 5
            img[poly([(px - 1, py + 3), (px, py - 4), (px + 1, py + 3)])] = 12
    for bx in range(108, 134, 4):
        img[box(bx, 24, bx + 1, 44) & gable] = 13
        img[ellipse(bx - 1, 21, bx + 3, 27) & ~ellipse(bx, 22, bx + 2, 26) & gable] = 13
    img[box(70, 42, 170, 44)] = 13
    img[ellipse(110, 46, 130, 66)] = 4
    img[ellipse(112, 48, 128, 64)] = 9
    img[ellipse(113, 49, 127, 63) & ~ellipse(115, 51, 125, 61)] = 0
    img[ellipse(118, 54, 122, 58)] = 4
    img[box(119, 50, 120, 56) | box(120, 55, 125, 56)] = 4
    for wx in (76, 90, 146, 160):
        img[poly([(wx - 1, 54), (wx + 3, 47), (wx + 7, 54)]) | box(wx - 1, 54, wx + 7, 74)] = 13
        img[poly([(wx, 54), (wx + 3, 48), (wx + 6, 54)]) | box(wx, 54, wx + 6, 73)] = 15
        img[box(wx + 3, 50, wx + 4, 73)] = 13
        img[box(wx, 63, wx + 6, 64)] = 13
        img[box(wx, 55, wx + 2, 62)] = 9
        img[box(wx, 65, wx + 6, 73) & LEVELS[2]] = 3
    for ax in range(74, 166, 12):
        arch = ellipse(ax, 74, ax + 9, 84) | box(ax, 79, ax + 9, 84)
        img[arch] = 0
        img[box(ax - 1, 74, ax, 84)] = 13


def square(img, top, seed=7):
    """Cobbles in perspective: rows widen towards us, each stone a little different, lit on top."""
    r = np.random.default_rng(seed)
    y, row = top, 0
    while y < H:
        hgt = 1 + row // 2
        sw = 4 + row * 2
        x0 = -int(r.integers(0, sw))
        while x0 < W:
            w = sw + int(r.integers(-1, 2))
            img[box(x0 + 1, y, x0 + w, y + hgt)] = (14, 15, 15)[int(r.integers(0, 3))]
            if hgt > 1:
                img[box(x0 + 1, y, x0 + w, y + 1)] = 13 if r.random() < 0.6 else 14
            x0 += w
        img[box(0, y + hgt, W, y + hgt + 1)] = 0
        y += hgt + 1
        row += 1


def rynek():
    """Wroclaw's market square at sunset: the brick town hall with its stone gable, clock and
    copper-helmed tower; plastered tenements with cornices, framed windows and tiled roofs."""
    img = np.full((H, W), SKY)
    glow(img, 20, 70, 60, [SKY, 3, 4])
    for sx in (204, 214):
        img[box(sx, 26, sx + 6, 60) | poly([(sx - 1, 26), (sx + 3, 6), (sx + 7, 26)])] = 14
    r = np.random.default_rng(84)
    x = -6
    for w, top, col, g in ((22, 34, 1, "volute"), (20, 40, 5, "eaves"), (24, 30, 10, "stepped"),
                           (18, 44, 13, "eaves")):
        house(img, r, x, w, top, 84, col, g)
        x += w
    x = 170
    for w, top, col, g in ((20, 38, 3, "eaves"), (24, 30, 13, "volute"), (20, 42, 1, "stepped"),
                           (22, 36, 5, "eaves")):
        house(img, r, x, w, top, 84, col, g)
        x += w
    town_hall(img)
    square(img, 84)
    for lx in (62, 178):
        img[box(lx, 52, lx + 2, 86)] = 0
        img[box(lx - 2, 46, lx + 4, 52)] = 0
        img[box(lx - 1, 47, lx + 3, 51)] = 4
    return img, ["c08a4a", "c0707a", "4a8a7a"], ["1a2050", "6a4a7a", "e09a6a"]



def bricks(img, mask, col=8):
    """Brick courses over a wall already painted: mortar every third row, joints staggered."""
    img[mask & (yy % 3 == 0) & ((xx + (yy // 3) * 2) % 5 != 0)] = col


def foliage(img, mask, seed, cols=(1, 5, 6)):
    """Tree crowns: clumps lit from the upper left, darker underneath."""
    n = noise(6, 3, seed)
    lit = n - (yy - yy[mask].min() if mask.any() else 0) / 60
    ramp(img, mask, np.clip(lit, 0, 1), list(cols))


def reflect(img, water, top, seed):
    """The water mirrors what stands above it, broken by ripples and darkened."""
    src = img.copy()
    for y in range(top, H):
        sy = 2 * top - y - 1
        keep = water[y]
        if sy < 0 or (y - top) % 3 == 2:                # a ripple line shows the sky's colour
            img[y, keep] = SKY
            continue
        shift = int(round(np.sin((y - top) * 0.9 + seed) * (1 + (y - top) / 14)))
        dark = np.array([REFLECT.get(int(c), int(c)) for c in np.roll(src[sy], shift)])
        img[y, keep] = dark[keep]


REFLECT = {12: 13, 13: 14, 4: 3, 3: 2, 2: 8, 8: 0, 7: 5, 6: 5, 14: 15, 15: 0, 1: 0, 5: 1, 9: 15}


def odra():
    """Wroclaw at dawn from the Oder: Ostrow Tumski with the cathedral's twin green spires and
    the Holy Cross church in brick among trees, the green iron Tumski bridge with its lamps,
    the river mirroring it all."""
    img = np.full((H, W), SKY)
    glow(img, 34, 58, 46, [SKY, 3, 4])
    img[ellipse(28, 50, 40, 62)] = 4
    img[ellipse(30, 52, 38, 60)] = 12
    # the Holy Cross church: a brick hall with one tall spire
    hc = box(14, 30, 70, 62)
    ramp(img, hc, 0.95 - (xx - 14) / 70, [8, 2, 3])
    bricks(img, hc)
    roof = poly([(12, 30), (24, 14), (60, 14), (72, 30)])
    ramp(img, roof, 0.8 - (xx - 12) / 60 * 0.6, [0, 15, 14])
    img[roof & ((xx - yy) % 4 == 0)] = 15
    tw = box(56, 18, 68, 62)
    ramp(img, tw, 0.95 - (xx - 56) / 14, [8, 2, 3])
    bricks(img, tw)
    img[poly([(55, 18), (62, -14), (69, 18)])] = 7
    img[poly([(62, 18), (62, -14), (69, 18)])] = 5
    for wx in (18, 28, 38, 48):
        img[poly([(wx - 1, 40), (wx + 2, 35), (wx + 5, 40)]) | box(wx - 1, 40, wx + 5, 56)] = 13
        img[poly([(wx, 40), (wx + 2, 36), (wx + 4, 40)]) | box(wx, 40, wx + 4, 55)] = 15
        img[box(wx, 41, wx + 1, 48)] = 9
    # the cathedral: a long nave and two towers with slender copper spires
    nave = box(118, 30, 204, 62)
    ramp(img, nave, 0.95 - (xx - 118) / 100, [8, 2, 3])
    bricks(img, nave)
    roof = poly([(116, 30), (128, 16), (196, 16), (206, 30)])
    ramp(img, roof, 0.8 - (xx - 116) / 90 * 0.6, [0, 15, 14])
    img[roof & ((xx - yy) % 4 == 0)] = 15
    for tx in (124, 146):
        t = box(tx, 20, tx + 14, 62)
        ramp(img, t, 0.95 - (xx - tx) / 16, [8, 2, 3])
        bricks(img, t)
        img[box(tx - 1, 20, tx + 15, 22)] = 13
        img[poly([(tx - 1, 20), (tx + 7, -16), (tx + 15, 20)])] = 7
        img[poly([(tx + 7, 20), (tx + 7, -16), (tx + 15, 20)])] = 5
        img[poly([(tx + 3, 30), (tx + 7, 25), (tx + 11, 30)]) | box(tx + 3, 30, tx + 11, 42)] = 13
        img[poly([(tx + 4, 30), (tx + 7, 26), (tx + 10, 30)]) | box(tx + 4, 30, tx + 10, 41)] = 15
    for wx in range(166, 200, 9):
        img[poly([(wx - 1, 38), (wx + 2, 33), (wx + 5, 38)]) | box(wx - 1, 38, wx + 5, 56)] = 13
        img[poly([(wx, 38), (wx + 2, 34), (wx + 4, 38)]) | box(wx, 38, wx + 4, 55)] = 15
        img[box(wx, 39, wx + 1, 46)] = 9
    # trees along the island's bank, in front of the walls
    crowns = (ridge(58, 14, 9, 81) & (yy < 64)) & ~box(60, 0, 118, 96)
    crowns |= ellipse(76, 40, 104, 66) | ellipse(96, 46, 120, 66) | ellipse(204, 36, 240, 66)
    foliage(img, crowns & (yy < 64), 85)
    img[box(0, 62, W, 65)] = 14                                              # the stone quay
    img[box(0, 64, W, 65)] = 15
    # the Tumski bridge: two low iron spans arching up to the deck from stone piers, lamps
    deck = np.zeros((H, W), bool)
    for ax in (70, 140):
        under = ellipse(ax - 1, 60, ax + 71, 88)
        deck |= under & ~ellipse(ax + 1, 62, ax + 69, 90) & (yy >= 59) & (yy < 66)
        for k in range(ax + 4, ax + 68, 4):
            deck |= (xx == k) & (yy >= 59) & (yy < 66) & ~under
    deck |= box(0, 56, 216, 60) | box(0, 52, 216, 53)
    for k in range(2, 214, 3):
        deck |= box(k, 53, k + 1, 56)
    img[deck] = 7
    img[box(0, 59, 216, 60)] = 5
    for lx in range(6, 214, 24):
        img[box(lx, 46, lx + 1, 56)] = 0
        img[box(lx - 1, 43, lx + 2, 46)] = 4
    for px0 in (64, 138, 208):
        img[box(px0, 59, px0 + 6, 66)] = 14
        img[box(px0, 59, px0 + 2, 66)] = 13
    water = yy >= 66
    reflect(img, water, 66, 82)
    for px0 in (64, 138, 208):                                              # the piers in the water
        img[box(px0, 66, px0 + 6, 76)] = 15
        img[box(px0, 66, px0 + 2, 76)] = 14
        img[box(px0 - 1, 74, px0 + 7, 76)] = 13
    mist = (yy > 58) & (yy < 72) & (np.sin(xx / 13) + noise(20, 2, 83) * 2 > 1.4)
    img[mist & LEVELS[1]] = 13
    return img, ["1a2030", "2a4a3a", "3a8a6a"], ["2a3a6a", "c07a8a", "f0c080"]


def sleza_far():
    """Mount Sleza over the plain at dusk: a forested cone with its little church on top and
    Radunia beside it, mist at its foot, a patchwork of fields and hedgerows, a village lighting
    its windows; a post windmill and a wayside shrine near us."""
    img = np.full((H, W), SKY)
    stars(img, 30, yy < 28, 91)
    glow(img, 10, 64, 60, [SKY, 2, 3])
    # the massif: forest texture, paler into the mist below, the last light on its left flank
    mount = poly([(40, 66), (96, 30), (120, 16), (132, 16), (160, 30), (186, 40), (200, 38),
                  (240, 56), (240, 66)]) | ridge(62, 6, 30, 92)
    haze = (yy - 16) / 70
    ramp(img, mount, np.clip(0.1 + 0.35 * noise(5, 3, 95) + haze * 0.7, 0, 1), [15, 1, 7])
    rim = mount & ~np.roll(mount, 2, axis=1) & (xx < 126)
    img[rim & LEVELS[2]] = 3
    img[box(124, 9, 130, 16) | poly([(123, 9), (127, 5), (131, 9)])] = 0      # the church on top
    img[box(126, 1, 128, 6)] = 0
    # the plain: fields and hedgerows in perspective
    plain = yy >= 60
    fields = [(60, 64, 5), (64, 69, 3), (69, 75, 5), (75, 82, 8)]
    for k, (y0, y1, col) in enumerate(fields):
        band = box(0, y0, W, y1)
        img[band] = col
        img[band & (noise(14, 2, 50 + k) > 0.55) & LEVELS[2]] = 1 if col != 1 else 5
        img[box(0, y1 - 1, W, y1)] = 15                                       # a hedgerow
        r = np.random.default_rng(60 + k)
        for _ in range(6 + k * 2):
            tx = int(r.integers(0, W))
            tr = 2 + k
            img[ellipse(tx - tr, y1 - tr * 2, tx + tr, y1) & (yy < y1)] = 15
    mist = (yy > 54) & (yy < 66) & (noise(18, 2, 97) > 0.42)
    img[mist & LEVELS[1]] = 13
    for hx in (150, 160, 172, 181):                                           # the village
        img[box(hx, 64, hx + 7, 69) | poly([(hx - 1, 64), (hx + 3, 60), (hx + 8, 64)])] = 15
        img[box(hx + 2, 66, hx + 3, 67)] = 4
    img[box(166, 54, 168, 64) | poly([(165, 54), (167, 49), (169, 54)])] = 15
    # near: the hillock and its post windmill, the shrine
    hill = ellipse(4, 68, 84, 120) & (yy < 90)
    ramp(img, hill, 0.2 + 0.2 * noise(4, 2, 99), [0, 15])
    img[box(42, 50, 45, 72)] = 0                                              # the post
    body = box(34, 40, 54, 58) | poly([(33, 40), (44, 32), (55, 40)])
    img[body] = 0
    img[box(34, 40, 36, 58)] = 15
    img[box(42, 56, 46, 64) | box(38, 60, 50, 62)] = 0                      # the stair
    for a in (0.6, 2.17, 3.74, 5.31):
        dx, dy = np.cos(a), np.sin(a)
        px_, py_ = -dy * 3, dx * 3
        sail = poly([(44, 46), (44 + dx * 26, 46 + dy * 26), (44 + dx * 26 + px_, 46 + dy * 26 + py_),
                     (44 + dx * 6 + px_, 46 + dy * 6 + py_)])
        img[sail] = 0
        img[sail & ((xx + yy) % 3 == 0)] = 15                                 # the lattice
        img[(np.abs((xx - 44) * dy - (yy - 46) * dx) < 0.7) & (np.hypot(xx - 44, yy - 46) < 27)] = 0
    img[box(196, 62, 200, 86) | box(192, 56, 204, 62) | poly([(190, 56), (198, 48), (206, 56)])] = 0
    img[box(196, 58, 200, 61)] = 4
    img[box(197, 44, 199, 49) | box(195, 46, 201, 47)] = 0
    ground = yy >= 84
    ramp(img, ground, 0.2 + 0.25 * noise(4, 2, 98), [0, 15])
    return img, ["1a2a2a", "2a4a30", "4a5a7a"], ["101a40", "6a4a6a", "d0806a"]


def forest():
    """The night forest on the way up the mountain: beech trunks in layers of fog, lit by the
    moon on their right, granite boulders, roots and ferns by the path, toadstools."""
    img = np.full((H, W), SKY)
    r = np.random.default_rng(101)
    # layers from far to near: paler and thinner far away, the fog between them
    for depth, (cols, n, wmin) in enumerate((([5, 5, 7], 22, 2), ([15, 15, 7], 14, 4), ([0, 0, 15, 14], 9, 7))):
        fog = (yy > 40) & (noise(16, 2, 120 + depth) > 0.55)
        img[fog & LEVELS[1] & (img == SKY)] = 7
        for _ in range(n):
            x = int(r.integers(-10, W))
            w = int(r.integers(wmin, wmin + 4))
            trunk = box(x, 0, x + w, 86 - depth * 0)
            shade = (xx - x) / max(w, 1)                                    # the moon on the right
            ramp(img, trunk, np.clip((shade - 0.45) * 1.8, 0, 1), cols)
            if depth == 2:
                img[trunk & ((yy + x * 3) % 7 == 0) & (xx > x)] = 0              # bark
                root = poly([(x - 4, 86), (x, 76), (x + w, 76), (x + w + 4, 86)])
                ramp(img, root, np.clip((xx - x) / w * 0.8, 0, 1), cols)
    # moonlight falling through the canopy
    for sx in (60, 150, 200):
        shaft = poly([(sx, 0), (sx + 10, 0), (sx - 20, 90), (sx - 34, 90)])
        img[shaft & LEVELS[1] & (img != 0) & (img != SKY)] = 7
    # the ground: leaf litter, the path, boulders, ferns, toadstools
    ground = yy >= 80
    ramp(img, ground, np.clip(0.25 + 0.35 * noise(3, 2, 130) - (yy - 80) / 40, 0, 1), [0, 8, 1])
    path = poly([(90, 96), (156, 96), (134, 80), (118, 80)])
    ramp(img, path, 0.2 + 0.4 * noise(4, 2, 131), [0, 15, 7])
    for bx, by, bw in ((20, 84, 18), (198, 82, 24)):
        rock = ellipse(bx, by - bw // 2, bx + bw, by + 6) & (yy < by + 4)
        ramp(img, rock, np.clip((xx - bx) / bw * 0.8 + (by - yy) / 30, 0, 1), [0, 15, 14, 13])
        img[rock & (noise(2, 1, bx) > 0.7)] = 6                                 # moss
    for fx in range(4, W, 13):
        if 86 < fx < 160:
            continue
        for k in range(-2, 3):
            img[poly([(fx, 92), (fx + k * 4, 82 + abs(k) * 2), (fx + k * 4 + 1, 84 + abs(k) * 2)])] = 1
            img[poly([(fx, 92), (fx + k * 4, 82 + abs(k) * 2), (fx + k * 4 + 1, 84 + abs(k) * 2)]) & (xx > fx + 2)] = 6
    for mx, my in ((40, 90), (176, 92), (186, 89)):
        img[box(mx + 2, my, mx + 4, my + 5)] = 12
        img[ellipse(mx, my - 3, mx + 6, my + 2) & (yy <= my)] = 2
        img[box(mx + 1, my - 2, mx + 2, my - 1) | box(mx + 4, my - 1, mx + 5, my)] = 12
    return img, ["2a3a2a", "1a2030", "3a4a60"], ["05081a", "101a3a", "1a2a4a"]


def lit(img, mask, cols, light):
    """Paint mask in a material's colours from shadow to full light by the light map (0..1)."""
    ramp(img, mask, light, cols)


def workshop():
    """The shoemaker's workshop at night: a half-timbered wall, boots on a shelf, hides and tools
    on pegs, the workbench, floorboards, a window onto the town's roofs; one candle lights it,
    fading with distance."""
    img = np.zeros((H, W), int)
    cx, cy = 90, 60
    light = np.clip(1.25 - np.hypot(xx - cx, (yy - cy) * 1.3) / 100, 0.18, 1)
    wall = yy < 80
    lit(img, wall, [0, 7, 1, 5], light)                                   # plaster
    timber = box(0, 0, 8, 80) | box(56, 0, 64, 80) | box(206, 0, 214, 80) | box(0, 6, W, 11)
    timber |= poly([(64, 11), (70, 11), (100, 80), (94, 80)]) | poly([(206, 11), (200, 11), (176, 80), (182, 80)])
    lit(img, timber, [0, 0, 8, 3], light * 0.9)
    img[timber & ((xx * 3 + yy) % 9 == 0)] = 0                           # the grain
    # the window: night, the moon, the town's roofs
    win = box(150, 16, 194, 56)
    img[box(147, 13, 197, 59)] = 8
    img[win] = SKY
    stars(img, 10, win & (yy < 40), 4)
    img[ellipse(178, 20, 188, 30) & win] = 13
    roofs = win & (poly([(150, 56), (150, 44), (160, 36), (170, 44), (176, 40), (186, 46), (194, 38), (194, 56)]))
    img[roofs] = 15
    img[win & box(156, 46, 158, 49)] = 4
    img[box(171, 16, 173, 56) | box(150, 35, 194, 37)] = 8
    img[box(147, 57, 197, 60)] = 3
    # shelf with boots, each pair lit by how close it stands to the candle
    img[box(10, 38, 56, 41)] = 8
    for i, bx in enumerate(range(12, 54, 11)):
        boot = box(bx, 26, bx + 5, 38) | box(bx, 33, bx + 9, 38)
        lit(img, boot, [[0, 8, 2], [0, 15, 14], [0, 8, 3], [0, 2, 3]][i % 4], light + 0.1)
        img[box(bx, 26, bx + 5, 27) & boot] = 0
    # hides and tools hanging on pegs
    for hx, col in ((112, [0, 8, 3]), (126, [0, 8, 2])):
        hide = poly([(hx, 14), (hx + 10, 14), (hx + 12, 30), (hx + 8, 40), (hx + 2, 38), (hx - 2, 28)])
        lit(img, hide, col, light)
        img[box(hx + 4, 12, hx + 6, 15)] = 0
    img[box(220, 20, 222, 34) | box(216, 18, 226, 22)] = 15                 # a hammer
    img[box(230, 22, 231, 40) | box(228, 20, 233, 23)] = 14                 # an awl
    # the workbench, a shoe last and the candle
    top = box(20, 66, 140, 71)
    lit(img, top, [0, 8, 3, 4], light + 0.2)
    img[box(20, 70, 140, 71)] = 0
    for lx in (26, 128):
        lit(img, box(lx, 71, lx + 6, 84), [0, 0, 8], light)
    img[box(108, 60, 120, 66) | box(110, 56, 116, 60)] = 8                  # the last
    img[box(108, 60, 120, 61)] = 3
    img[box(88, 58, 92, 66)] = 12
    img[box(88, 58, 89, 66)] = 13
    img[box(89, 54, 91, 58)] = 4
    img[box(89, 55, 90, 57)] = 12
    # floorboards running towards us
    floor = yy >= 80
    lit(img, floor, [0, 0, 8, 3], light * 0.9)
    for k in range(-20, 30):
        img[floor & (np.abs(xx - (120 + k * 6 * (1 + (yy - 80) / 10))) < 0.6)] = 0
    img[box(0, 80, W, 81)] = 0
    return img, ["8a6040", "c09a6a", "4a3028"], ["0a1030", "1a2a5a", "2a3a70"]


def road():
    """The road south at sunset: Mount Sleza blue in the haze, a village and its church on the
    horizon, fields of wheat and ploughland in perspective, pollard willows along a rutted
    dirt road."""
    img = np.full((H, W), SKY)
    glow(img, 176, 60, 50, [SKY, 3, 4, 12])
    img[ellipse(170, 54, 182, 66) & (yy < 62)] = 12
    # far: the mountain and the village, pale with distance
    mount = poly([(0, 62), (28, 40), (52, 22), (62, 20), (80, 30), (118, 52), (150, 62)])
    ramp(img, mount, 0.2 + 0.45 * noise(10, 3, 77) + (xx > 60) * 0.15, [1, 7, 7])          # forested, lit from the right
    img[box(60, 16, 62, 21)] = 7
    for hx, hw in ((196, 8), (206, 6), (214, 9), (226, 7)):
        img[box(hx, 58, hx + hw, 62) | poly([(hx - 1, 58), (hx + hw // 2, 54), (hx + hw + 1, 58)])] = 1
    img[box(220, 46, 222, 58) | poly([(219, 46), (221, 38), (223, 46)])] = 1
    # fields in bands that widen towards us
    bands = [(62, 66, [3, 4]), (66, 71, [1, 5]), (71, 77, [3, 4]), (77, 84, [8, 3])]
    for k, (y0, y1, cols) in enumerate(bands):
        band = box(0, y0, W, y1)
        ramp(img, band, 0.35 + 0.4 * noise(20, 2, 40 + k), cols)
        if k == 3:                                                      # furrows towards a far point
            for f in range(-40, 60):
                img[band & (np.abs(xx - (120 + (f * 9) * (yy - 60) / 24)) < 0.6)] = 0
        img[box(0, y0, W, y0 + 1)] = 5 if k % 2 else 8
    # pollard willows along the road
    for i, wx in enumerate((14, 52, 96, 150, 204)):
        img[box(wx - 1, 66, wx + 2, 86)] = 0
        crown = ellipse(wx - 9, 50, wx + 10, 70)
        foliage(img, crown, 300 + i, (0, 5, 1))
        for k in range(-3, 4):                                          # thin shoots
            img[(np.abs(xx - (wx + k * 3 + (yy - 50) * k * 0.15)) < 0.6) & (yy > 44) & (yy < 56)] = 5
    # the wayside cross
    img[box(124, 64, 126, 86) | box(119, 68, 131, 70)] = 0
    img[box(124, 64, 125, 86)] = 8
    # the rutted dirt road and its grassy verge
    road = yy >= 84
    ramp(img, road, 0.45 + 0.3 * noise(8, 2, 61), [0, 8, 3])
    img[box(0, 84, W, 86) & LEVELS[2]] = 5
    img[box(0, 89, W, 90) | box(0, 93, W, 94)] = 0
    img[(yy == 90) & ((xx * 7) % 13 < 3)] = 3
    return img, ["5a4a7a", "4a6a3a", "7a6a9a"], ["2a1a4a", "c06a50", "f0a050"]


def sleza():
    """The summit of Sleza on Kupala night: a bonfire on the granite plateau lighting the rocks,
    spruces at the edge, the valley in mist below, the moon."""
    img = np.full((H, W), SKY)
    stars(img, 70, yy < 50, 11)
    glow(img, 200, 16, 20, [SKY, 7, 13], yy < 50)
    img[ellipse(194, 10, 206, 22)] = 12
    img[ellipse(198, 12, 202, 16)] = 13
    # the valley far below: hills, mist, a village's lights
    hills = ridge(56, 10, 40, 21)
    ramp(img, hills, 0.3 + (yy - 46) / 60, [5, 7])
    mist = (yy > 50) & (yy < 66) & (noise(20, 2, 23) > 0.45)
    img[mist & LEVELS[2]] = 13
    for vx in (30, 36, 44, 160, 168):
        img[(yy == 60) & (xx == vx)] = 4
    # spruces at the edges of the summit
    for k, (sx, sh) in enumerate(((-4, 54), (10, 46), (24, 38), (206, 50), (222, 58), (236, 44))):
        tree = poly([(sx - sh // 3, 74), (sx, 74 - sh), (sx + sh // 3, 74)])
        ramp(img, tree, 0.15 * noise(3, 1, 200 + k), [0, 15])
        for tier in range(74 - sh + 6, 74, 5):
            img[tree & (yy == tier)] = 0
    # the plateau: granite, lit by the fire, fading into the night
    fx, fy = 112, 74
    light = np.clip(1.0 - np.hypot(xx - fx, (yy - fy) * 2.2) / 80, 0, 1)
    ground = ridge(70, 4, 50, 22)
    ramp(img, ground, np.clip(light * 0.8 + 0.2 * noise(3, 2, 24), 0, 1), [0, 15, 8, 3])
    for bx, by, bw, bh in ((40, 76, 22, 12), (66, 72, 12, 8), (186, 74, 26, 14)):
        rock = ellipse(bx, by - bh, bx + bw, by + bh // 2) & (yy < by + 2)
        rl = np.clip(light * 1.2 + (bx + bw / 2 < fx) * (xx - bx) / bw * 0.4 - (bx + bw / 2 > fx) * (xx - bx) / bw * 0.4, 0, 1)
        ramp(img, rock, rl, [0, 15, 14, 3])
    # the bonfire: crossed logs, flames, smoke rising to the moon
    img[poly([(98, 80), (100, 78), (126, 74), (124, 76)]) | poly([(100, 74), (102, 72), (126, 80), (124, 82)])] = 8
    flame = poly([(100, 76), (104, 62), (108, 68), (112, 52), (116, 66), (120, 60), (124, 76)])
    img[flame] = 2
    img[poly([(104, 76), (108, 64), (112, 56), (116, 64), (120, 76)])] = 3
    img[poly([(107, 76), (112, 62), (117, 76)])] = 4
    img[poly([(110, 76), (112, 68), (114, 76)])] = 12
    smoke = (np.abs(xx - (112 + (52 - yy) * 0.6 + np.sin(yy / 6) * 4)) < 3 + (52 - yy) * 0.15) & (yy < 52)
    img[smoke & LEVELS[1] & (img == SKY)] = 14
    return img, ["1a1a2a", "2a3a4a", "5a7a9a"], ["05081a", "10204a", "2a5a7a"]


def gothic(img, x, y, w, h, frame=13, glass=15):
    """A tall pointed window in a stone frame, with a mullion and a glint of sky."""
    img[poly([(x - 1, y + w // 2), (x + w // 2, y - 1), (x + w, y + w // 2)]) | box(x - 1, y + w // 2, x + w + 1, y + h + 1)] = frame
    img[poly([(x, y + w // 2), (x + w // 2, y), (x + w - 1, y + w // 2)]) | box(x, y + w // 2, x + w, y + h)] = glass
    img[box(x + w // 2, y + 1, x + w // 2 + 1, y + h)] = frame
    img[box(x, y + w // 2 + 1, x + 1, y + h // 2)] = 9


def krakow():
    """Krakow's market square at dusk: the Cloth Hall, ochre plaster over gothic arcades under a
    renaissance attic of masks and pinnacles; St Mary's in brick with its two unequal towers,
    the bugler's spire with its golden crown and the domed bell tower; cobbles."""
    img = np.full((H, W), SKY)
    glow(img, 60, 80, 70, [SKY, 3, 4])
    r = np.random.default_rng(55)
    for k, (x, w, top) in enumerate(((0, 20, 46), (20, 24, 40), (44, 18, 48), (126, 22, 44))):
        img[box(x, top, x + w, 60)] = 15                                    # tenements behind
        img[poly([(x, top), (x + w // 2, top - 10), (x + w, top)])] = 15
        for wx in range(x + 3, x + w - 3, 5):
            img[box(wx, top + 4, wx + 2, top + 8)] = 4 if r.random() < 0.4 else 0
    # St Mary's: brick nave and roof, tall windows
    nave = box(150, 50, 236, 84)
    ramp(img, nave, 0.9 - (xx - 150) / 110, [8, 2, 3])
    bricks(img, nave)
    roof = poly([(148, 50), (168, 34), (232, 34), (238, 50)])
    ramp(img, roof, 0.7 - (xx - 148) / 90 * 0.5, [0, 15, 14])
    img[roof & ((xx - yy) % 4 == 0)] = 15
    for wx in range(186, 232, 11):
        gothic(img, wx, 56, 6, 20)
    # the bugler's tower: a gothic spire with a ring of turrets and a golden crown
    tw = box(158, 34, 176, 84)
    ramp(img, tw, 0.95 - (xx - 158) / 22, [8, 2, 3])
    bricks(img, tw)
    for wy in (40, 58):
        gothic(img, 164, wy, 6, 12)
    img[box(156, 32, 178, 34)] = 13
    img[poly([(158, 32), (167, 2), (176, 32)])] = 7
    img[poly([(167, 32), (167, 2), (176, 32)])] = 5
    for tx in (157, 162, 172, 177):
        img[poly([(tx - 2, 33), (tx, 21), (tx + 2, 33)])] = 7
    img[box(164, 14, 171, 18) | box(166, 10, 169, 14)] = 4
    img[box(165, 15, 166, 17)] = 12
    img[box(167, 0, 168, 10)] = 4
    # the bell tower, lower, with its renaissance helmet
    bt = box(206, 44, 222, 84)
    ramp(img, bt, 0.95 - (xx - 206) / 20, [8, 2, 3])
    bricks(img, bt)
    gothic(img, 211, 52, 6, 14)
    copper_helmet(img, 214, 46, 7)
    # the Cloth Hall
    hall = box(2, 46, 146, 84)
    ramp(img, hall, 0.95 - (xx - 2) / 220 - (yy - 46) / 160, [3, 1, 1, 10])
    img[box(2, 40, 146, 46) & ((xx + yy) % 2 == 0)] = 8                   # the roof behind the attic
    img[box(2, 40, 146, 46) & ((xx + yy) % 2 == 1)] = 2
    attic = box(2, 32, 146, 42)
    ramp(img, attic, 0.9 - (xx - 2) / 200, [3, 1, 10])
    for ax in range(4, 146, 8):                                          # pinnacles and masks
        img[poly([(ax, 33), (ax + 2, 24), (ax + 4, 33)])] = 1
        img[box(ax + 1, 22, ax + 3, 25)] = 13
        img[ellipse(ax + 4, 35, ax + 8, 39)] = 13
        img[box(ax + 5, 36, ax + 6, 37) | box(ax + 7, 36, ax + 8, 37)] = 0
    img[box(2, 42, 146, 44)] = 12
    img[box(2, 44, 146, 45)] = 3
    for wx in range(8, 144, 12):                                          # upper windows
        img[box(wx - 1, 49, wx + 5, 58)] = 12
        img[box(wx, 50, wx + 4, 57)] = 4 if r.random() < 0.6 else 15
        img[box(wx + 2, 50, wx + 3, 57)] = 12
    img[box(2, 60, 146, 62)] = 12
    for ax in range(6, 144, 12):                                          # the arcades, lit inside
        arch = poly([(ax, 70), (ax + 5, 63), (ax + 10, 70)]) | box(ax, 70, ax + 10, 84)
        img[arch] = 0
        img[arch & (yy > 72)] = 8
        img[arch & (yy > 72) & LEVELS[2]] = 3
        img[box(ax - 2, 62, ax, 84)] = 10
        img[box(ax - 1, 62, ax, 84)] = 1
    square(img, 84, 11)
    return img, ["c09a5a", "2a5a4a", "4a8a7a"], ["2a3a7a", "9a7a9a", "f0b080"]


def wawel():
    """Wawel hill over the Vistula at sunset: green slopes and brick walls with their towers, the
    castle with red roofs, the cathedral's golden Sigismund dome between copper helmets, the
    dragon's den at the foot, the river mirroring the sky."""
    img = np.full((H, W), SKY)
    glow(img, 40, 70, 50, [SKY, 3, 4])
    img[ellipse(30, 60, 50, 80) & (yy < 70)] = 12
    far = ridge(66, 6, 40, 33)
    img[far] = 1
    hill = ridge(64, 12, 50, 31) | ellipse(60, 50, 270, 130)
    ramp(img, hill, np.clip(0.55 + 0.3 * noise(5, 3, 36) - (yy - 50) / 50, 0, 1), [0, 15, 5])
    for tx, ty in ((70, 62), (82, 58), (232, 56), (96, 60)):                # trees on the slope
        foliage(img, ellipse(tx - 6, ty - 8, tx + 6, ty + 4), tx, (0, 15, 5))
    # brick fortifications and their towers
    walls = box(96, 46, 236, 66)
    for bx in (96, 150, 206):
        walls |= poly([(bx, 66), (bx + 4, 36), (bx + 22, 36), (bx + 26, 66)])
    ramp(img, walls, 0.95 - (xx - 96) / 180, [8, 2, 3])
    bricks(img, walls)
    for cx in range(98, 236, 5):
        img[box(cx, 44, cx + 3, 46) & walls] = 8
    for bx in (96, 150, 206):
        img[poly([(bx + 2, 36), (bx + 13, 24), (bx + 24, 36)])] = 2
        img[box(bx + 10, 42, bx + 15, 48)] = 0
    # the castle: pale walls, rows of windows, red roofs
    castle = box(152, 18, 232, 44)
    ramp(img, castle, 0.95 - (xx - 152) / 100, [14, 13, 12])
    img[poly([(150, 18), (160, 8), (224, 8), (234, 18)])] = 2
    img[poly([(150, 18), (160, 8), (224, 8), (234, 18)]) & ((xx - yy) % 4 == 0)] = 8
    for wy in (22, 32):
        for wx in range(156, 230, 7):
            img[box(wx - 1, wy - 1, wx + 4, wy + 6)] = 12
            img[box(wx, wy, wx + 3, wy + 5)] = 4 if (wx + wy) % 3 == 0 else 15
    # the cathedral: its walls, the golden dome, two copper helmets
    cat = box(108, 22, 150, 44)
    ramp(img, cat, 0.9 - (xx - 108) / 50, [14, 13, 12])
    for wx in (114, 126, 138):
        gothic(img, wx, 28, 5, 12)
    img[box(118, 14, 134, 22)] = 13
    img[ellipse(117, 4, 135, 26) & (yy < 15)] = 4
    img[ellipse(117, 4, 126, 26) & (yy < 15)] = 3
    img[ellipse(130, 6, 135, 20) & (yy < 13)] = 12
    img[box(125, 0, 127, 5)] = 4
    for tx, top in ((102, 4), (144, 10)):
        t = box(tx, top + 14, tx + 10, 44)
        ramp(img, t, 0.9 - (xx - tx) / 12, [8, 2, 3])
        bricks(img, t)
        copper_helmet(img, tx + 5, top + 16, 7)
    # the dragon's den at the foot of the hill
    img[ellipse(62, 64, 94, 94) & hill] = 0
    img[ellipse(66, 68, 90, 94) & hill & ((xx + yy) % 2 == 0)] = 15
    img[box(0, 78, W, 80)] = 15                                            # the embankment
    img[box(0, 78, W, 79)] = 14
    reflect(img, yy >= 80, 80, 34)
    return img, ["3a2a4a", "2a4a3a", "4a9a7a"], ["4a2a6a", "b05a6a", "f0b070"]


def hall():
    """King Krak's hall in Wawel: a coffered ceiling, tapestries of green foliage, wood panelling,
    sunbeams from the tall windows, the throne on its dais under a red canopy with the white
    eagle, a checkered marble floor running to the throne."""
    img = np.zeros((H, W), int)
    light = np.clip(0.75 - np.abs(xx - 120) / 260, 0, 1)
    ramp(img, yy < 80, light * 0.8, [0, 15, 14])                           # plaster above
    # the coffered ceiling
    ceil = yy < 14
    img[ceil] = 8
    for cx in range(0, W, 16):
        for cy in (1, 8):
            img[box(cx + 2, cy, cx + 14, cy + 5)] = 0
            img[box(cx + 3, cy + 1, cx + 13, cy + 4)] = 8
            img[box(cx + 7, cy + 2, cx + 9, cy + 3)] = 4
    img[box(0, 13, W, 15)] = 4
    img[box(0, 15, W, 18) & ((xx // 4) % 2 == 0)] = 2                    # the painted frieze
    img[box(0, 15, W, 18) & ((xx // 4) % 2 == 1)] = 3
    # tall windows at the ends, their beams across the floor
    for wx in (2, 222):
        img[box(wx - 2, 20, wx + 18, 66)] = 13
        img[box(wx, 22, wx + 16, 64)] = SKY
        img[box(wx + 7, 22, wx + 9, 64) | box(wx, 42, wx + 16, 44)] = 14
    for wx, d in ((18, 1), (222, -1)):
        beam = poly([(wx, 22), (wx, 64), (wx + d * 90, 96), (wx + d * 60, 96)])
        img[beam & LEVELS[1] & (yy > 40)] = 4
    # tapestries: verdure in greens and browns
    for tx in (26, 166):
        tap = box(tx, 22, tx + 48, 62)
        ramp(img, tap, np.clip(0.2 + 0.7 * noise(4, 3, tx), 0, 1), [8, 1, 5, 6])
        img[box(tx, 22, tx + 48, 24) | box(tx, 60, tx + 48, 62)] = 3
        img[box(tx, 22, tx + 2, 62) | box(tx + 46, 22, tx + 48, 62)] = 3
    # wood panelling
    pan = box(0, 64, W, 80)
    ramp(img, pan, light, [0, 8, 3])
    for px0 in range(0, W, 12):
        img[box(px0, 66, px0 + 10, 78) & ~box(px0 + 1, 67, px0 + 9, 77)] = 0
    # the canopy, the eagle, the throne on its dais
    can = box(94, 18, 146, 44) | poly([(94, 44), (100, 50), (106, 44), (112, 50), (118, 44), (124, 50),
                                       (130, 44), (136, 50), (142, 44), (146, 44)])
    ramp(img, can, 0.4 + 0.5 * np.abs(np.sin(xx / 4)), [8, 2, 2])
    img[box(94, 18, 146, 20) | box(94, 42, 146, 44)] = 4
    img[ellipse(112, 24, 128, 38) | poly([(104, 28), (120, 30), (136, 28), (130, 34), (110, 34)])] = 12
    img[box(119, 22, 121, 25)] = 4
    img[box(100, 46, 140, 80)] = 4                                         # the throne
    img[box(104, 50, 136, 72)] = 2
    img[box(104, 50, 106, 72)] = 8
    img[box(100, 46, 140, 48) | box(98, 44, 102, 50) | box(138, 44, 142, 50)] = 12
    for k, (x0, x1) in enumerate(((88, 152), (84, 156))):
        img[box(x0, 80 + k * 3, x1, 83 + k * 3)] = 13
        img[box(x0, 80 + k * 3, x1, 81 + k * 3)] = 12
    # the marble floor in perspective and the carpet
    floor = yy >= 86
    vx, vy = 120, 40
    u = (xx - vx) / (yy - vy + 1e-6) * 14
    v = 700 / (yy - vy + 1e-6)
    checker = ((np.floor(u / 3) + np.floor(v)) % 2 == 0)
    img[floor & checker] = 13
    img[floor & ~checker] = 15
    img[poly([(104, 86), (136, 86), (176, 96), (64, 96)])] = 2
    img[poly([(104, 86), (106, 86), (68, 96), (64, 96)]) | poly([(134, 86), (136, 86), (176, 96), (172, 96)])] = 4
    for cx in (58, 182):                                                  # chandeliers
        img[box(cx, 0, cx + 1, 26)] = 0
        img[box(cx - 10, 26, cx + 11, 28)] = 4
        for k in range(-10, 12, 5):
            img[box(cx + k, 22, cx + k + 1, 26)] = 12
            img[box(cx + k, 20, cx + k + 1, 22)] = 4
    return img, ["3a4a2a", "4a6a3a", "000000"], ["203060", "3a5aa0", "8ab0e0"]


def cellars():
    """The devil's cellars: a cavern of rough rock lit red from below by a lava river, stalactites
    with glints, columns fading into the smoke, chains, a cauldron on its fire, the pact on a
    stone lectern between candles, bones on the ledge."""
    img = np.zeros((H, W), int)
    glowup = np.clip((yy - 10) / 86, 0, 1)                                # the lava's light, from below
    smoke = noise(18, 2, 140)
    ramp(img, np.ones((H, W), bool), np.clip(0.1 + glowup * 0.6 + (smoke - 0.5) * 0.4, 0, 1), [1, 5, 2, 3])
    # arches on columns, dark against the glowing smoke, their edges catching the light
    arches = np.zeros((H, W), bool)
    for cx in (-20, 60, 140, 220):
        arches |= box(cx - 8, 0, cx + 8, 80)
    for ax in (20, 100, 180):
        arches |= box(ax - 40, 0, ax + 40, 30) & ~ellipse(ax - 32, 10, ax + 32, 70)
    ramp(img, arches, np.clip(noise(6, 2, 142) * 0.5 + glowup * 0.3, 0, 1), [0, 0, 1])
    rim = arches & ~np.roll(arches, -1, axis=0) & (yy > 6)
    img[rim] = 2
    for cx in (-20, 60, 140, 220):
        img[box(cx + 7, 30, cx + 8, 80)] = 5
    r = np.random.default_rng(141)
    for sx in range(2, W, 9):                                             # stalactites under the arches
        top = int(np.argmax(~arches[:, min(sx + 3, W - 1)])) if (~arches[:, min(sx + 3, W - 1)]).any() else 0
        ln = top + int(r.integers(5, 14))
        st = poly([(sx, top - 1), (sx + 3, ln), (sx + 6, top - 1)])
        img[st] = 0
        img[st & (xx >= sx + 3) & (yy > ln - 4)] = 2
    # chains hanging from the vault
    for cx in (60, 178):
        img[(xx == cx) & (yy < 44) & ((yy % 4) < 3)] = 14
        img[(xx == cx + 1) & (yy < 44) & ((yy % 4) == 1)] = 13
    # the ledge the cast stands on, lit at its lip
    ledge = (yy >= 72) & (yy < 88)
    ramp(img, ledge, np.clip(0.2 + noise(4, 2, 143) * 0.35 + (yy - 72) / 40, 0, 1), [0, 1, 5, 2])
    img[box(0, 72, W, 73)] = 2
    for bx in (78, 140, 228):                                               # bones and a skull
        img[box(bx, 86, bx + 7, 87) | box(bx - 1, 85, bx + 1, 88) | box(bx + 6, 85, bx + 8, 88)] = 13
    img[ellipse(150, 82, 156, 88)] = 12
    img[box(151, 84, 152, 85) | box(154, 84, 155, 85)] = 0
    # the lava river, its crust and glare
    lava = yy >= 88
    ramp(img, lava, np.clip(0.9 - (yy - 88) / 12 + noise(6, 2, 77) * 0.3, 0, 1), [2, 3, 4, 12])
    img[lava & (noise(5, 2, 78) > 0.62)] = 0
    img[box(0, 87, W, 88)] = 3
    # the cauldron on its fire
    img[ellipse(26, 52, 62, 78) & (yy > 58)] = 0
    ramp(img, ellipse(28, 54, 60, 76) & (yy > 60), np.clip(0.2 + (60 - np.abs(xx - 44)) / 80, 0, 1), [0, 15, 14])
    img[ellipse(26, 56, 62, 64)] = 0
    img[ellipse(30, 57, 58, 63)] = 6
    img[ellipse(34, 58, 44, 61)] = 12
    glow(img, 44, 80, 16, [0, 2, 3, 4], (yy > 74) & (yy < 88))
    # the lectern, the pact, the candles
    lect = box(186, 52, 196, 74)
    ramp(img, lect, np.clip(0.3 + (xx - 186) / 14, 0, 1), [0, 15, 14])
    img[box(182, 48, 200, 54)] = 13
    img[box(182, 48, 200, 49)] = 12
    img[box(186, 44, 198, 50)] = 12
    img[box(188, 46, 196, 47) | box(188, 48, 194, 49)] = 2
    for cx in (180, 202):
        img[box(cx, 42, cx + 2, 52)] = 12
        img[box(cx, 42, cx + 1, 52)] = 13
        img[box(cx, 38, cx + 2, 41)] = 4
        img[box(cx, 39, cx + 1, 40)] = 12
    return img, ["2a0a10", "5a1a14", "000000"], ["000000", "300808", "c03010"]


def night():
    """Krakow by night from across the Vistula: a crescent moon with its halo, clouds silvered
    by it, the Wawel's towers and roofs dark with lit windows, the river mirroring the lights."""
    img = np.full((H, W), SKY)
    stars(img, 110, yy < 70, 61)
    mx, my = 224, 40                                                         # clear of the title's logo
    glow(img, mx, my, 30, [SKY, 7, 13])
    img[ellipse(mx - 10, my - 10, mx + 10, my + 10)] = 12
    img[ellipse(mx - 8, my - 8, mx + 2, my + 4) & ~ellipse(mx - 4, my - 12, mx + 14, my + 6)] = 13
    img[ellipse(mx - 5, my - 12, mx + 13, my + 6)] = SKY
    img[ellipse(mx - 5, my - 12, mx + 13, my + 6) & LEVELS[1] & ellipse(mx - 10, my - 10, mx + 10, my + 10)] = 7
    # clouds drifting, lit on top by the moon
    for k, (cx, cy, cw) in enumerate(((50, 30, 70), (130, 18, 50), (186, 10, 40))):
        cloud = ellipse(cx - cw // 2, cy - 5, cx + cw // 2, cy + 5) & (noise(5, 2, 160 + k) > 0.35)
        img[cloud & LEVELS[2]] = 7
        img[cloud & ~np.roll(cloud, 2, axis=0) & LEVELS[2]] = 13
    # the hill and the castle in silhouette
    hill = ridge(72, 8, 40, 62)
    ramp(img, hill, 0.15 * noise(4, 2, 163), [0, 15])
    sil = box(60, 48, 182, 74) | poly([(78, 48), (90, 30), (102, 48)]) | box(120, 26, 132, 48)         | poly([(118, 26), (126, 12), (134, 26)]) | box(150, 38, 166, 48) | poly([(148, 38), (158, 30), (168, 38)])
    sil |= ellipse(104, 34, 118, 48) & (yy < 42)
    img[sil] = 15
    img[sil & ~np.roll(sil, -1, axis=1) & (yy > 30)] = 14                  # the moon's rim on the right
    for wy in (54, 62):
        for wx in range(64, 180, 8):
            if (wx * 7 + wy) % 5:
                img[box(wx, wy, wx + 3, wy + 4)] = 4
    img[box(124, 32, 128, 38)] = 4
    img[box(0, 74, W, 76)] = 0                                               # the embankment
    reflect(img, yy >= 76, 76, 165)
    img[(yy >= 77) & (np.abs(xx - 224 - np.sin(yy) * 2) < 2 + (yy - 76) * 0.4) & (yy % 2 == 0) & ((xx + yy * 3) % 5 < 3)] = 13   # the moon path
    return img, ["000000", "1a2a40", "4a6a8a"], ["05051a", "101a40", "2a3a60"]


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
    # bank 0 holds the header and the cast, spread over its MAP, the end of SPRITES and the
    # spare SFX slots (no sync needed: TIC-80 syncs a section once a frame); the backdrops go
    # to the MAP of banks 1..7, largest first, one sync each
    head = 2 + sum(23 + len(n) for n, _, _ in pieces) + 1 + 3 * 5
    parts, rest, used = [], castp, {(0, 0): head, (0, 1): 0, (0, 2): 0}
    datas = {pl: bytearray() for pl in used}
    for pl in ((0, 0), (0, 1), (0, 2)):
        room = REGIONS[pl[1]][1] - used[pl]
        piece, rest = rest[:room], rest[room:]
        if piece:
            parts.append((REGIONS[pl[1]][0] + used[pl], len(piece)))
            datas[pl] = bytearray(used[pl]) + piece
            used[pl] += len(piece)
    if rest:
        raise ValueError(f"the cast is {len(rest)} B too big for bank 0")
    where = {}
    for name, packed, _ in sorted(pieces, key=lambda p: -len(p[1])):
        for bank in range(1, BANKS):
            pl = (bank, 0)
            used.setdefault(pl, 0)
            datas.setdefault(pl, bytearray())
            if used[pl] + len(packed) <= REGIONS[0][1]:
                where[name] = (pl, used[pl])
                datas[pl] += packed
                used[pl] += len(packed)
                break
        else:
            raise ValueError(f"no room for the backdrop {name}")
    table = bytearray([len(pieces), len(sprites)])
    for name, packed, colours in pieces:
        (bank, r), off = where[name]
        table += bytes([len(name)]) + name.encode() + bytes([bank]) + (REGIONS[r][0] + off).to_bytes(3, "little")
        for h in colours:
            table += bytes(hexrgb(h))
    table += bytes([len(parts)])
    for at, n in parts + [(0, 0)] * (3 - len(parts)):
        table += at.to_bytes(3, "little") + n.to_bytes(2, "little")
    assert len(table) == head
    datas[(0, 0)][:head] = table
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
