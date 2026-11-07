"""Paint the backdrops of the story scenes and pack them into scenes.bin for blastic.lua.

Usage: python tools/scenes/paint.py <out.bin> [--preview dir]
Needs numpy and Pillow. Each backdrop is 240x96 pixels (the screen between the letterbox
bars), painted straight in palette indices: twelve colours are shared with the cast, four
(1, 5, 7, 11) belong to the backdrop, and 11 is the sky, which blastic.lua re-colours on
every scanline (BDR) into a smooth gradient, as the Amiga copper did.
Shading is ordered dithering with a horizontal period of two pixels, so every byte of a row
repeats and the byte RLE below packs it well.

The cast (cast.py) follows the backdrops.

Layout: u8 backdrop count, u8 sprite count; per backdrop u16 offset (from the start of the
blob), 3 RGB colours (indices 1, 5, 7) and 3 RGB sky stops (top, middle, bottom); per sprite
u16 offset. A backdrop is its 4-bit pixels (low nibble left), rows top down, byte RLE: c<128
copies the next c+1 bytes, c>=128 repeats the next byte c-126 times. A sprite is u8 name length,
the name, u8 width, height, x and y offset (of a patch over its bust), then per row runs of
colour<<4 | length-1 (11 is transparent).
"""
import sys, os
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
import cast

W, H = 240, 96
SHARED = {0: "1a1c2c", 2: "b13e53", 3: "ef7d57", 4: "ffcd75", 6: "38b764", 8: "5c3a1a",
          9: "3b5dc9", 10: "ffccaa", 12: "f4f4f4", 13: "94b0c2", 14: "566c86", 15: "333c57"}
SKY = 11
NAMES = ["rynek", "workshop", "road", "sleza", "wawel", "hall", "cellars", "night"]
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

