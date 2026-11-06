"""Convert a WAV into a TIC-80 PCM music blob (IMA ADPCM, beat-sliced like a tracker module).

TIC-80 1.4 plays 128 unsigned 8-bit samples per frame from PCM SAMPLES (0x14E24), i.e. 7680 Hz.
The blob fills TILES+SPRITES+MAP (0x04000, 49024 B) and continues in MUSIC PATTERNS+TRACKS
(0x11164, 11928 B), memory the game does not use; make_tic.py splits it into those cart chunks
and blastic.lua streams it.

The loop is cut into equal beat slices. When the slices do not fit, similar ones share one stored
sample (k-medoids on log-mel spectra) and an order list replays them, as in an Amiga module.

Usage: python wav2tic.py <in.wav> <out.bin> [--bars N] [--start-bar N] [--slice beats]
                         [--loop-bars N] [--gain G] [--sfx boom.wav] [--preview out.wav]
Blob layout (little endian):
  u16 slice length in samples, u8 slice count, u8 order length, u16 sound effect offset (0 = none),
  u16 sound effect length in samples, order[], then per slice s16 predictor + u8 step index, then
  4-bit IMA ADPCM nibbles (low nibble first), slices back to back; then the sound effect:
  s16 predictor + u8 step index and its nibbles.
"""
import argparse, sys
import numpy as np, soundfile as sf, librosa
from scipy.signal import resample_poly

RATE = 7680
HEADER = 8
LOW_SIZE = 0x0FF80 - 0x04000
SEAM = 384
BUDGET = LOW_SIZE + 0x13FFC - 0x11164

STEPS = [7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55,
         60, 66, 73, 80, 88, 97, 107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337,
         371, 408, 449, 494, 544, 598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552,
         1707, 1878, 2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358, 5894,
         6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350,
         22385, 24623, 27086, 29794, 32767]
INDEX_ADJ = [-1, -1, -1, -1, 2, 4, 6, 8]


def adpcm_step(pred, idx, code):
    step = STEPS[idx]
    d = step >> 3
    if code & 4: d += step
    if code & 2: d += step >> 1
    if code & 1: d += step >> 2
    pred = pred - d if code & 8 else pred + d
    pred = max(-32768, min(32767, pred))
    idx = max(0, min(88, idx + INDEX_ADJ[code & 7]))
    return pred, idx


def adpcm_encode(x, idx0):
    pred, idx = int(x[0]), idx0
    codes, err = [], 0
    for s in x:
        diff = int(s) - pred
        step = STEPS[idx]
        code = 8 if diff < 0 else 0
        diff = abs(diff)
        if diff >= step: code |= 4; diff -= step
        if diff >= step >> 1: code |= 2; diff -= step >> 1
        if diff >= step >> 2: code |= 1
        pred, idx = adpcm_step(pred, idx, code)
        codes.append(code)
        err += (int(s) - pred) ** 2
    return codes, err


def adpcm_decode(pred, idx, codes):
    out = np.empty(len(codes), np.int32)
    for i, c in enumerate(codes):
        pred, idx = adpcm_step(pred, idx, c)
        out[i] = pred
    return out


def encode_slice(x):
    best = None
    for idx0 in range(0, 89, 4):
        codes, err = adpcm_encode(x, idx0)
        if best is None or err < best[2]:
            best = (idx0, codes, err)
    return int(x[0]), best[0], best[1]


