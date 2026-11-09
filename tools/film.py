#!/usr/bin/env python3
"""Turn the frames recorded by tools/film.lua into a video or a contact sheet.

python tools/film.py <dir> <out.mp4> [fps=30]     needs ffmpeg on PATH; muxes audio.raw in
python tools/film.py <dir> <out.png> --sheet N    every N-th frame on one sheet
Text is drawn with Pillow's font, so it looks different from TIC-80's.
"""
import sys, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FW, FH, ZOOM = 240, 136, 3
FRAME = 16320 + 48 + 136 * 3


def frames(d):
    texts = {}
    for line in open(f"{d}/texts.txt", encoding="utf-8"):
        n, x, y, c, scale, t = line.rstrip("\n").split("\t", 5)
        texts.setdefault(int(n), []).append((int(x), int(y), int(c), int(scale), t))
    data = open(f"{d}/frames.bin", "rb").read()
    for k in range(len(data) // FRAME):
        chunk = data[k * FRAME:(k + 1) * FRAME]
        px, pal, rows = chunk[:16320], chunk[16320:16368], chunk[16368:]
        b = np.frombuffer(px, np.uint8).reshape(FH, FW // 2)
        idx = np.empty((FH, FW), np.uint8)
        idx[:, 0::2], idx[:, 1::2] = b & 15, b >> 4
        rgb = np.frombuffer(pal, np.uint8).reshape(16, 3)[idx]
        sky = np.frombuffer(rows, np.uint8).reshape(FH, 1, 3)
        rgb = np.where((idx == 11)[:, :, None], sky, rgb)
        img = Image.fromarray(rgb.astype(np.uint8))
        img = img.resize((FW * ZOOM, FH * ZOOM), Image.NEAREST)
        draw = ImageDraw.Draw(img)
        for x, y, c, scale, t in texts.get(k + 1, []):
            font = ImageFont.load_default(size=6 * ZOOM * scale)
            draw.text((x * ZOOM, y * ZOOM), t, fill=tuple(pal[c * 3:c * 3 + 3]), font=font)
        yield img


def main():
    d, out = sys.argv[1], sys.argv[2]
    if "--sheet" in sys.argv:
        step = int(sys.argv[sys.argv.index("--sheet") + 1])
        picked = [im for k, im in enumerate(frames(d)) if k % step == step // 2]
        cols = 4
        w, h = FW * ZOOM // 2, FH * ZOOM // 2
        rows = (len(picked) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * w, rows * h), (255, 255, 255))
        for i, im in enumerate(picked):
            sheet.paste(im.resize((w - 4, h - 4)), ((i % cols) * w, (i // cols) * h))
        sheet.save(out)
        return
    fps = sys.argv[3] if len(sys.argv) > 3 else "30"
    audio = ["-f", "u8", "-ar", "7680", "-ac", "1", "-i", f"{d}/audio.raw", "-c:a", "aac", "-b:a", "128k",
             "-shortest"]
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{FW * ZOOM}x{FH * ZOOM}", "-r", fps, "-i", "-"] + audio +
                          ["-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "18", out], stdin=subprocess.PIPE)
    for im in frames(d):
        ff.stdin.write(im.tobytes())
    ff.stdin.close()
    ff.wait()


if __name__ == "__main__":
    main()
