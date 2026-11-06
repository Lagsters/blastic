"""Compose the game music in code: funky bass guitar lead, Amiga-style synths and drums.

Usage: python compose.py <out.wav> <GeneralUser-GS.sf2>
Writes an exact loop of SONG at 128 BPM (one bar = 14400 samples at the 7680 Hz PCM rate); notes
ringing past the end wrap to the start, so the loop has no seam. The song uses only 8 distinct
bars, so wav2tic.py stores each once and replays them from an order list, like a tracker module. Needs numpy, scipy, soundfile,
tinysoundfont. The bass guitar is sampled, as in Amiga modules: GeneralUser GS (free license,
https://schristiancollins.com/generaluser.php), presets Finger Bass and Slap Bass 1.
"""
import sys
import numpy as np, soundfile as sf, tinysoundfont

SR = 32000
BPM = 128
STEP = SR * 60 // BPM // 4          # one 16th note: 3750 samples
rng = np.random.default_rng(7)

E1 = 40                              # MIDI note numbers: E2, low enough for weight, audible on small speakers
EM, C, D, AM, B7 = [52, 55, 59, 62], [48, 52, 55, 59], [50, 54, 57, 60], [57, 60, 64, 67], [47, 51, 54, 57]
# Bass riff per bar, one entry per 16th: (semitones above root, kind); kinds: n note, g ghost, p pop.
RIFF = [(0, 'n'), None, (0, 'g'), (0, 'p'), None, (0, 'n'), (0, 'g'), (-2, 'n'),
        None, (0, 'n'), (0, 'p'), (0, 'g'), (-5, 'n'), None, (-2, 'n'), (0, 'p')]
FILL = [(0, 'n'), (0, 'g'), (0, 'p'), (0, 'g'), (-2, 'n'), (-4, 'n'), (-5, 'n'), (0, 'p'),
        (-2, 'n'), (-5, 'n'), (0, 'p'), (3, 'n'), (2, 'n'), (0, 'n'), (-2, 'p'), (-1, 'p')]
# Synth melody per bar: (16th step, length in 16ths, MIDI note).
LEAD_E = [(0, 3, 71), (3, 3, 74), (6, 2, 76), (8, 6, 74)]
LEAD_A = [(0, 3, 72), (3, 3, 76), (6, 2, 79), (8, 6, 76)]
LEAD_B = [(0, 2, 75), (2, 2, 74), (4, 4, 71), (8, 8, 75)]
BAR_TYPES = {  # bass root, pad chord, bass riff, melody
    'E': (E1, EM, RIFF, []), 'C': (E1 - 4, C, RIFF, []), 'D': (E1 - 2, D, RIFF, []),
    'A': (E1 + 5, AM, RIFF, []), 'B': (E1 - 5, B7, RIFF, []),
    'e': (E1, EM, RIFF, LEAD_E), 'a': (E1 + 5, AM, RIFF, LEAD_A), 'b': (E1 - 5, B7, FILL, LEAD_B),
}
SONG = "EECD EEAB eeab EECD eeab EEAB eeab EECD".replace(" ", "")
LOOP = STEP * 16 * len(SONG)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def place(buf, start, sig):
    """Mix sig into the loop at start, wrapping the tail around to the beginning."""
    idx = (start + np.arange(len(sig))) % LOOP
    np.add.at(buf, idx, sig)


FINGER, SLAP = 33, 36            # General MIDI bass presets
VELOCITY = {'n': 127, 'g': 60, 'p': 127}


