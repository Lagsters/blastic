"""Render the bomb explosion sample: a falling low thump under a dark noise blast.

Usage: python boom.py <out.wav>
0.8 s at 32 kHz; wav2tic.py --sfx stores it next to the music. Needs numpy, scipy, soundfile.
"""
import sys
import numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt

SR = 32000
LENGTH = 0.8
rng = np.random.default_rng(3)


def filt(x, kind, freq):
    return sosfilt(butter(2, freq, kind, fs=SR, output='sos'), x)


def main():
    t = np.arange(int(SR * LENGTH)) / SR
    pitch = 35 + 110 * np.exp(-t * 14)                      # 145 Hz falling to 35 Hz
    thump = np.sin(2 * np.pi * np.cumsum(pitch) / SR) * np.exp(-t * 3.5)
    noise = rng.uniform(-1, 1, len(t))
    # Kept below ~600 Hz: brighter noise or crackle reads as shrill in the game mix.
    blast = filt(noise, 'low', 600) * np.exp(-t * 14) + filt(noise, 'low', 250) * np.exp(-t * 4)
    attack = np.minimum(1, t / 0.002)
    boom = (thump * 1.4 + blast * 0.9) * attack
    boom = np.tanh(boom * 3.5)  # dense: as loud as the PCM channel allows
    boom[-800:] *= np.linspace(1, 0, 800)
    sf.write(sys.argv[1], (boom / np.abs(boom).max() * 0.95).astype(np.float32), SR, subtype="PCM_16")
    print(sys.argv[1], LENGTH, "s")


if __name__ == "__main__":
    main()
