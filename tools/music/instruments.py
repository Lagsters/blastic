"""Render the game's instrument samples and pack them into music.bin for the Lua tracker.

Usage: python instruments.py <GeneralUser-GS.sf2> <out.bin> [--preview dir]
Needs numpy, scipy, soundfile, tinysoundfont. The bass is sampled from GeneralUser GS (free
license, https://schristiancollins.com/generaluser.php), as in Amiga modules; drums and the
explosion are synthesised. blastic.lua plays the songs from these samples (see SONGS there).

TIC-80 1.4 plays 128 unsigned 8-bit samples per frame from PCM SAMPLES (0x14E24), i.e. 7680 Hz.
The blob lands in TILES+SPRITES+MAP (0x04000), memory the game does not draw from.
Layout (little endian): u8 sample count, then per sample u16 offset + u16 length in samples;
at each offset s16 predictor, u8 step index and 4-bit IMA ADPCM nibbles, low nibble first.
"""
import sys, os
import numpy as np, soundfile as sf, tinysoundfont
from scipy.signal import butter, sosfilt, resample_poly

SR = 32000
RATE = 7680
BASE_NOTE = 40                     # E2: bass samples are played back transposed from here
NAMES = ["bass", "slap", "ghost", "kick", "snare", "hat", "ohat", "boom"]
rng = np.random.default_rng(7)

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
    pred = max(-32768, min(32767, pred - d if code & 8 else pred + d))
    return pred, max(0, min(88, idx + INDEX_ADJ[code & 7]))


def adpcm_encode(x):
    """Codes for x from the best of a few start step indices; returns (pred0, idx0, codes)."""
    best = None
    for idx0 in range(0, 89, 4):
        pred, idx, codes, err = int(x[0]), idx0, [], 0
        for s in x:
            diff, step = int(s) - pred, STEPS[idx]
            code = 8 if diff < 0 else 0
            diff = abs(diff)
            if diff >= step: code |= 4; diff -= step
            if diff >= step >> 1: code |= 2; diff -= step >> 1
            if diff >= step >> 2: code |= 1
            pred, idx = adpcm_step(pred, idx, code)
            codes.append(code)
            err += (int(s) - pred) ** 2
        if best is None or err < best[3]:
            best = (int(x[0]), idx0, codes, err)
    return best[:3]


def filt(x, kind, freq):
    return sosfilt(butter(2, freq, kind, fs=SR, output='sos'), x)


def bass_notes(sf2):
    synth = tinysoundfont.Synth(samplerate=SR)
    font = synth.sfload(sf2)

    def note(preset, vel, held, total):
        synth.program_select(0, font, 0, preset)
        synth.noteon(0, BASE_NOTE, vel)
        a = np.frombuffer(synth.generate(int(SR * held)), np.float32).reshape(-1, 2).mean(1)
        synth.noteoff(0, BASE_NOTE)
        b = np.frombuffer(synth.generate(int(SR * (total - held))), np.float32).reshape(-1, 2).mean(1)
        return np.concatenate([a, b])

    return note(33, 127, 0.4, 0.5), note(36, 127, 0.25, 0.32), note(33, 60, 0.04, 0.07)


def drums():
    t = np.arange(int(SR * 0.3)) / SR
    kick = np.sin(2 * np.pi * (50 * t + 90 * (1 - np.exp(-t * 30)) / 30)) * np.exp(-t * 9)
    n = int(SR * 0.2)
    t = np.arange(n) / SR
    noise = rng.uniform(-1, 1, n)
    snare = filt(noise, 'high', 1000) * np.exp(-t * 18) * 0.6 + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30) * 0.5

    def hat(length):
        k = int(SR * length)
        return filt(rng.uniform(-1, 1, k), 'high', 2500) * np.exp(-np.arange(k) / (k / 4))

    return kick, snare, hat(0.04), hat(0.15)


def boom():
    t = np.arange(int(SR * 0.8)) / SR
    pitch = 35 + 110 * np.exp(-t * 14)                      # 145 Hz falling to 35 Hz
    thump = np.sin(2 * np.pi * np.cumsum(pitch) / SR) * np.exp(-t * 3.5)
    noise = rng.uniform(-1, 1, len(t))
    # Kept below ~600 Hz: brighter noise reads as shrill in the game mix.
    blast = filt(noise, 'low', 600) * np.exp(-t * 14) + filt(noise, 'low', 250) * np.exp(-t * 4)
    out = np.tanh((thump * 1.4 + blast * 0.9) * np.minimum(1, t / 0.002) * 3.5)
    out[-800:] *= np.linspace(1, 0, 800)
    return out


def main():
    sf2, out = sys.argv[1], sys.argv[2]
    preview = sys.argv[sys.argv.index("--preview") + 1] if "--preview" in sys.argv else None
    sounds = dict(zip(NAMES, [*bass_notes(sf2), *drums(), boom()]))
    table, data = bytearray([len(NAMES)]), bytearray()
    head = 1 + 4 * len(NAMES)
    for name in NAMES:
        x = resample_poly(sounds[name], RATE, SR)
        x = x[:len(x) & ~1] / np.max(np.abs(x)) * 0.95 * 32767
        x[-32:] *= np.linspace(1, 0, 32)
        pred, idx, codes = adpcm_encode(x)
        table += (head + len(data)).to_bytes(2, "little") + len(x).to_bytes(2, "little")
        data += int(pred).to_bytes(2, "little", signed=True) + bytes([idx])
        data += bytes(codes[j] | (codes[j + 1] << 4) for j in range(0, len(codes), 2))
        if preview:
            os.makedirs(preview, exist_ok=True)
            sf.write(os.path.join(preview, name + ".wav"), (x / 32768).astype(np.float32), RATE)
        print(f"{name:6s} {len(x) / RATE:.2f} s")
    open(out, "wb").write(table + data)
    print(f"{out}: {len(table) + len(data)} B")


if __name__ == "__main__":
    main()
