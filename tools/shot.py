#!/usr/bin/env python3
"""Scale the frames written by tools/shot.lua to PNG screenshots: python tools/shot.py <dir> <out-dir>"""
import sys
from PIL import Image, ImageDraw, ImageFont

SWEETIE16 = "1a1c2c 5d275d b13e53 ef7d57 ffcd75 a7f070 38b764 257179 29366f 3b5dc9 41a6f6 73eff7 f4f4f4 94b0c2 566c86 333c57".split()
PAL = [tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) for h in SWEETIE16]
ZOOM = 4

def render(src, name, dst):
    with open(f"{src}/{name}.pgm") as f:
        tok = f.read().split()
    w, h = int(tok[1]), int(tok[2])
    img = Image.new("RGB", (w, h))
    img.putdata([PAL[int(v)] for v in tok[4:4 + w * h]])
    img = img.resize((w * ZOOM, h * ZOOM), Image.NEAREST)
    draw = ImageDraw.Draw(img)
    for line in open(f"{src}/{name}.txt", encoding="utf-8"):
        text, x, y, c, scale = line.rstrip("\n").split("\t")
        x, y, c, scale = int(x), int(y), int(c), int(scale)
        if y < 0 or y >= h:
            continue
        font = ImageFont.load_default(size=7 * ZOOM * scale)
        draw.text((x * ZOOM, y * ZOOM), text, fill=PAL[c], font=font)
    img.save(f"{dst}/{name}.png", optimize=True)

if __name__ == "__main__":
    for n in ("title", "game"):
        render(sys.argv[1], n, sys.argv[2])