def rynek():
    img = np.full((H, W), SKY)
    # tenements: gables of the market square, each its own colour
    x, k = -6, 0
    cols = [1, 5, 7, 3, 1, 5]
    while x < W:
        w = 26 + (k * 7) % 10
        top = 30 + (k * 13) % 14
        c = cols[k % len(cols)]
        body = box(x, top, x + w, H)
        gable = poly([(x, top), (x + w // 2, top - 14 - k % 3 * 4), (x + w, top)])
        ramp(img, body | gable, 0.9 - (xx - x) / w * 0.5, [15, c, c])
        for wy in range(top + 6, 76, 11):
            for wx in range(x + 4, x + w - 4, 8):
                lit = (wx * 7 + wy * 3 + k) % 5 < 2
                img[box(wx, wy, wx + 3, wy + 6)] = 4 if lit else 15
        x += w
        k += 1
    # the gothic town hall in the middle: stepped gable and a tall spire
    hall = box(84, 30, 156, H)
    ramp(img, hall, 0.9 - (yy - 30) / 120 - (xx - 84) / 300, [15, 14, 13])
    for i in range(6):
        img[box(92 + i * 10, 22 + abs(i - 2.5) * 4, 100 + i * 10, 30)] = 14
    spire = poly([(112, 4), (120, -20), (128, 4)]) | box(112, 4, 128, 30)
    ramp(img, spire, 0.4 + 0.3 * (xx - 112) / 16, [15, 14, 13])
    img[ellipse(114, 10, 125, 21)] = 12
    img[box(119, 12, 120, 17)] = 0
    img[box(119, 16, 123, 17)] = 0
    for wx in range(92, 150, 12):
        img[poly([(wx, 52), (wx + 3, 46), (wx + 6, 52)]) | box(wx, 52, wx + 6, 66)] = 4
    # cobbles, darker towards the viewer
    street = yy >= 82
    ramp(img, street, 0.8 - (yy - 82) / 16, [0, 15, 14])
    # a street lamp in front
    img[box(200, 50, 202, H)] = 0
    glow(img, 201, 48, 16, [SKY, 4, 12], ~street & (img == SKY))
    img[box(197, 44, 205, 50)] = 4
    return img, ["8a6a3c", "a05a6a", "4a7a5a"], ["202a5a", "b06a5a", "f0a060"]


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


def wawel():
    img = np.full((H, W), SKY)
    glow(img, 60, 70, 50, [SKY, 3, 4])
    hill = ridge(74, 14, 50, 31) | ellipse(90, 56, 250, 130)
    ramp(img, hill, 0.75 - (yy - 56) / 40, [0, 15, 5])
    # the castle: walls, red roofs, the cathedral's golden dome
    walls = box(110, 34, 220, 64)
    ramp(img, walls, 0.95 - (xx - 110) / 150, [14, 13, 12])
    for rx in range(110, 220, 22):
        img[poly([(rx - 2, 34), (rx + 11, 22), (rx + 24, 34)])] = 2
    img[box(150, 14, 170, 34)] = 13
    img[ellipse(150, 4, 170, 22)] = 4
    img[box(159, 0, 161, 6)] = 4
    for wx in range(116, 216, 9):
        img[box(wx, 42, wx + 3, 48)] = 4 if wx % 3 else 15
    img[ellipse(118, 66, 146, 96) & hill] = 0  # the dragon's den
    # the Vistula with broken reflections
    river = yy >= 84
    img[river] = 7
    refl = river & (noise(6, 1, 34) > 0.55) & ((yy % 3) == 0)
    img[refl] = 4
    return img, ["000000", "3a2a5a", "3a4a8a"], ["4a2a6a", "b05a6a", "f0b070"]


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
    img = np.zeros((H, W), int)
    ramp(img, np.ones((H, W), bool), 0.2 + yy / H * 0.6, [0, 1, 5])
    for ax in [-20, 80, 180]:  # arches into the dark
        img[ellipse(ax, 10, ax + 80, 130)] = 0
        img[ellipse(ax + 8, 18, ax + 72, 130)] = SKY
    glow(img, 120, H, 70, [SKY, 2, 3, 4], yy > 60)
    for sx in range(5, W, 23):  # stalactites
        img[poly([(sx, 0), (sx + 4, 8 + sx % 13), (sx + 8, 0)])] = 0
    for cx in [40, 200]:  # chains
        img[(xx == cx) & (yy < 50) & ((yy % 4) < 3)] = 14
    img[yy >= 88] = 0
    return img, ["3a1010", "6a2020", "000000"], ["000000", "400a10", "a02010"]


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

def rle(data: bytes) -> bytes:
    out, i, n = bytearray(), 0, len(data)
    lit = bytearray()

    def flush():
        while lit:
            part = lit[:128]
            out.append(len(part) - 1)
            out.extend(part)
            del lit[:128]

    while i < n:
        j = i
        while j < n and data[j] == data[i] and j - i < 129:
            j += 1
        if j - i >= 3:
            flush()
            out.append(j - i + 126)
            out.append(data[i])
            i = j
        else:
            lit.append(data[i])
            i += 1
    flush()
    return bytes(out)


def unrle(data: bytes) -> bytes:
    out, i = bytearray(), 0
    while i < len(data):
        c = data[i]
        if c < 128:
            out += data[i + 1:i + 2 + c]
            i += c + 2
        else:
            out += bytes([data[i + 1]]) * (c - 126)
            i += 2
    return bytes(out)


def pack(img):
    img = img.astype(np.uint8)
    return bytes((img[:, 0::2] | (img[:, 1::2] << 4)).flatten())


def main():
    out = sys.argv[1]
    preview = sys.argv[sys.argv.index("--preview") + 1] if "--preview" in sys.argv else None
    sprites = cast.sprites()
    head = 2 + len(NAMES) * 20 + len(sprites) * 2
    table, data = bytearray([len(NAMES), len(sprites)]), bytearray()
    for name in NAMES:
        img, own, sky = globals()[name]()
        raw = pack(img)
        packed = rle(raw)
        assert unrle(packed) == raw
        table += (head + len(data)).to_bytes(2, "little")
        for h in own + sky:
            table += bytes(hexrgb(h))
        data += packed
        print(f"{name:9s} {len(packed):5d} B")
        if preview:
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
            Image.fromarray(rgb).resize((W * 3, H * 3), Image.NEAREST).save(
                os.path.join(preview, name + ".png"))
    for name, (ox, oy, px) in sprites.items():
        table += (head + len(data)).to_bytes(2, "little")
        data += bytes([len(name)]) + name.encode() + bytes([px.shape[1], px.shape[0], ox, oy])
        for row in px:
            x = 0
            while x < len(row):
                n = 1
                while x + n < len(row) and row[x + n] == row[x] and n < 16:
                    n += 1
                data.append(int(row[x]) << 4 | (n - 1))
                x += n
    print(f"cast      {len(sprites)} sprites")
    blob = table + data
    open(out, "wb").write(blob)
    print(f"{out}: {len(blob)} B")


if __name__ == "__main__":
    main()