def render_bass(notes, sf2):
    """Play the riff on one string: each note releases the previous one, like a real bass."""
    synth = tinysoundfont.Synth(samplerate=SR)
    font = synth.sfload(sf2)
    synth.program_select(0, font, 0, FINGER)
    synth.program_select(1, font, 0, SLAP)
    out, pos, held = [], 0, None
    # The loop restart chokes the last note; its release tail then wraps onto the first bar.
    events = sorted(notes) + [(LOOP, None, None)]
    for start, midi, kind in events:
        if start > pos:
            out.append(np.frombuffer(synth.generate(start - pos), np.float32).reshape(-1, 2).mean(1))
            pos = start
        if held:
            synth.noteoff(*held)
            held = None
        if midi is None:
            out.append(np.frombuffer(synth.generate(SR // 2), np.float32).reshape(-1, 2).mean(1))
            break
        chan = 1 if kind == 'p' else 0
        synth.noteon(chan, midi, VELOCITY[kind])
        held = (chan, midi)
        if kind == 'g':  # dead note: muted right after the attack
            out.append(np.frombuffer(synth.generate(SR // 25), np.float32).reshape(-1, 2).mean(1))
            pos += SR // 25
            synth.noteoff(chan, midi)
            held = None
    sig = np.concatenate(out)
    bass = sig[:LOOP].copy()
    bass[:len(sig) - LOOP] += sig[LOOP:]
    return bass


def saw(freq, length, detune=0.0):
    t = np.arange(length) / SR
    return sum(2 * ((t * freq * (1 + d) + ph) % 1) - 1 for d, ph in ((-detune, 0.0), (detune, 0.37)))


def lowpass(x, alpha):
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += alpha * (v - acc)
        y[i] = acc
    return y


def pad(notes, length):
    sig = sum(saw(hz(m), length, 0.004) for m in notes) / len(notes)
    env = np.minimum(1, np.arange(length) / 2000) * np.minimum(1, (length - np.arange(length)) / 3000)
    return lowpass(sig, 0.08) * env * 0.16


def square_lead(midi, length):
    t = np.arange(length) / SR
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t) * np.minimum(1, t * 4)
    ph = np.cumsum(hz(midi) * vib / SR)
    sig = np.where(ph % 1 < 0.3, 1.0, -1.0)
    env = np.minimum(1, np.arange(length) / 150) * np.exp(-t * 1.2)
    env[-400:] *= np.linspace(1, 0, 400)
    return lowpass(sig, 0.25) * env * 0.13


def kick():
    t = np.arange(int(SR * 0.3)) / SR
    return np.sin(2 * np.pi * (50 * t + 90 * (1 - np.exp(-t * 30)) / 30)) * np.exp(-t * 9) * 0.9


def snare():
    n = int(SR * 0.2)
    t = np.arange(n) / SR
    noise = rng.uniform(-1, 1, n)
    noise = noise - lowpass(noise, 0.15)
    return (noise * np.exp(-t * 18) * 0.5 + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30) * 0.4)


def hat(open_=False):
    n = int(SR * (0.15 if open_ else 0.04))
    noise = rng.uniform(-1, 1, n)
    noise = noise - lowpass(noise, 0.5)
    return noise * np.exp(-np.arange(n) / (n / 4)) * (0.14 if open_ else 0.1)


def main():
    out = sys.argv[1]
    bass, synth, drums = np.zeros(LOOP), np.zeros(LOOP), np.zeros(LOOP)
    k, s = kick(), snare()
    notes = []
    for bar, kind in enumerate(SONG):
        root, chord, riff, lead = BAR_TYPES[kind]
        b0 = bar * 16 * STEP
        notes += [(b0 + i * STEP, root + ev[0], ev[1]) for i, ev in enumerate(riff) if ev]
        place(synth, b0, pad(chord, 16 * STEP))
        for st, ln, m in lead:
            place(synth, b0 + st * STEP, square_lead(m, ln * STEP))
        for i in range(16):
            if i in (0, 6, 10):
                place(drums, b0 + i * STEP, k)
            if i in (4, 12):
                place(drums, b0 + i * STEP, s)
            place(drums, b0 + i * STEP, hat(open_=(i % 8 == 6)) * (1.0 if i % 2 == 0 else 0.6))
    bass = render_bass(notes, sys.argv[2])
    bass = bass / np.abs(bass).max() * 0.9
    mix = bass * 2.4 + synth * 0.35 + drums * 0.45
    mix = np.tanh(mix * 2.0)
    sf.write(out, (mix / np.abs(mix).max() * 0.9).astype(np.float32), SR, subtype="PCM_16")
    print(out, LOOP / SR, "s")


if __name__ == "__main__":
    main()