def decode_blob(blob):
    """One pass of the order list as the bytes blastic.lua pokes (pred // 256 + 128)."""
    slice_len, k, n = int.from_bytes(blob[0:2], "little"), blob[2], blob[3]
    data = HEADER + n + 3 * k
    out = []
    for s in blob[HEADER:HEADER + n]:
        h = HEADER + n + 3 * s
        pred, idx = int.from_bytes(blob[h:h + 2], "little", signed=True), blob[h + 2]
        base = data + s * slice_len // 2
        codes = [(blob[base + j // 2] >> (4 * (j & 1))) & 15 for j in range(slice_len)]
        out.append(adpcm_decode(pred, idx, codes))
    return (np.concatenate(out) // 256 + 128).astype(np.uint8)


def kmedoids(dist, k, iters=50):
    n = len(dist)
    med = [int(np.argmin(dist.sum(1)))]
    while len(med) < k:
        med.append(int(np.argmax(dist[:, med].min(1))))
    for _ in range(iters):
        changed = False
        for m in range(k):
            cost = dist[:, med].min(1).sum()
            for c in range(n):
                if c in med: continue
                trial = med[:m] + [c] + med[m + 1:]
                tc = dist[:, trial].min(1).sum()
                if tc < cost - 1e-9:
                    med, cost, changed = trial, tc, True
        if not changed: break
    return med, dist[:, med].argmin(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp"); ap.add_argument("out")
    ap.add_argument("--bars", type=int, default=0, help="loop length in bars, 0 = as many as fit the track")
    ap.add_argument("--start-bar", type=int, default=1)
    ap.add_argument("--slice", type=int, default=1, help="slice length in beats")
    ap.add_argument("--gain", type=float, default=0.8, help="peak level, leaves headroom for SFX")
    ap.add_argument("--loop-bars", type=int, default=0,
                    help="the whole input is an exact loop of N 4-beat bars (no beat tracking, no fade)")
    ap.add_argument("--sfx", help="one-shot sound (the explosion) stored after the music")
    ap.add_argument("--sfx-gain", type=float, default=0.9)
    ap.add_argument("--preview")
    a = ap.parse_args()

    y, sr = librosa.load(a.inp, sr=None, mono=True)
    x = resample_poly(y, RATE, sr)
    x = x / np.max(np.abs(x)) * a.gain * 32767
    if a.loop_bars:
        tempo = 60 * a.loop_bars * 4 * RATE / len(x)
        period = len(x) / RATE / (a.loop_bars * 4)
        slice_len = len(x) // (a.loop_bars * 4 // a.slice) & ~1
        n = a.loop_bars * 4 // a.slice
        slices = [x[i * slice_len:(i + 1) * slice_len] for i in range(n)]
    else:
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
        tempo = float(np.atleast_1d(tempo)[0])
        # A fixed grid from the median beat interval: equal slices need a constant tempo.
        period = float(np.median(np.diff(beats)))
        phase = float(np.median((beats - beats[0]) % period)) + beats[0]
        slice_len = int(round(period * a.slice * RATE)) & ~1
        first = int(round((phase + (a.start_bar * 4 * period)) * RATE))
        avail = (len(x) - first) // slice_len
        per_bar = 4 // a.slice if a.slice <= 4 else 1
        n = avail - avail % per_bar
        if a.bars: n = min(n, a.bars * per_bar)
        end = first + n * slice_len
        # The loop end fades into the audio just before the loop start, so the jump back is seamless.
        fade = min(SEAM, first)
        ramp = np.linspace(0, 1, fade)
        x[end - fade:end] = x[end - fade:end] * (1 - ramp) + x[first - fade:first] * ramp
        slices = [x[first + i * slice_len: first + (i + 1) * slice_len] for i in range(n)]

    sfx = None
    if a.sfx:
        z, zr = librosa.load(a.sfx, sr=None, mono=True)
        z = resample_poly(z, RATE, zr)
        sfx = (z / np.max(np.abs(z)) * a.sfx_gain * 32767)[:len(z) & ~1]
    header = HEADER + n + (len(sfx) // 2 + 3 if sfx is not None else 0)
    cost = slice_len // 2 + 3
    k = min(n, (BUDGET - header) // cost, 255)
    if k < 1: sys.exit("slice does not fit the budget")

    if k < n:
        mels = [librosa.power_to_db(librosa.feature.melspectrogram(y=s, sr=RATE, n_mels=48, n_fft=512,
                                                                   hop_length=256)) for s in slices]
        flat = np.array([m.ravel() for m in mels])
        dist = np.sqrt(((flat[:, None, :] - flat[None, :, :]) ** 2).mean(2))
        med, assign = kmedoids(dist, k)
    else:
        med, assign = list(range(n)), np.arange(n)

    enc = [encode_slice(slices[m]) for m in med]
    blob = bytearray()
    blob += slice_len.to_bytes(2, "little") + bytes([k, n, 0, 0, 0, 0]) + bytes(int(i) for i in assign)
    for pred, idx, _ in enc:
        blob += int(pred).to_bytes(2, "little", signed=True) + bytes([idx])
    for _, _, codes in enc:
        for j in range(0, len(codes), 2):
            blob.append(codes[j] | (codes[j + 1] << 4))
    if sfx is not None:
        pred, idx, codes = encode_slice(sfx)
        blob[4:8] = len(blob).to_bytes(2, "little") + len(sfx).to_bytes(2, "little")
        blob += int(pred).to_bytes(2, "little", signed=True) + bytes([idx])
        blob += bytes(codes[j] | (codes[j + 1] << 4) for j in range(0, len(codes), 2))
        print(f"sound effect {len(sfx) / RATE:.2f} s, {len(codes) // 2 + 3} B")
    assert len(blob) <= BUDGET, len(blob)
    open(a.out, "wb").write(blob)

    out8 = decode_blob(blob).astype(np.float32) - 128
    ref8 = np.clip(np.concatenate(slices) / 256, -128, 127)
    snr = 10 * np.log10(np.mean(ref8 ** 2) / np.mean((ref8 - out8) ** 2))
    print(f"tempo {tempo:.1f} bpm, beat {period:.3f} s, slice {slice_len} samples ({a.slice} beat)")
    print(f"loop {n} slices = {n * slice_len / RATE:.2f} s, stored {k} unique, blob {len(blob)} / {BUDGET} B")
    print(f"SNR vs 7680 Hz reference: {snr:.1f} dB")
    if a.preview:
        sf.write(a.preview, (out8 / 128).astype(np.float32), RATE)


if __name__ == "__main__":
    main()
